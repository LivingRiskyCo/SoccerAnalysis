# Tagging, Anchors, and Re-ID System Roadmap

## Overview

This document provides a comprehensive roadmap of how player tagging, anchor frames, and Re-ID (Re-Identification) work together in the soccer analysis system. It explains confidence scoring, protection windows, and how jersey numbers, shoes, and body mechanics affect player identification.

---

## 1. Player Tagging System

### 1.1 Where Tagging Occurs

**Primary Tools:**
- **Player Gallery Seeder** (`player_gallery_seeder.py`): Interactive tagging on video frames
- **Track Review & Player Assignment** (`track_review_assigner.py`): Post-analysis correction and assignment

### 1.2 Tagging Process in Player Gallery Seeder

**Step 1: Detection**
- YOLO detects players in the current frame
- Filters applied:
  - Minimum area: 2000 pixels (excludes balls)
  - Minimum height: 60 pixels
  - Aspect ratio: > 1.1 (players are taller than wide)
- Bounding boxes expanded by 5% for better visibility/clicking

**Step 2: Re-ID Feature Extraction**
- Re-ID features extracted from **original** (non-expanded) bbox for accuracy
- Features used for gallery matching

**Step 3: Anchor Frame Protection Check (PRIORITY)**
- **ANCHOR_PROTECTION_WINDOW = 150 frames** (±150 frames from anchor)
- If a detection matches an anchor-protected player:
  - Uses **1.00 confidence** (ground truth)
  - Matching criteria:
    - IoU > 0.05 OR
    - Center distance < 200px
  - Prevents duplicate assignments (one player per detection)

**Step 4: Gallery Matching (if not anchor-protected)**
- Matches against player gallery using Re-ID features
- Similarity threshold: 0.6 (configurable)
- Returns: `(player_id, player_name, similarity_score)`

**Step 5: User Assignment**
- User clicks on detection → assigns name
- Creates anchor frame with:
  - `player_name`: User-assigned name
  - `confidence: 1.00` (ground truth)
  - `bbox`: [x1, y1, x2, y2]
  - `team`: From gallery (if available)
  - `jersey_number`: From gallery (if available)
  - `frame_num`: Current frame

**Step 6: Gallery Update**
- Player added/updated in gallery with:
  - Re-ID features (body, jersey, foot)
  - Reference frame (current frame + bbox)
  - Jersey number
  - Team
  - Uniform info (jersey color, shorts, socks)

---

## 2. Anchor Frame System

### 2.1 What Are Anchor Frames?

Anchor frames are **ground truth** player tags with **1.00 confidence**. They represent manually verified player identities at specific frames.

**Format:**
```python
{
    frame_num: [
        {
            "track_id": int or None,  # Optional - may be matched by bbox
            "player_name": str,        # Required
            "bbox": [x1, y1, x2, y2], # Required for bbox matching
            "confidence": 1.00,        # Always 1.00 (ground truth)
            "team": str,               # Optional
            "jersey_number": str       # Optional
        }
    ]
}
```

### 2.2 Anchor Frame Protection Windows

**Protection Zones:**
- **HARD PROTECTION**: ±50 frames from anchor
  - Complete block of Re-ID overrides
  - Track locked to anchor player name
  
- **SOFT PROTECTION**: ±100 frames from anchor
  - 3x evidence multiplier required to override
  - Still prefers anchor assignment
  
- **DECAY ZONE**: 100-150 frames from anchor
  - Gradual decay from 3x to 1x multiplier
  - Re-ID can override with sufficient evidence
  
- **BEYOND DECAY**: >150 frames from anchor
  - No special protection
  - Re-ID operates normally

**Constants:**
```python
ANCHOR_HARD_PROTECTION_FRAMES = 50   # Hard block zone
ANCHOR_SOFT_PROTECTION_FRAMES = 100  # Full 3x multiplier zone
ANCHOR_DECAY_FRAMES = 150            # Protection ends here
```

### 2.3 Dynamic Protection Extension

**Permanent Anchor Protection:**
- Tracks assigned via anchor frames get **permanent protection**
- Protection window extends dynamically as track continues:
  - `protection_end = current_frame_num + ANCHOR_DECAY_FRAMES`
  - Ensures anchor-assigned players maintain identity for entire video

**High-Confidence History Tracking:**
- Tracks with ≥0.80 similarity for 100+ consecutive frames get **auto-protection**
- Protection window extended similar to anchor frames
- Provides automatic robust identification for consistently recognized players

### 2.4 Anchor Frame Application Priority

**Priority Order:**
1. **Anchor Frames** (1.00 confidence) - HIGHEST PRIORITY
2. **Gallery Matching** (0.0-1.0 similarity) - Standard Re-ID
3. **Alternative Matching** (conflict resolution) - Fallback

**Application Process:**
1. Check if current frame has anchor frames
2. Match anchor to detection:
   - **Priority 1**: Track ID matching (if anchor has track_id)
   - **Priority 2**: Bbox matching (IoU or center distance)
3. Apply anchor assignment:
   - Set `player_names[track_id] = anchor_player_name`
   - Set `track_name_confidence[track_id] = (name, 1.00, frame_num)`
   - Set `track_anchor_protection[track_id] = (name, start, end)`
4. Skip gallery matching for anchor-protected tracks

---

## 3. Re-ID (Re-Identification) System

### 3.1 Re-ID Feature Extraction

**Feature Types:**
- **Body Features** (40% weight): Full body appearance
- **Jersey Features** (30% weight): Jersey region appearance
- **Foot Features** (15% weight): Foot/shoe region appearance
- **General Features** (15% weight): Fallback features

**Ensemble Matching:**
- Combines all available features using weighted average
- Formula: `0.7 * weighted_avg + 0.3 * max_similarity`
- Provides robust matching even if one feature type is weak

### 3.2 Gallery Matching Process

**Step 1: Feature Normalization**
- Normalize input features to unit vector
- Validate feature quality (non-zero, non-NaN)

**Step 2: Multi-Feature Ensemble Matching**
- Match against body, jersey, foot, and general features
- Weighted combination: 40% body, 30% jersey, 15% foot, 15% general

**Step 3: Confidence Boosts and Penalties**

**Jersey Number Boost:**
- Exact match: **+0.15** (15% boost)
- Partial match (e.g., "6" vs "06"): **+0.05** (5% boost)

**Team Matching:**
- Same team: **+0.02** boost (if similarity close to threshold)
- Different team: **-0.08** penalty (8% reduction)
- Strict mode: Skip different-team players entirely

**Uniform Matching:**
- Same uniform (jersey+shorts+socks): **+0.05 to +0.10** boost
- Stored in `uniform_variants` for multi-uniform players

**Early Frame Boost:**
- Players tagged in frames 0-1000: **+0.10** boost (if similarity ≥ 0.5)
- Helps prioritize early-tagged players

**Step 4: Hard Negative Mining**
- Adjusts similarity if detection matches known hard negatives
- Reduces false positives from similar-looking players

**Step 5: Adaptive Threshold**
- Adjusts threshold based on:
  - Detection quality (confidence, image quality)
  - Gallery diversity (how similar players look)
  - Gallery size (more players = slightly stricter)
- **Never lowers below GUI threshold** (user setting respected)

**Step 6: Return Best Match**
- Returns: `(player_id, player_name, similarity_score)`
- Similarity must exceed threshold (default: 0.6)

### 3.3 Re-ID Confidence Scores

**Confidence Range:**
- **0.0 - 1.0**: Re-ID similarity score
- **1.00**: Anchor frame (ground truth, permanent)
- **≥0.80**: High confidence (auto-protection after 100 frames)
- **≥0.60**: Standard threshold (configurable in GUI)
- **<0.60**: Below threshold (no match)

**Confidence Sources:**
1. **Anchor Frames**: Always 1.00
2. **Gallery Matching**: 0.0-1.0 (cosine similarity)
3. **High-Confidence History**: ≥0.80 (after 100 consecutive frames)

---

## 4. Confidence Score System

### 4.1 Confidence Levels

| Confidence | Source | Protection | Overrideable |
|------------|--------|------------|--------------|
| **1.00** | Anchor Frame | Permanent | No (hard lock) |
| **≥0.80** | High-Confidence History | Auto-extended | Yes (with 3x evidence) |
| **0.60-0.79** | Standard Re-ID | None | Yes (normal) |
| **<0.60** | Below Threshold | None | N/A (no match) |

### 4.2 Confidence Persistence

**Anchor Frames (1.00):**
- Permanent for entire video
- Protection window extends dynamically
- Cannot be overridden by Re-ID

**High-Confidence History (≥0.80):**
- Auto-protection after 100 consecutive frames
- Protection window extends dynamically
- Can be overridden with 3x evidence

**Standard Re-ID (0.60-0.79):**
- No special protection
- Can be overridden by better matches
- Normal Re-ID operation

### 4.3 Confidence Updates

**When Confidence Changes:**
1. **Anchor Frame Applied**: → 1.00 (permanent)
2. **High-Confidence Match**: → similarity score (0.80-1.0)
3. **Standard Match**: → similarity score (0.60-0.79)
4. **Below Threshold**: → No match (confidence = 0.0)

**Confidence Storage:**
```python
track_name_confidence[track_id] = (player_name, confidence, frame_num)
```

---

## 5. Jersey, Shoes, and Body Mechanics

### 5.1 Jersey Number Impact

**Jersey Number Matching:**
- **Exact Match**: +0.15 boost (15% similarity increase)
- **Partial Match**: +0.05 boost (5% similarity increase)
- **No Match**: No penalty (Re-ID features still used)

**Jersey Number Persistence:**
- If track previously had jersey number, boost matches with that jersey
- Requires similarity ≥0.5 AND gallery threshold
- Helps maintain identity when jersey is visible

**Jersey Features:**
- 30% weight in ensemble matching
- Extracted from jersey region (top 10-40% of bbox)
- Stored separately from body features

### 5.2 Shoe/Foot Features Impact

**Foot Features:**
- 15% weight in ensemble matching
- Extracted from foot region (bottom 20% of bbox)
- Useful for identification when jersey is occluded

**Shoe Color:**
- Stored in player profile (`shoe_color: [H, S, V]`)
- Can be used for additional filtering/boosting (future enhancement)

### 5.3 Body Mechanics Impact

**Body Features:**
- 40% weight in ensemble matching (highest weight)
- Full body appearance (most reliable)
- Primary identification method

**Gait Analysis:**
- GaitAnalyzer tracks walking/running patterns
- Can be used for additional identification (future enhancement)
- Currently initialized but not fully integrated

**Pose Keypoints:**
- YOLO pose model extracts keypoints
- Can be used for body mechanics analysis (future enhancement)

### 5.4 Feature Weight Summary

| Feature Type | Weight | Use Case |
|--------------|--------|----------|
| **Body** | 40% | Primary identification |
| **Jersey** | 30% | Jersey region appearance |
| **Foot** | 15% | Shoe/foot appearance |
| **General** | 15% | Fallback features |

**Ensemble Formula:**
```
similarity = 0.7 * weighted_avg(body, jersey, foot, general) + 0.3 * max(body, jersey, foot, general)
```

---

## 6. Protection Window Duration

### 6.1 Anchor Frame Protection

**Initial Window:**
- **±150 frames** from anchor frame
- Example: Anchor at frame 100 → Protection: frames -50 to 250

**Dynamic Extension:**
- Protection window extends as track continues
- `protection_end = current_frame_num + ANCHOR_DECAY_FRAMES`
- Example: Track continues to frame 500 → Protection extends to frame 650

**Permanent Protection:**
- Anchor-assigned tracks maintain protection for entire video
- Protection window always extends ahead of current frame

### 6.2 High-Confidence History Protection

**Activation:**
- Requires ≥0.80 similarity for **100 consecutive frames**
- Example: Frames 0-99 all have ≥0.80 → Protection activates at frame 100

**Protection Window:**
- Initial: `current_frame_num ± ANCHOR_DECAY_FRAMES`
- Extends dynamically as track continues (same as anchor frames)

### 6.3 Protection Zones

**Zone 1: Hard Protection (0-50 frames from anchor)**
- Complete block of Re-ID overrides
- Track locked to protected name

**Zone 2: Soft Protection (50-100 frames from anchor)**
- 3x evidence multiplier required to override
- Strong preference for protected name

**Zone 3: Decay Zone (100-150 frames from anchor)**
- Gradual decay from 3x to 1x multiplier
- Re-ID can override with sufficient evidence

**Zone 4: Beyond Protection (>150 frames from anchor)**
- No special protection
- Normal Re-ID operation

---

## 7. Verification: Seeder Gallery Rules

### 7.1 Rules Applied in Player Gallery Seeder

✅ **Anchor Frame Protection**
- Location: `player_gallery_seeder.py` lines 523-693
- Protection window: ±150 frames
- Matching: IoU > 0.05 OR center distance < 200px
- Confidence: 1.00 for anchor-protected players

✅ **Re-ID Feature Extraction**
- Location: `player_gallery_seeder.py` lines 609-630
- Uses original (non-expanded) bbox for accuracy
- Extracts features for gallery matching

✅ **Gallery Matching**
- Location: `player_gallery_seeder.py` lines 700-798
- Uses `player_gallery.match_player()` with:
  - Re-ID features
  - Similarity threshold: 0.6
  - Jersey number (if available)
  - Team (if available)

✅ **Anchor Frame Creation**
- Location: `player_gallery_seeder.py` lines 1733-1739
- Includes:
  - `player_name`: User-assigned
  - `confidence: 1.00` (ground truth)
  - `bbox`: [x1, y1, x2, y2]
  - `team`: From gallery
  - `jersey_number`: From gallery

✅ **Gallery Update**
- Location: `player_gallery_seeder.py` lines 1086-1088, 1133-1135
- Updates player profile with:
  - Re-ID features (body, jersey, foot)
  - Reference frame
  - Jersey number
  - Team
  - Uniform info

### 7.2 Rules Applied in Main Analysis

✅ **Anchor Frame Loading**
- Location: `combined_analysis_optimized.py` lines 4343-4847
- Loads `PlayerTagsSeed-{video}.json` files
- Validates confidence = 1.00
- Filters by CSV players (if `validate_against_csv=True`)

✅ **Anchor Frame Application**
- Location: `combined_analysis_optimized.py` lines 9017-9806
- Priority: Before gallery matching
- Matching: Track ID → Bbox (IoU/center distance)
- Sets confidence = 1.00

✅ **Protection Window Initialization**
- Location: `combined_analysis_optimized.py` lines 6753-6891
- Pre-computes protection windows at startup
- Groups anchors by player/track
- Calculates full protection ranges

✅ **Dynamic Protection Extension**
- Location: `combined_analysis_optimized.py` lines 8843-8857, 8938-8939
- Extends protection window as track continues
- Formula: `protection_end = current_frame_num + ANCHOR_DECAY_FRAMES`

✅ **Gallery Matching with Boosts**
- Location: `player_gallery.py` lines 2453-3188
- Jersey number boost: +0.15 (exact), +0.05 (partial)
- Team boost: +0.02 (same team), -0.08 (different team)
- Uniform boost: +0.05 to +0.10 (same uniform)
- Early frame boost: +0.10 (frames 0-1000)

✅ **Multi-Feature Ensemble**
- Location: `player_gallery.py` lines 2697-2776
- Body: 40% weight
- Jersey: 30% weight
- Foot: 15% weight
- General: 15% weight

---

## 8. Logic Verification Checklist

### 8.1 Anchor Frame Logic

- [x] Anchor frames have confidence = 1.00
- [x] Protection window = ±150 frames
- [x] Dynamic extension as track continues
- [x] Priority: Anchor frames before gallery matching
- [x] Matching: Track ID → Bbox (IoU/center distance)
- [x] Permanent protection for anchor-assigned tracks

### 8.2 Re-ID Logic

- [x] Multi-feature ensemble matching (body, jersey, foot, general)
- [x] Jersey number boost: +0.15 (exact), +0.05 (partial)
- [x] Team boost: +0.02 (same), -0.08 (different)
- [x] Uniform boost: +0.05 to +0.10 (same uniform)
- [x] Early frame boost: +0.10 (frames 0-1000)
- [x] Adaptive threshold (never below GUI setting)
- [x] Hard negative mining integration

### 8.3 Confidence System

- [x] Anchor frames: 1.00 (permanent)
- [x] High-confidence history: ≥0.80 (auto-protection after 100 frames)
- [x] Standard Re-ID: 0.60-0.79 (no special protection)
- [x] Below threshold: <0.60 (no match)

### 8.4 Seeder Gallery Rules

- [x] Anchor protection check before gallery matching
- [x] Re-ID feature extraction from original bbox
- [x] Gallery matching with jersey/team boosts
- [x] Anchor frame creation with 1.00 confidence
- [x] Gallery update with all features (body, jersey, foot)

---

## 9. Key Constants and Parameters

### 9.1 Protection Windows

```python
ANCHOR_HARD_PROTECTION_FRAMES = 50   # Hard block zone
ANCHOR_SOFT_PROTECTION_FRAMES = 100  # Full 3x multiplier zone
ANCHOR_DECAY_FRAMES = 150            # Protection ends here
ANCHOR_PROTECTION_WINDOW = 150       # Seeder protection window
```

### 9.2 Confidence Thresholds

```python
gallery_similarity_threshold = 0.6   # Default Re-ID threshold (GUI configurable)
high_confidence_threshold = 0.80     # Auto-protection threshold
high_confidence_frames = 100         # Frames required for auto-protection
```

### 9.3 Feature Weights

```python
BODY_WEIGHT = 0.40      # 40% weight
JERSEY_WEIGHT = 0.30    # 30% weight
FOOT_WEIGHT = 0.15      # 15% weight
GENERAL_WEIGHT = 0.15   # 15% weight
```

### 9.4 Boosts and Penalties

```python
JERSEY_EXACT_BOOST = 0.15        # +15% for exact jersey match
JERSEY_PARTIAL_BOOST = 0.05      # +5% for partial jersey match
TEAM_SAME_BOOST = 0.02           # +2% for same team
TEAM_DIFF_PENALTY = 0.08         # -8% for different team
UNIFORM_BOOST = 0.05-0.10        # +5-10% for same uniform
EARLY_FRAME_BOOST = 0.10         # +10% for early-tagged players
```

---

## 10. Summary

### 10.1 Tagging Flow

1. **User tags player** in Player Gallery Seeder
2. **Anchor frame created** with confidence 1.00
3. **Protection window activated** (±150 frames)
4. **Gallery updated** with Re-ID features
5. **Player identified** in subsequent frames via anchor protection

### 10.2 Re-ID Flow

1. **Re-ID features extracted** from detection
2. **Multi-feature ensemble matching** against gallery
3. **Boosts applied** (jersey, team, uniform, early frame)
4. **Similarity calculated** (0.0-1.0)
5. **Match assigned** if similarity ≥ threshold

### 10.3 Confidence Flow

1. **Anchor frames**: 1.00 (permanent, cannot override)
2. **High-confidence history**: ≥0.80 (auto-protection after 100 frames)
3. **Standard Re-ID**: 0.60-0.79 (normal operation)
4. **Below threshold**: <0.60 (no match)

### 10.4 Protection Flow

1. **Anchor frame applied** → Protection window initialized
2. **Track continues** → Protection window extends dynamically
3. **High-confidence match** → Auto-protection after 100 frames
4. **Protection zones**:
   - Hard (0-50 frames): Complete block
   - Soft (50-100 frames): 3x evidence required
   - Decay (100-150 frames): Gradual decay
   - Beyond (>150 frames): Normal Re-ID

---

## 11. Future Enhancements

### 11.1 Planned Improvements

- **Gait Analysis Integration**: Use walking/running patterns for identification
- **Pose Keypoint Matching**: Use body pose for additional identification
- **Shoe Color Filtering**: Use shoe color for additional filtering/boosting
- **Multi-Uniform Support**: Better handling of players with multiple uniforms
- **Temporal Consistency**: Track identity across long occlusions

### 11.2 Potential Optimizations

- **Feature Caching**: Cache Re-ID features for faster matching
- **Parallel Matching**: Match multiple detections in parallel
- **Incremental Gallery Updates**: Update gallery incrementally during analysis
- **Adaptive Feature Weights**: Adjust feature weights based on detection quality

---

## 12. Troubleshooting

### 12.1 Common Issues

**Issue: Player not being identified**
- Check: Anchor frames loaded correctly?
- Check: Protection window active?
- Check: Re-ID features extracted?
- Check: Similarity threshold too high?

**Issue: Wrong player assigned**
- Check: Anchor frame protection blocking correct match?
- Check: Jersey number boost causing incorrect match?
- Check: Team filtering too strict?
- Check: Hard negative mining adjusting similarity incorrectly?

**Issue: Protection not working**
- Check: Protection window initialized?
- Check: Dynamic extension active?
- Check: Confidence = 1.00 for anchor frames?
- Check: Track ID matching correctly?

### 12.2 Diagnostic Commands

**Check anchor frames:**
```python
# In combined_analysis_optimized.py, frame 0 logs:
print(f"🎯 ANCHOR FRAMES LOADED: {total_anchor_frames} frame(s) with {total_anchor_tags} tag(s)")
```

**Check protection windows:**
```python
# In combined_analysis_optimized.py, frame 0 logs:
print(f"✓ Initialized {protection_windows_initialized} protection window(s)")
```

**Check Re-ID matching:**
```python
# In player_gallery.py, match_player logs:
print(f"✓ DIAGNOSTIC: match_player - {profile.name}: final_similarity={similarity:.3f}")
```

---

## End of Roadmap

This document provides a comprehensive overview of the tagging, anchor, and Re-ID system. For specific implementation details, refer to the source code files mentioned throughout this document.


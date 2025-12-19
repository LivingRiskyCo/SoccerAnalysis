# Seeder Gallery Rules Verification

## Summary

This document verifies that all tagging, anchor, and Re-ID rules are correctly applied in the Player Gallery Seeder (`player_gallery_seeder.py`).

---

## ✅ Verification Results

### 1. Anchor Frame Protection (PRIORITY CHECK)

**Location**: `player_gallery_seeder.py` lines 523-693

**Status**: ✅ **CORRECTLY IMPLEMENTED**

**Implementation**:
- Protection window: **±150 frames** from anchor (`ANCHOR_PROTECTION_WINDOW = 150`)
- Matching criteria: **IoU > 0.05 OR center distance < 200px** (lenient for player movement)
- Confidence: **1.00** for anchor-protected players
- Duplicate prevention: `assigned_players` set tracks which players are already assigned
- **Priority**: Checked **BEFORE** gallery matching (lines 632-687)

**Code Evidence**:
```python
# Line 523-526: Protection window calculation
ANCHOR_PROTECTION_WINDOW = 150
protection_start = max(0, anchor_frame_num - ANCHOR_PROTECTION_WINDOW)
protection_end = anchor_frame_num + ANCHOR_PROTECTION_WINDOW

# Line 632-687: Anchor protection check BEFORE gallery matching
if anchor_match and anchor_player_name:
    # Use anchor match with 1.00 confidence
    self.detected_player_matches[bbox] = (anchor_player_id, anchor_player_name, 1.00)
```

---

### 2. Re-ID Feature Extraction

**Location**: `player_gallery_seeder.py` lines 609-630 (detection), 1652-1709 (user tagging)

**Status**: ✅ **CORRECTLY IMPLEMENTED**

**Implementation**:
- Uses **original** (non-expanded) bbox for feature extraction (line 612)
- Extracts **body features** (general Re-ID features)
- Extracts **jersey features** (torso region)
- Extracts **foot features** (foot/shoe region)
- All features extracted before gallery matching

**Code Evidence**:
```python
# Line 612: Use original YOLO bbox for feature extraction (not expanded)
x1_int, y1_int, x2_int, y2_int = int(x1), int(y1), int(x2), int(y2)

# Line 1668-1674: Extract body features
features = self.reid_tracker.extract_features(self.current_frame, detections)

# Line 1683-1695: Extract jersey features
jersey_features = self.reid_tracker.extract_jersey_features(self.current_frame, detections)

# Line 1697-1709: Extract foot features
foot_features = self.reid_tracker.extract_foot_features(self.current_frame, detections)
```

---

### 3. Gallery Matching with Boosts

**Location**: `player_gallery_seeder.py` lines 710-714

**Status**: ✅ **CORRECTLY IMPLEMENTED**

**Implementation**:
- Calls `gallery.match_player()` with Re-ID features
- Similarity threshold: **0.5** (lower for display purposes)
- Gallery matching includes:
  - Jersey number boost (+0.15 exact, +0.05 partial)
  - Team boost (+0.02 same, -0.08 different)
  - Uniform boost (+0.05 to +0.10 same uniform)
  - Early frame boost (+0.10 for frames 0-1000)
  - Multi-feature ensemble (body 40%, jersey 30%, foot 15%, general 15%)

**Code Evidence**:
```python
# Line 710-714: Gallery matching
match_result = self.gallery.match_player(
    feature_vector,
    similarity_threshold=0.5  # Lower threshold for display
)
```

**Note**: The actual boosts are applied inside `player_gallery.match_player()` (see `player_gallery.py` lines 2679-2826).

---

### 4. Anchor Frame Creation

**Location**: `player_gallery_seeder.py` lines 1733-1745

**Status**: ✅ **CORRECTLY IMPLEMENTED**

**Implementation**:
- `player_name`: User-assigned name
- `confidence: 1.00` (ground truth)
- `bbox`: [x1, y1, x2, y2]
- `team`: From user input or gallery
- `jersey_number`: From user input or gallery
- `track_id`: None (matched by bbox during analysis)

**Code Evidence**:
```python
# Line 1733-1740: Anchor frame creation
anchor_entry = {
    "track_id": None,  # Will be matched by bbox position during analysis
    "player_name": player_name,
    "jersey_number": jersey,  # Include jersey number for better matching
    "team": team,
    "bbox": list(bbox),  # [x1, y1, x2, y2]
    "confidence": 1.00  # Anchor frames are ground truth
}
```

---

### 5. Gallery Update with All Features

**Location**: `player_gallery_seeder.py` lines 1774-1785

**Status**: ✅ **CORRECTLY IMPLEMENTED**

**Implementation**:
- Updates player with **all feature types**:
  - `features`: General/body features
  - `body_features`: Explicit body features
  - `jersey_features`: Jersey region features
  - `foot_features`: Foot/shoe region features
- Includes `jersey_number` and `team`
- Includes `reference_frame` (frame_num, video_path, bbox)

**Code Evidence**:
```python
# Line 1776-1785: Update player with all features
self.gallery.update_player(
    player_id=player_id,
    features=features,  # General/body features
    body_features=features,  # Explicit body features
    jersey_features=jersey_features,
    foot_features=foot_features,
    reference_frame=reference_frame,
    jersey_number=jersey,
    team=team
)
```

---

### 6. Jersey Number and Team Handling

**Location**: `player_gallery_seeder.py` lines 1641-1642, 1736-1737, 1783-1784

**Status**: ✅ **CORRECTLY IMPLEMENTED**

**Implementation**:
- Retrieves jersey number from user input (`self.jersey_entry.get()`)
- Retrieves team from user input (`self.team_entry.get()`)
- Includes in anchor frame (`anchor_entry['jersey_number']`, `anchor_entry['team']`)
- Includes in gallery update (`jersey_number=jersey`, `team=team`)

**Code Evidence**:
```python
# Line 1641-1642: Get jersey and team from user input
jersey = self.jersey_entry.get().strip() or None
team = self.team_entry.get().strip() or None

# Line 1736-1737: Include in anchor frame
"jersey_number": jersey,
"team": team,

# Line 1783-1784: Include in gallery update
jersey_number=jersey,
team=team
```

---

### 7. Confidence Score System

**Location**: `player_gallery_seeder.py` lines 680, 698, 1740

**Status**: ✅ **CORRECTLY IMPLEMENTED**

**Implementation**:
- Anchor-protected players: **1.00 confidence** (line 680, 698)
- Anchor frames: **1.00 confidence** (line 1740)
- Gallery matches: Similarity score (0.0-1.0) from `match_player()`

**Code Evidence**:
```python
# Line 680: Anchor protection confidence
anchor_confidence = 1.00  # Anchor frames are ground truth

# Line 698: Anchor match confidence
self.detected_player_matches[bbox] = (anchor_player_id, anchor_player_name, 1.00)

# Line 1740: Anchor frame confidence
"confidence": 1.00  # Anchor frames are ground truth
```

---

### 8. Protection Window Duration

**Location**: `player_gallery_seeder.py` lines 523-526, 536-544

**Status**: ✅ **CORRECTLY IMPLEMENTED**

**Implementation**:
- Protection window: **±150 frames** from anchor
- Calculated per anchor frame: `protection_start = anchor_frame_num - 150`, `protection_end = anchor_frame_num + 150`
- Active for current frame if: `protection_start <= current_frame_num <= protection_end`

**Code Evidence**:
```python
# Line 523-526: Protection window calculation
ANCHOR_PROTECTION_WINDOW = 150
protection_start = max(0, anchor_frame_num - ANCHOR_PROTECTION_WINDOW)
protection_end = anchor_frame_num + ANCHOR_PROTECTION_WINDOW

# Line 540: Check if current frame is within protection window
if protection_start <= self.current_frame_num <= protection_end:
    # Player is protected
```

---

## Summary Checklist

| Rule | Status | Location |
|------|--------|----------|
| Anchor protection before gallery matching | ✅ | Lines 523-693 |
| Re-ID feature extraction (body, jersey, foot) | ✅ | Lines 609-630, 1652-1709 |
| Gallery matching with boosts | ✅ | Lines 710-714 (boosts in `player_gallery.py`) |
| Anchor frame creation (1.00 confidence) | ✅ | Lines 1733-1745 |
| Gallery update with all features | ✅ | Lines 1774-1785 |
| Jersey number and team handling | ✅ | Lines 1641-1642, 1736-1737, 1783-1784 |
| Confidence score system | ✅ | Lines 680, 698, 1740 |
| Protection window duration | ✅ | Lines 523-526, 536-544 |

---

## Conclusion

**All rules are correctly implemented in the Player Gallery Seeder.**

The seeder:
1. ✅ Checks anchor protection **BEFORE** gallery matching
2. ✅ Extracts **all feature types** (body, jersey, foot)
3. ✅ Uses **original bbox** for feature extraction (not expanded)
4. ✅ Creates anchor frames with **1.00 confidence**
5. ✅ Updates gallery with **all features** (body, jersey, foot)
6. ✅ Includes **jersey number and team** in anchor frames and gallery
7. ✅ Applies **protection window** of ±150 frames
8. ✅ Prevents **duplicate assignments** (one player per detection)

The seeder correctly applies all rules from the roadmap document (`TAGGING_ANCHORS_REID_ROADMAP.md`).


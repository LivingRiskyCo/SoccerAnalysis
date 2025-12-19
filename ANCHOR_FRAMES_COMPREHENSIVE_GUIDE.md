# Anchor Frames: Comprehensive System Integration Guide

## Overview

Anchor frames are **ground truth tags** (confidence: 1.00, similarity: 1.00) that flow through the entire tracking system. They are created when you tag players in the Setup Wizard and are used for:

1. **Player Gallery** - Reference frames with highest priority
2. **Re-ID Matching** - Feature extraction and similarity matching
3. **Track Routing** - Route corrections and predictions
4. **Metrics Evaluation** - Ground truth for HOTA, MOTA, IDF1
5. **Confidence Hierarchy** - Highest priority assignments (1.00 confidence)

---

## How Anchor Frames Are Created

### Manual Tagging
When you manually tag a player in Setup Wizard:
- Creates an anchor frame entry with `confidence: 1.00`
- Stores: `track_id`, `player_name`, `team`, `bbox`, `confidence`
- Saved to `PlayerTagsSeed-{video}.json` and `seed_config.json`

### Tag All Instances (NEW - Fixed)
**Previously**: Only created mappings, NOT anchor frames ❌  
**Now**: Creates anchor frames for ALL instances ✅

When you use "Tag All Instances" or "Tag All Instances (All Players)":
- Creates anchor frames for **every frame** where that track ID appears
- Each anchor frame has `confidence: 1.00` (ground truth)
- This dramatically increases ground truth data for:
  - Better Re-ID matching
  - More comprehensive metrics evaluation
  - More reference frames in player gallery

**Example**: If you tag "Yusuf" and he appears in 100 frames, you now get 100 anchor frames instead of just 1!

---

## Flow Through the System

### 1. Setup Wizard → Analysis

```
Setup Wizard (tagging)
    ↓
PlayerTagsSeed-{video}.json (saved with anchor_frames)
    ↓
combined_analysis_optimized.py (loads anchor frames)
    ↓
Applied during analysis with 1.00 confidence
```

### 2. Anchor Frame Application (Analysis)

**Location**: `combined_analysis_optimized.py` (lines ~5540-5774)

**Process**:
1. **Load anchor frames** from JSON files (strict video path matching)
2. **Match anchor frames to detections**:
   - Primary: Bbox position matching (IoU > 0.2, distance < 150px)
   - Fallback: Track ID matching
3. **Apply with 1.00 confidence**:
   ```python
   track_name_confidence[matched_track_id] = (anchor_player_name, 1.00, current_frame_num)
   ```
4. **Extract Re-ID features** from anchor frame detection
5. **Update Player Gallery** immediately with anchor frame features

### 3. Player Gallery Integration

**Location**: `player_gallery.py`

**Reference Frame Storage**:
- Anchor frames stored as `reference_frame` with:
  - `confidence: 1.00`
  - `similarity: 1.00`
  - `bbox`: Actual bounding box
  - `frame_num`: Frame number
  - `video_path`: Video file path

**Quality Pruning** (lines 591-629):
Reference frames are pruned by quality:
1. **Similarity score** (100x weight) - Anchor frames: 1.00 = 100 points
2. **Confidence** (50x weight) - Anchor frames: 1.00 = 50 points
3. **Recency** (1x weight)
4. **Has bbox** (5x weight)

**Result**: Anchor frames get **150+ points** and are **never pruned** (highest priority)

### 4. Re-ID Feature Extraction

**Location**: `combined_analysis_optimized.py` (lines ~5634-5763)

**Process**:
1. When anchor frame matches a detection:
   - Extract Re-ID features from the detection
   - Use original sharp frame (not net-filtered) for best quality
   - Create single-detection object for feature extraction
2. **Update gallery immediately**:
   ```python
   player_gallery.update_player(
       player_id=player_id,
       features=detection_feature.reshape(1, -1),  # Anchor frame features
       reference_frame={
           'frame_num': current_frame_num,
           'video_path': input_path,
           'bbox': anchor_bbox,
           'confidence': 1.00,  # Ground truth
           'similarity': 1.00    # Ground truth
       }
   )
   ```
3. **Future matching** uses these anchor frame features (not old gallery features)

### 5. Confidence Hierarchy

**Location**: `combined_analysis_optimized.py` (lines ~6386-6390)

**Priority Order**:
1. **Anchor Frames** (1.00 confidence) - **HIGHEST PRIORITY**
   - Protected from overwriting
   - Applied before gallery matching
   - Never changed by lower-confidence matches
2. **Gallery Matches** (0.48-1.00 confidence)
   - Based on Re-ID similarity
   - Can be updated if similarity improves
3. **Route Locked** (0.85+ confidence)
   - Stable track assignments
   - Preferred for future matches

**Protection Logic**:
```python
if confidence >= 1.00:
    # This is an anchor frame - protect it
    print(f"🔒 ANCHOR PROTECTED: Track #{track_id} = {existing_name} (anchor frame, skipping gallery match)")
    continue  # Skip gallery matching for this track
```

### 6. Route Corrections & Predictions

**Location**: `combined_analysis_optimized.py` (lines ~6176-6216)

**HOTA-Guided Tracking**:
- Uses anchor frames as ground truth for real-time HOTA calculation
- Suggests route corrections when tracking quality drops
- Adjusts Re-ID thresholds based on anchor frame matches

**Process**:
1. Calculate recent HOTA using anchor frames as ground truth
2. If HOTA drops, suggest Re-ID threshold adjustments
3. Use anchor frame matches to validate route corrections

### 7. Metrics Evaluation

**Location**: `tracking_metrics_evaluator.py`

**Ground Truth Loading**:
- Loads anchor frames from `PlayerTagsSeed-{video}.json`
- Converts to ground truth tracks format: `{track_id: [(frame, x1, y1, x2, y2), ...]}`
- Only evaluates frames that have anchor frames (prevents false positives)

**Metrics Calculated**:
- **HOTA**: Higher Order Tracking Accuracy
- **MOTA**: Multiple Object Tracking Accuracy
- **IDF1**: ID F1 Score (ID consistency)

**Important**: With "Tag All Instances" now creating anchor frames, you'll have **much more ground truth data** for accurate metrics!

---

## Key Benefits of Anchor Frames

### 1. Ground Truth for Metrics
- **Before**: Only 16 anchor frames → limited evaluation
- **After**: Hundreds/thousands of anchor frames → comprehensive evaluation

### 2. Better Re-ID Matching
- Anchor frames update gallery with **ground truth features**
- Future matching uses these high-quality features
- Improves cross-video recognition

### 3. Route Corrections
- Anchor frames provide **validation points** for tracking quality
- HOTA-guided tracking uses them to suggest corrections
- Improves overall tracking accuracy

### 4. Confidence Hierarchy
- Anchor frames (1.00) are **protected** from overwriting
- Highest priority in track assignments
- Ensures your manual tags are respected

### 5. Player Gallery Quality
- Anchor frames get **150+ quality points** (never pruned)
- Highest priority reference frames
- Used for best profile image selection

---

## Best Practices

### 1. Use "Tag All Instances" Liberally
- Tag all instances of players you're confident about
- Creates many anchor frames quickly
- Improves metrics and Re-ID matching

### 2. Tag Multiple Frames Per Player
- Different angles, lighting, poses
- More anchor frames = better Re-ID matching
- More comprehensive metrics evaluation

### 3. Verify Anchor Frames Are Created
- Check `PlayerTagsSeed-{video}.json` for `anchor_frames` entries
- Each entry should have `confidence: 1.00`
- Count should match your tagged instances

### 4. Monitor Metrics
- More anchor frames = more accurate metrics
- HOTA, MOTA, IDF1 will be more meaningful
- System will warn if < 50 anchor frames

---

## Technical Details

### Anchor Frame Format
```json
{
  "anchor_frames": {
    "1": [
      {
        "track_id": 11,
        "player_name": "Yusuf Cankara",
        "team": "Gray",
        "bbox": [100, 200, 150, 350],
        "confidence": 1.00
      }
    ],
    "2": [...]
  }
}
```

### Matching Logic
- **Primary**: Bbox position (IoU > 0.2, distance < 150px)
- **Fallback**: Track ID matching
- **Logging**: Logs match method for debugging

### Feature Extraction
- Uses **original sharp frame** (not net-filtered)
- Single-detection object for Re-ID extraction
- Updates gallery **immediately** (not deferred)

### Quality Scoring
- Similarity: 100x weight (anchor = 1.00 = 100 points)
- Confidence: 50x weight (anchor = 1.00 = 50 points)
- Recency: 1x weight
- Has bbox: 5x weight
- **Total**: 150+ points (highest priority)

---

## Summary

**Anchor frames are now fully integrated throughout the system:**

✅ Created by "Tag All Instances" (NEW)  
✅ Stored in Player Gallery with highest priority  
✅ Used for Re-ID feature extraction and matching  
✅ Applied with 1.00 confidence (protected)  
✅ Used for route corrections and predictions  
✅ Used as ground truth for metrics evaluation  
✅ Never pruned from gallery (highest quality)  

**The system now uses anchor frames comprehensively for all tracking operations!**


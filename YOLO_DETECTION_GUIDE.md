# YOLO Detection & Tracking Precision Guide

## What YOLO Looks For Between Frames

YOLO (You Only Look Once) is a deep learning object detection model that analyzes **entire frames** to detect objects. Here's what it's actually looking for:

### 1. **Visual Features (What YOLO Detects)**
- **Shape patterns**: Human body shapes, proportions, silhouettes
- **Texture patterns**: Jersey textures, uniform patterns, skin tones
- **Color patterns**: Team jersey colors, equipment colors
- **Spatial relationships**: Head-to-body ratio, limb positions
- **Context clues**: Player-like objects in sports field context

### 2. **How YOLO Works Between Frames**
YOLO does **NOT** track between frames - it detects independently on each frame:
- Each frame is analyzed **independently** (no memory of previous frames)
- YOLO outputs: bounding boxes, confidence scores, class IDs
- **Tracking** (connecting detections across frames) is handled by **OC-SORT/ByteTrack** tracker
- **Re-ID** (re-identification) uses appearance features to match players after occlusions

### 3. **Current System Architecture**
```
Frame → YOLO Detection → OC-SORT Tracker → Re-ID Matching → Player Gallery
```

## Current Detection Settings

Based on your code, YOLO is configured with:

1. **Confidence Threshold**: `track_thresh` (default: 0.25, adjustable in GUI)
   - Lower = more detections (more false positives)
   - Higher = fewer detections (more false negatives)

2. **Adaptive Confidence**: Automatically adjusts based on:
   - Frame brightness (darker = lower threshold)
   - Frame contrast (low contrast = higher threshold)
   - Scene conditions

3. **Resolution Processing**:
   - Full resolution for 4K videos (can be downscaled)
   - ROI cropping (field bounds) to focus detection area
   - Batch processing for GPU efficiency

4. **Class Filtering**: Only detects class `[0]` (person/player)

## How to Improve YOLO Precision

### 1. **Optimize Detection Threshold** ⭐ EASIEST
**Location**: GUI → Tracking Settings → "Detection Threshold"

**Recommendations**:
- **High-quality video, good lighting**: 0.20-0.30
- **Low-quality video, poor lighting**: 0.15-0.25
- **Too many false positives**: Increase to 0.30-0.40
- **Missing players**: Decrease to 0.15-0.20

**How to tune**:
1. Run analysis on a short clip (1-2 minutes)
2. Check if players are missed → lower threshold
3. Check if non-players detected → raise threshold
4. Find the sweet spot where all players detected, minimal false positives

### 2. **Use ROI (Region of Interest) Cropping** ⭐ HIGH IMPACT
**Location**: Setup Wizard → Field Bounds

**What it does**:
- Crops frame to field area before YOLO detection
- Removes stands, sidelines, background
- Focuses YOLO on relevant area

**How to improve**:
- **Tighten ROI bounds**: Only include field area (exclude sidelines, stands)
- **Update for different camera angles**: Re-run Setup Wizard if camera moves
- **Check ROI accuracy**: Use "Preview Field Bounds" in Setup Wizard

**Impact**: Can reduce false positives by 30-50%

### 3. **Adjust YOLO Resolution** ⭐ BALANCE SPEED/ACCURACY
**Location**: GUI → Tracking Settings → "YOLO Resolution"

**Options**:
- **Full**: Best accuracy, slowest (for 4K videos)
- **1080p**: Good balance (recommended for most videos)
- **720p**: Faster, slightly less accurate
- **480p**: Fastest, less accurate (not recommended)

**Recommendations**:
- **4K videos**: Use "1080p" (downscales automatically)
- **1080p videos**: Use "Full" or "1080p"
- **720p videos**: Use "Full"

**Why**: YOLO works best at ~640-1280px width. Too large = slower, too small = less accurate.

### 4. **Improve Video Quality** ⭐ FOUNDATION
**What helps YOLO**:
- **Higher resolution**: 1080p minimum (720p acceptable)
- **Stable camera**: Less motion blur
- **Good lighting**: Consistent brightness, avoid shadows
- **Frame rate**: 30fps+ (higher = smoother tracking)
- **Contrast**: Clear separation between players and background

**What hurts YOLO**:
- **Motion blur**: Fast camera movement
- **Low resolution**: <720p
- **Poor lighting**: Dark scenes, harsh shadows
- **Compression artifacts**: Low bitrate videos

### 5. **Use Anchor Frames** ⭐ HIGH PRECISION
**What it does**:
- Manually tag players in specific frames with 1.00 confidence
- System uses these as "ground truth" for tracking
- Helps correct tracking errors

**How to use**:
1. **Setup Wizard**: Tag players during initial setup
2. **Gallery Seeder**: Add anchor frames for key moments
3. **Conflict Resolution**: Add anchors when tracking fails

**Impact**: Can improve tracking accuracy by 20-40% in difficult scenes

### 6. **Optimize Tracking Parameters** ⭐ STABILITY
**Location**: GUI → Tracking Settings

**Key parameters**:
- **Min Track Length** (default: 3): Frames before track activates
  - Higher = more stable (prevents early ID switching)
  - Lower = faster activation (may cause ID switching)
  
- **Re-ID Similarity Threshold** (default: 0.5): How similar players must be to match
  - Higher = stricter matching (fewer false matches)
  - Lower = more lenient (more matches, may cause errors)
  
- **Track Buffer Time** (default: 8.0s): How long to keep lost tracks alive
  - Higher = less "blinking" (tracks stay alive longer)
  - Lower = faster recovery (tracks die faster)

**Recommendations**:
- **Stable tracking**: Increase Min Track Length to 5-7
- **Fast-moving players**: Increase Track Buffer to 10-12s
- **Many similar players**: Increase Re-ID threshold to 0.6-0.7

### 7. **Build Player Gallery** ⭐ CROSS-VIDEO ACCURACY
**What it does**:
- Stores appearance features for each player
- Matches players across videos
- Improves Re-ID accuracy

**How to build**:
1. Tag players in multiple videos
2. System learns appearance features automatically
3. More videos = better recognition

**Impact**: Dramatically improves cross-video player recognition

### 8. **Frame Processing Rate** ⭐ SPEED/ACCURACY BALANCE
**Location**: GUI → Tracking Settings → "Process Every Nth Frame"

**What it does**:
- Processes every Nth frame for detection
- Interpolates tracking between processed frames

**Recommendations**:
- **High FPS videos (60fps+)**: Process every 2-3 frames
- **Normal FPS (30fps)**: Process every frame (1)
- **Low FPS (<30fps)**: Process every frame (1)

**Trade-off**: 
- Higher skip = faster processing, less accurate
- Lower skip = slower processing, more accurate

## Advanced Techniques

### 9. **Multi-Scale Detection** (Not Currently Implemented)
**Concept**: Run YOLO at multiple resolutions and combine results
**Benefit**: Better detection of small/far players
**Cost**: 2-3x slower processing

### 10. **Test-Time Augmentation** (Not Currently Implemented)
**Concept**: Run YOLO on slightly transformed versions of frame (flipped, rotated)
**Benefit**: More robust to camera angle changes
**Cost**: 2-4x slower processing

### 11. **Temporal Smoothing** (Already Implemented)
**What it does**: Smooths player positions across frames
**Location**: GUI → "Temporal Smoothing" checkbox
**Impact**: Reduces jitter, smoother tracking

## Detection vs Tracking vs Re-ID

**Important distinction**:
- **YOLO Detection**: Finds players in each frame (independent)
- **OC-SORT Tracker**: Connects detections across frames (temporal)
- **Re-ID Matching**: Matches players by appearance (cross-video)

**To improve precision**:
1. **Detection issues** → Adjust YOLO threshold, ROI, resolution
2. **Tracking issues** → Adjust tracking parameters, anchor frames
3. **Re-ID issues** → Build player gallery, adjust Re-ID threshold

## Quick Diagnostic Checklist

**Problem: Missing players**
- [ ] Lower detection threshold (0.15-0.20)
- [ ] Check ROI bounds (too tight?)
- [ ] Increase YOLO resolution
- [ ] Check video quality/lighting

**Problem: False positives (detecting non-players)**
- [ ] Raise detection threshold (0.30-0.40)
- [ ] Tighten ROI bounds (exclude stands/sidelines)
- [ ] Use Setup Wizard to reject false positives

**Problem: ID switching (player IDs change)**
- [ ] Increase Min Track Length (5-7)
- [ ] Increase Re-ID Similarity Threshold (0.6-0.7)
- [ ] Add anchor frames at problem moments
- [ ] Increase Track Buffer Time (10-12s)

**Problem: Tracks "blinking" (appearing/disappearing)**
- [ ] Increase Track Buffer Time (10-12s)
- [ ] Lower detection threshold slightly
- [ ] Check for occlusions (players blocking each other)

## Best Practices Summary

1. **Start with defaults** → Test on short clip
2. **Tune detection threshold** → Find balance
3. **Set ROI bounds** → Focus on field area
4. **Use appropriate resolution** → 1080p for most cases
5. **Add anchor frames** → For difficult scenes
6. **Build player gallery** → For cross-video recognition
7. **Adjust tracking parameters** → Based on video characteristics
8. **Iterate** → Run analysis, check results, adjust, repeat

## Technical Details

### Current YOLO Model
- **Model**: YOLOv11 (Ultralytics)
- **Classes**: Person detection only (`classes=[0]`)
- **Batch Processing**: Yes (configurable batch size)
- **GPU Acceleration**: Yes (CUDA)

### Detection Pipeline
```
Frame → Resize (if needed) → ROI Crop → YOLO Detection → 
Filter by Confidence → OC-SORT Tracking → Re-ID Matching
```

### Adaptive Confidence Algorithm
- Analyzes frame brightness and contrast
- Adjusts threshold automatically:
  - Dark scenes: Lower threshold
  - Bright scenes: Higher threshold
  - Low contrast: Higher threshold

## Questions?

- **Detection not working?** → Check video quality, ROI bounds, threshold
- **Tracking unstable?** → Adjust tracking parameters, add anchor frames
- **Cross-video matching poor?** → Build player gallery, adjust Re-ID threshold


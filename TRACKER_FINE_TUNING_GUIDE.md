# Tracker and Occlusion Fine-Tuning Guide

This document outlines parameters that can be fine-tuned to improve capture and track consistency in the soccer analysis system.

## Current Configurable Parameters (GUI)

### 1. **Detection Threshold** (`track_thresh`)
- **Current Default**: 0.40
- **Range**: 0.1 - 0.5
- **Effect**: Lower = more detections (catches partially occluded players), Higher = fewer false positives
- **Recommendation**: 
  - 0.20-0.30 for crowded scenes or partial occlusions
  - 0.30-0.40 for normal play
  - 0.40-0.50 for clean, well-lit footage

### 2. **Match Threshold** (`match_thresh`)
- **Current Default**: 0.6
- **Range**: 0.5 - 1.0
- **Effect**: Higher = stricter matching (better ID consistency), Lower = more lenient (tracks reconnect easier)
- **Recommendation**:
  - 0.4-0.5 for high FPS (120fps) - more lenient for fast movement
  - 0.5-0.6 for medium FPS (30-60fps)
  - 0.6-0.7 for low FPS (<30fps)

### 3. **Track Buffer Time** (`track_buffer_seconds`)
- **Current Default**: 5.0 seconds
- **Range**: 1.0 - 15.0 seconds
- **Effect**: How long to keep lost tracks alive before deletion. Higher = less ID switching during occlusions
- **Recommendation**:
  - 3.0-5.0s for normal play
  - 5.0-8.0s for frequent occlusions
  - 8.0-10.0s for very crowded scenes

### 4. **Minimum Track Length** (`min_track_length`)
- **Current Default**: 5 frames
- **Range**: 3 - 10 frames
- **Effect**: Frames a track must persist before activation. Higher = more stable, less early ID switching
- **Recommendation**:
  - 3-5 frames for high FPS (120fps)
  - 5-7 frames for medium FPS (30-60fps)
  - 7-10 frames for low FPS (<30fps)

### 5. **Re-ID Similarity Threshold** (`reid_similarity_threshold`)
- **Current Default**: 0.55
- **Range**: 0.25 - 0.75
- **Effect**: Minimum cosine similarity for Re-ID matching. Higher = stricter (fewer false matches), Lower = more lenient (better reconnection)
- **Recommendation**:
  - 0.50-0.55 for normal play
  - 0.45-0.50 for frequent occlusions
  - 0.55-0.60 for very similar jerseys/uniforms

### 6. **Occlusion Recovery Time** (`occlusion_recovery_seconds`)
- **Current Default**: 3.0 seconds
- **Range**: 1.0 - 10.0 seconds
- **Effect**: How long to search for disappeared players before giving up. Scales with FPS automatically.
- **Recommendation**:
  - 2.0-3.0s for normal play
  - 3.0-5.0s for frequent occlusions
  - 5.0-8.0s for very crowded scenes
  - Higher = longer search = better recovery but more computation

### 7. **Occlusion Recovery Distance** (`occlusion_recovery_distance`)
- **Current Default**: 250 pixels
- **Range**: 100 - 500 pixels
- **Effect**: Maximum pixel distance for spatial recovery of disappeared players
- **Recommendation**:
  - 200-250px for normal play
  - 250-350px for frequent occlusions
  - 350-400px for very crowded scenes
  - Higher = search wider area = better recovery but more false positives

### 8. **Re-ID Check Interval** (`reid_check_interval`)
- **Current Default**: 30 frames
- **Range**: 10 - 60 frames
- **Effect**: How often to check Re-ID for tracks with existing assignments
- **Recommendation**:
  - 20-30 frames for normal play
  - 15-20 frames for frequent occlusions (more frequent checks)
  - 30-40 frames for high FPS (120fps)
  - Lower = more frequent checks = better reconnection but slower

### 9. **Re-ID Confidence Threshold** (`reid_confidence_threshold`)
- **Current Default**: 0.75
- **Range**: 0.60 - 0.90
- **Effect**: Skip Re-ID checks if track confidence above this threshold
- **Recommendation**:
  - 0.75-0.80 for normal play
  - 0.70-0.75 for frequent occlusions (check more tracks)
  - 0.80-0.85 for high-confidence scenarios
  - Lower = check more tracks = better but slower
  - Higher = skip more checks = faster but may miss some updates

## Hardcoded Parameters (Should Be Made Configurable)

### 5. **Gallery Check Interval** (`gallery_check_interval`)
- **Current**: 5 frames (~0.17s at 30fps, hardcoded)
- **Effect**: How often to check gallery for player identification
- **Recommendation**: Make configurable (3-10 frames)
  - Lower = more frequent = better identification but slower
  - Higher = less frequent = faster but may delay identification

### 6. **OC-SORT Max Age Multiplier**
- **Current**: `track_buffer_scaled * 3` (hardcoded)
- **Effect**: Maximum age of track before deletion in OC-SORT
- **Recommendation**: Make configurable (2x-5x buffer)
  - Higher = tracks live longer = better persistence but more memory
  - Lower = faster cleanup = less memory but may lose tracks

### 7. **Track Activation Threshold Minimum**
- **Current**: 0.20 (hardcoded minimum, uses `track_thresh` otherwise)
- **Effect**: Minimum confidence to start a new track
- **Recommendation**: Make configurable (0.15-0.25)
  - Lower = more tracks start = catches more players but more false positives
  - Higher = fewer tracks = cleaner but may miss some players

### 8. **Player Uniqueness Grace Frames** (`PLAYER_UNIQUENESS_GRACE_FRAMES`)
- **Current**: 3 frames (hardcoded)
- **Effect**: Allow player name on multiple tracks during transitions
- **Recommendation**: Make configurable (2-5 frames)
  - Higher = smoother transitions but more temporary duplicates
  - Lower = stricter uniqueness but may cause flickering

## New Parameters to Consider

### 1. **Occlusion Detection Sensitivity**
- Detect occlusions earlier/later
- Range: 0.1-0.5 (IoU threshold for occlusion detection)

### 2. **Velocity Prediction Weight**
- How much to trust motion prediction during occlusions
- Range: 0.0-1.0 (0 = no prediction, 1 = full prediction)

### 3. **Spatial Proximity Weight**
- Weight for spatial distance in track matching
- Range: 0.0-1.0 (higher = prioritize closer matches)

### 4. **Appearance Similarity Weight**
- Weight for appearance features in track matching (when Re-ID available)
- Range: 0.0-1.0 (higher = prioritize appearance over motion)

### 5. **Track Smoothing Window**
- Frames to use for position smoothing
- Range: 3-15 frames (higher = smoother but more lag)

## Recommended Fine-Tuning Strategy

### For Better Capture (More Detections):
1. Lower `track_thresh` to 0.20-0.30
2. Lower `min_track_length` to 3-5 frames
3. Increase `occlusion_recovery_seconds` to 4.0-6.0 seconds
4. Increase `occlusion_recovery_distance` to 300-350 pixels

### For Better Track Consistency (Less ID Switching):
1. Increase `match_thresh` to 0.65-0.70
2. Increase `track_buffer_seconds` to 6.0-8.0 seconds
3. Increase `min_track_length` to 7-10 frames
4. Lower `reid_similarity_threshold` to 0.50-0.52 (more lenient reconnection)
5. Decrease `reid_check_interval` to 15-20 frames (more frequent checks)
6. Lower `reid_confidence_threshold` to 0.70-0.72 (check more tracks)
7. Increase `OC-SORT max_age` multiplier to 4x-5x

### For Frequent Occlusions:
1. Increase `track_buffer_seconds` to 8.0-10.0 seconds
2. Increase `occlusion_recovery_seconds` to 5.0-8.0 seconds
3. Increase `occlusion_recovery_distance` to 300-400 pixels
4. Lower `match_thresh` to 0.50-0.55 (more lenient matching)
5. Decrease `reid_check_interval` to 10-15 frames
6. Lower `reid_confidence_threshold` to 0.70-0.72 (check more tracks)
7. Use OC-SORT tracker (better occlusion handling)

### For High FPS (120fps):
1. Lower `match_thresh` to 0.40-0.50
2. Lower `min_track_length` to 3-5 frames
3. `occlusion_recovery_seconds` scales automatically with FPS (e.g., 3.0s = 360 frames at 120fps)
4. Decrease `reid_check_interval` to 20-30 frames (more frequent at high FPS)

### For Low FPS (<30fps):
1. Increase `match_thresh` to 0.65-0.75
2. Increase `min_track_length` to 7-10 frames
3. Increase `track_buffer_seconds` to 6.0-8.0 seconds
4. Increase `reid_check_interval` to 10-15 frames (fewer frames available)

## Implementation Priority

**✅ COMPLETED** (Now Configurable):
1. ✅ `occlusion_recovery_seconds` - Now configurable in GUI (scales with FPS)
2. ✅ `occlusion_recovery_distance` - Now configurable in GUI
3. ✅ `reid_check_interval` - Now configurable in GUI
4. ✅ `reid_confidence_threshold` - Now configurable in GUI

**Medium Priority**:
5. Make `gallery_check_interval` configurable
6. Make OC-SORT `max_age` multiplier configurable
7. Make `track_activation_threshold` separate from `track_thresh`

**Low Priority** (Nice to Have):
8. Make `PLAYER_UNIQUENESS_GRACE_FRAMES` configurable
9. Add velocity prediction weight
10. Add spatial proximity weight


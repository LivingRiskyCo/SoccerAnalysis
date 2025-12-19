# Player Tracking Accuracy - Current Status & Priorities

## ✅ Already Implemented (High Accuracy Features)

### 1. **ROI Cropping** ✅
- Uses field calibration to crop frames before YOLO
- Reduces false detections from stands/background
- 2-3x speedup + better accuracy

### 2. **Adaptive Confidence Thresholds** ✅
- Adjusts detection confidence based on frame brightness/contrast
- Better detection in varying lighting conditions
- Reduces false negatives in dark/bright scenes

### 3. **Velocity Constraints** ✅
- Prevents impossible jumps (player teleporting)
- Validates movement against max velocity (10 m/s)
- More realistic trajectories

### 4. **Route Locking & Breadcrumbs** ✅
- Early-frame tags (first 1000 frames) are "locked" as correct paths
- User corrections stored as breadcrumbs
- Gallery track history provides guidance
- Combined boosts similarity scores by up to 0.25

### 5. **Global Player Constraint** ✅
- Prevents same player on multiple tracks simultaneously
- Detects conflicts and reports to GUI
- User can resolve conflicts manually

### 6. **Team Persistence** ✅
- Once a track is assigned to a team, it stays on that team
- Prevents Gray track from switching to Blue (and vice versa)

### 7. **Coach Exclusion** ✅
- Coaches (e.g., Kevin Hill) are excluded from team assignments
- Prevents coaches from being assigned to teams

---

## 🚧 High Priority (Next to Implement)

### 1. **Track Merging/Splitting** ⏳ IN PROGRESS
**Goal:** Automatically detect when two tracks are the same player and merge them

**Why it's critical:**
- Directly addresses duplicate IDs (e.g., Rocco on tracks #1, #6, #7)
- Reduces manual conflict resolution needed
- 30-50% reduction in duplicate IDs expected

**Implementation Plan:**
```python
def should_merge_tracks(track1_id, track2_id, track_state, player_names, reid_features):
    """
    Determine if two tracks should be merged.
    
    Criteria:
    1. Same player name assigned to both tracks
    2. Tracks are very close (< 50 pixels) in current frame
    3. High Re-ID similarity (> 0.8) between tracks
    4. Overlapping time periods (both active recently)
    5. Similar velocity/direction
    """
    # Check if same player name
    if track1_id not in player_names or track2_id not in player_names:
        return False
    
    name1 = player_names[str(track1_id)]
    name2 = player_names[str(track2_id)]
    if name1 != name2 or name1.startswith("#") or name2.startswith("#"):
        return False  # Not the same player or generic names
    
    # Check distance
    if track1_id in track_state and track2_id in track_state:
        pos1 = track_state[track1_id]['xyxy']
        pos2 = track_state[track2_id]['xyxy']
        center1 = ((pos1[0] + pos1[2])/2, (pos1[1] + pos1[3])/2)
        center2 = ((pos2[0] + pos2[2])/2, (pos2[1] + pos2[3])/2)
        distance = np.sqrt((center1[0] - center2[0])**2 + (center1[1] - center2[1])**2)
        if distance > 50:  # Too far apart
            return False
    
    # Check Re-ID similarity (if features available)
    # ... (compare Re-ID features)
    
    return True

def merge_tracks(keep_track_id, merge_track_id, player_names, track_state, ...):
    """
    Merge merge_track_id into keep_track_id.
    - Keep the longer/stronger track
    - Transfer player name, jersey, team assignments
    - Update all global mappings
    - Remove duplicate track
    """
    # Transfer assignments
    # Update mappings
    # Remove duplicate
```

**Status:** 🔄 Implementing now

---

### 2. **Track Interpolation for Players** 📋 PENDING
**Goal:** Fill gaps in player tracks during occlusions (ball already has this)

**Why it helps:**
- Smoother trajectories
- Reduces track fragmentation
- Better for movement analysis

**Implementation:**
- Extend ball interpolation logic to players
- Use velocity prediction for short gaps (< 5 frames)
- Use last known position for very short gaps (< 3 frames)

**Status:** 📋 Ready to implement after track merging

---

### 3. **Global Motion Compensation (GMC)** 📋 PENDING
**Goal:** Compensate for camera motion/shake to reduce false track losses

**Why it helps:**
- 10-20% reduction in track losses during camera movement
- Better tracking stability in handheld footage
- Especially useful for soccer videos with camera pan/zoom

**Implementation:**
- Check if OC-SORT supports `use_gmc=True` flag
- If not, implement custom GMC using homography transformation
- Apply to detections before tracking

**Status:** 📋 Medium priority

---

## 📊 Accuracy Metrics to Track

1. **Duplicate IDs:** Number of times same player appears on multiple tracks
2. **Track Losses:** Number of times a track disappears and reappears
3. **ID Switches:** Number of times a track ID changes for the same player
4. **False Positives:** Detections that aren't players
5. **False Negatives:** Players that aren't detected

---

## 🎯 Priority Order

1. ✅ **Track Merging/Splitting** - Highest impact on duplicate IDs
2. 📋 **Track Interpolation** - Improves trajectory smoothness
3. 📋 **GMC** - Reduces false track losses

---

## 📝 Notes

- All improvements should have GUI toggles for easy enable/disable
- Log improvements in console (e.g., "✓ Track merging: merged 3 duplicate tracks")
- Test with videos known to have duplicate IDs
- Monitor performance impact (should be minimal)

---

## 🚀 Future Enhancements (After Core Accuracy)

Once player tracking is highly accurate, we can add:
- **Event Tagging:** Goals, passes, shots, fouls
- **Speed Measurements:** Player velocity, acceleration
- **Heatmaps:** Position heatmaps, movement patterns
- **Advanced Analytics:** Possession, passing networks, etc.




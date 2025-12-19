# ByteTrack Parameter Guide

## Understanding the Three Key Parameters

### 1. `track-thresh` (track_activation_threshold)
**What it does:** Minimum confidence score a YOLO detection needs to be considered for tracking

**Lower value (e.g., 0.20):**
- ✅ More detections are considered (including lower confidence ones)
- ✅ Can catch partially occluded players
- ⚠️ **MORE new IDs created** (because more detections = more potential new tracks)
- ⚠️ More false positives (low confidence detections might be noise)

**Higher value (e.g., 0.40):**
- ✅ Fewer false positives (only high confidence detections)
- ✅ More stable tracks (only confident detections)
- ⚠️ **FEWER new IDs** (fewer detections overall)
- ⚠️ May miss partially occluded players

**Example:**
- `track-thresh = 0.20`: YOLO detects a player with 0.25 confidence → ✅ Tracked (creates new ID or updates existing)
- `track-thresh = 0.40`: YOLO detects a player with 0.25 confidence → ❌ Ignored (too low confidence)

---

### 2. `match-thresh` (minimum_matching_threshold)
**What it does:** How much a detection must overlap with an existing track to be considered a "match" (IoU threshold)

**Lower value (e.g., 0.6):**
- ✅ **EASIER to connect to existing items** (more lenient matching)
- ✅ Fewer new IDs (detections more likely to match existing tracks)
- ✅ Better for fast movement (players move more between frames)
- ⚠️ May cause ID switches (wrong detection matched to wrong track)

**Higher value (e.g., 0.8):**
- ✅ **HARDER to connect to existing items** (stricter matching)
- ✅ Better ID consistency (less likely to switch IDs)
- ⚠️ More new IDs created (detections don't match existing tracks)
- ⚠️ May lose tracking during fast movement or occlusion

**Example:**
- `match-thresh = 0.6`: Detection overlaps 65% with existing track → ✅ Matched (updates existing ID)
- `match-thresh = 0.8`: Detection overlaps 65% with existing track → ❌ Not matched (creates new ID)

---

### 3. `track-buffer` (lost_track_buffer)
**What it does:** How many frames a "lost" track is kept in memory before being deleted

**Higher value (e.g., 100 frames):**
- ✅ **Keeps trying to reconnect longer**
- ✅ Better for occlusions (player hidden behind another player)
- ✅ Better for fast movement (player moves out of frame briefly)
- ✅ More persistent tracking (ID survives longer)
- ⚠️ Uses more memory

**Lower value (e.g., 30 frames):**
- ✅ Uses less memory
- ⚠️ **Gives up reconnecting sooner**
- ⚠️ May lose tracking during brief occlusions
- ⚠️ Creates new IDs more often (old track deleted, new one created)

**Example at 120fps:**
- `track-buffer = 30`: Player disappears → Track kept for 30 frames (0.25 seconds) → If not found, deleted
- `track-buffer = 120`: Player disappears → Track kept for 120 frames (1.0 second) → If not found, deleted

---

## Recommended Settings

### For High FPS Videos (120fps):
- `track-thresh = 0.20-0.25`: Lower to catch all players
- `match-thresh = 0.6-0.7`: Lower for fast movement (players move less per frame)
- `track-buffer = 100-150`: Higher to maintain tracking through occlusions

### For Standard FPS Videos (30-60fps):
- `track-thresh = 0.25-0.30`: Moderate
- `match-thresh = 0.7-0.8`: Moderate to strict
- `track-buffer = 50-80`: Moderate

### For Slow Movement / Stable Tracking:
- `track-thresh = 0.30-0.35`: Higher to reduce false positives
- `match-thresh = 0.8-0.9`: Stricter for better ID consistency
- `track-buffer = 30-50`: Lower (less needed)

---

## Quick Reference

| Parameter | Lower Value | Higher Value |
|-----------|-------------|--------------|
| **track-thresh** | More detections, **More new IDs** | Fewer detections, Fewer new IDs |
| **match-thresh** | **Easier to connect**, Fewer new IDs | Harder to connect, **More new IDs** |
| **track-buffer** | **Gives up sooner**, More new IDs | **Keeps trying longer**, Fewer new IDs |

---

## Common Issues & Solutions

**Problem:** Too many new IDs (rapid ID switching)
- **Solution:** Increase `match-thresh` (0.7 → 0.8) OR increase `track-buffer` (30 → 100)

**Problem:** Losing tracking during fast movement
- **Solution:** Decrease `match-thresh` (0.8 → 0.6) AND increase `track-buffer` (30 → 100)

**Problem:** Missing partially occluded players
- **Solution:** Decrease `track-thresh` (0.30 → 0.20)

**Problem:** Too many false positives
- **Solution:** Increase `track-thresh` (0.20 → 0.30)


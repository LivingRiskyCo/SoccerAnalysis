# When Does the Tracker Create New Tracks?

## Overview

The tracking system (ByteTrack/OC-SORT) creates **new tracks** when a detection cannot be matched to any existing track. Here's what triggers new track creation:

## Main Reasons for New Track Creation

### 1. **Detection Cannot Be Matched to Existing Tracks**
   - **Matching Threshold**: The tracker uses `match_thresh` (default 0.6) to determine if a detection matches an existing track
   - **IoU (Intersection over Union)**: The tracker calculates how much a detection overlaps with a predicted track position
   - **If IoU < match_thresh**: The detection is too far from all existing tracks → **NEW TRACK CREATED**

### 2. **Track Has Been "Lost" Too Long**
   - **Track Buffer**: Tracks are kept alive for `track_buffer_seconds` (default 5.0 seconds)
   - **Lost Track Buffer**: When a track disappears, it's kept in a "lost" state for this duration
   - **After Buffer Expires**: If a track hasn't been seen for longer than the buffer time → **TRACK IS DELETED**
   - **Reappearance**: If the player reappears after the buffer expires → **NEW TRACK CREATED** (old track is gone)

### 3. **Detection Appears Far From All Existing Tracks**
   - **Spatial Distance**: If a detection's position is too far from where any existing track is predicted to be
   - **Motion Prediction**: The tracker uses Kalman filtering to predict where tracks should be
   - **If detection is outside predicted area**: → **NEW TRACK CREATED**

### 4. **New Player Enters the Field**
   - **First Appearance**: When a player enters the field for the first time
   - **No existing track matches**: → **NEW TRACK CREATED**

## Key Parameters That Control Track Creation

### `match_thresh` (Matching Threshold)
- **Default**: 0.6
- **Lower** (e.g., 0.4) = More lenient matching = **FEWER new tracks** (easier to reconnect)
- **Higher** (e.g., 0.8) = Stricter matching = **MORE new tracks** (harder to reconnect)

### `track_buffer_seconds` (Lost Track Buffer)
- **Default**: 5.0 seconds
- **Longer** (e.g., 10.0s) = Tracks stay alive longer = **FEWER new tracks** (more time to reconnect)
- **Shorter** (e.g., 2.0s) = Tracks expire faster = **MORE new tracks** (less time to reconnect)

### `min_track_length` (Minimum Track Length)
- **Default**: 5 frames
- **Higher** (e.g., 10) = New tracks must persist longer = **FEWER spurious tracks**
- **Lower** (e.g., 3) = New tracks can be shorter = **MORE tracks** (including false positives)

## Common Scenarios

### Scenario 1: Player Occlusion
- **What happens**: Player goes behind another player or object
- **Result**: Track is "lost" and enters lost buffer
- **If reconnects within buffer**: Same track ID maintained
- **If buffer expires**: New track ID created when player reappears

### Scenario 2: Fast Movement
- **What happens**: Player moves very quickly between frames
- **Result**: Detection might be too far from predicted position
- **If IoU < match_thresh**: New track created (even though it's the same player)

### Scenario 3: Detection Confidence Drops
- **What happens**: YOLO confidence drops below threshold temporarily
- **Result**: Detection might be filtered out, track goes to lost buffer
- **If reconnects**: Same track ID (if within buffer)
- **If doesn't reconnect**: New track when player reappears

## How to Reduce New Track Creation

1. **Increase `track_buffer_seconds`**: 
   - Longer buffer = more time to reconnect = fewer new tracks
   - **Recommended**: 8.0-10.0 seconds for fast-moving players

2. **Lower `match_thresh`**:
   - More lenient matching = easier to reconnect = fewer new tracks
   - **Warning**: Too low (e.g., 0.3) can cause incorrect matches

3. **Use Re-ID System**:
   - Re-ID can reconnect tracks even after long occlusions
   - Uses appearance features, not just position

4. **Use Appearance-Based Trackers**:
   - `deepocsort`, `strongsort`, `botsort` use appearance features
   - Better at reconnecting after occlusions

## Current Settings in Your System

Based on the code:
- **Track Buffer**: 5.0 seconds (scales with FPS)
- **Matching Threshold**: 0.6 (adjustable via GUI)
- **Min Track Length**: 5 frames (adjustable via GUI)
- **Tracker Type**: ByteTrack or OC-SORT (user selectable)

## Why You Might See New Tracks

1. **Players moving very fast** → Detection too far from predicted position
2. **Long occlusions** → Track buffer expires before reconnection
3. **Multiple players close together** → Tracker gets confused, creates new tracks
4. **Detection confidence drops** → Track temporarily lost, new track when reappears
5. **Field boundary filtering** → Player temporarily filtered, new track when reappears

## Solution: Use Re-ID for Reconnection

The Re-ID system can reconnect tracks even when the tracker creates new track IDs:
- **Re-ID matches by appearance** (not just position)
- **Can reconnect across long occlusions**
- **Works even if tracker creates new track ID**

This is why anchor frame protection and high-confidence history tracking are important - they maintain player identity even when track IDs change!


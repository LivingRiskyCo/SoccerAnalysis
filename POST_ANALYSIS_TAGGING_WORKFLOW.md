# Post-Analysis Player Tagging Workflow

## Overview

**This workflow separates analysis from player tagging**, which provides:
- ✅ **Clean tracking data** - No false matches polluting your gallery
- ✅ **Better track IDs** - Consolidated, stable track IDs after analysis
- ✅ **Full context** - Tag players with complete movement history visible
- ✅ **Quality control** - Review before committing to gallery
- ✅ **Faster analysis** - No Re-ID matching overhead during analysis

## Recommended Workflow

### Step 1: Run Analysis WITHOUT Player Matching

**Goal**: Get clean tracking data with stable track IDs

1. **Open Soccer Analysis GUI**
2. **Disable Player Gallery Matching**:
   - Go to **Tracking** tab
   - **Uncheck** "Use Player Gallery" or set "Use Re-ID" to False
   - This runs pure tracking without player name matching

3. **Run Analysis**:
   - Select your video
   - Click "Start Analysis"
   - Analysis will:
     - Detect players
     - Track them with IDs
     - Generate CSV with track IDs
     - **NO player name matching** (faster, cleaner)

4. **Output**: 
   - `video_analyzed_tracking_data.csv` with track IDs (1, 2, 3, etc.)
   - No player names assigned yet

---

### Step 2: Consolidate Track IDs (Optional but Recommended)

**Goal**: Merge duplicate track IDs that represent the same player

1. **Run Consolidation Tool**:
   ```bash
   python consolidate_player_ids.py
   ```

2. **Load your CSV**:
   - Select `video_analyzed_tracking_data.csv`
   - Tool will analyze track sequences
   - Find duplicate IDs (same player, different IDs)

3. **Review Suggested Merges**:
   - Tool shows potential merges based on:
     - Position continuity
     - Time gaps
     - Movement patterns

4. **Apply Consolidation**:
   - Review and approve merges
   - Tool creates `video_analyzed_tracking_data_consolidated.csv`
   - **Stable track IDs** ready for tagging

---

### Step 3: Tag Players Using Track Review Assigner

**Goal**: Assign player names to track IDs with full context

1. **Open Track Review & Assigner**:
   - From GUI: Tools → Track Review & Player Assignment
   - Or run: `python track_review_assigner.py`

2. **Load Files**:
   - **CSV**: Load `video_analyzed_tracking_data_consolidated.csv`
   - **Video**: Load original video file

3. **Review Tracks**:
   - Left panel: List of all track IDs
   - Click a track ID to see:
     - Track info (frames, duration, positions)
     - Video viewer showing player on that track
     - Navigate through frames where track appears

4. **Assign Player Names**:
   - Right panel: Player assignment
   - Select track ID from list
   - Enter player name (or select from gallery)
   - Add jersey number and team
   - Click "Assign Player to Track"

5. **Review Multiple Frames**:
   - Use frame navigation to see player at different times
   - Verify it's the same player throughout track
   - Tag with confidence

6. **Save Assignments**:
   - Assignments saved to `track_assignments.json`
   - Can export to anchor frames for future analysis

---

### Step 4: Build Player Gallery from Verified Matches

**Goal**: Create high-quality gallery from verified track assignments

1. **Export to Anchor Frames**:
   - In Track Review Assigner
   - Click "Export to Anchor Frames"
   - Creates `PlayerTagsSeed-video.json` with verified tags

2. **Or Use Player Gallery Seeder**:
   - Open Player Gallery Seeder
   - Load video and CSV
   - For each verified track:
     - Navigate to frames where track appears
     - Click on player
     - Add to gallery with verified name
   - Gallery now has high-quality references

3. **Verify Gallery**:
   - Check Player Gallery in GUI
   - Each player should have:
     - Multiple reference frames
     - Different angles/poses
     - Verified names (not guesses)

---

### Step 5: Re-run Analysis WITH Gallery (Optional)

**Goal**: Use verified gallery for future analyses

1. **Enable Player Gallery**:
   - Go to Tracking tab
   - **Check** "Use Player Gallery"
   - Enable Re-ID matching

2. **Run Analysis on New Video**:
   - System will use verified gallery
   - Should have much better accuracy
   - Fewer false matches

---

## Alternative: Tag in Playback Viewer

If you prefer to tag directly in the playback viewer:

1. **Load Video & CSV in Playback Viewer**:
   - Open Playback Viewer
   - Load original video
   - Load consolidated CSV

2. **Navigate and Tag**:
   - Play through video
   - See all tracks with IDs
   - When you see a player you recognize:
     - Note the track ID
     - Use Track Review Assigner to assign name
     - Or use Player Gallery Seeder to add to gallery

3. **Benefits**:
   - See full context (all players, ball, movement)
   - Better spatial awareness
   - Can tag multiple players in same frame

---

## Workflow Comparison

### ❌ OLD Workflow (Tagging During Analysis)
- Analysis tries to match players in real-time
- False matches pollute gallery
- No context when tagging
- Rushed decisions
- Gallery becomes "garbage"

### ✅ NEW Workflow (Post-Analysis Tagging)
- Analysis just tracks (fast, clean)
- Consolidate track IDs
- Tag with full context (see movement, behavior)
- Verify before committing
- Clean, verified gallery

---

## Tips

1. **Start with Consolidation**: Always consolidate track IDs first - it makes tagging much easier

2. **Tag High-Quality Tracks**: Focus on tracks with:
   - Many frames (long duration)
   - Clear visibility
   - Stable movement

3. **Use Track Info**: In Track Review Assigner, check:
   - Frame count (more = better)
   - Position range (shows movement)
   - Time span (shows duration)

4. **Tag Multiple Frames**: For each player, tag them in:
   - Different poses
   - Different angles
   - Different game situations

5. **Verify Before Gallery**: Don't add to gallery until you're confident it's correct

6. **Batch Process**: Tag all players for one video, then move to next

---

## Tools Reference

- **`consolidate_player_ids.py`**: Merge duplicate track IDs
- **`track_review_assigner.py`**: Review tracks and assign player names
- **`player_gallery_seeder.py`**: Build gallery from verified matches
- **Playback Viewer**: Review tracking data with full context

---

## Next Steps

1. Try this workflow on one video
2. Compare results to old workflow
3. Build verified gallery
4. Use gallery for future analyses

This workflow should significantly improve your player recognition accuracy and prevent gallery pollution!


# Track-to-Anchor Workflow Guide

## Problem
You've tagged players at the **track level** in Track Review, but need to:
1. Convert those track assignments to anchor frames for the correct video (part3, not part5)
2. Use those anchor frames for Re-ID learning in the next analysis run
3. Combine track-level tagging with Re-ID feature extraction

## Solution: Complete Workflow

### Step 1: Export Track Assignments as Anchor Frames

**In Track Review & Player Assignment tool:**

1. **After tagging all players**, click **"Set Tags as Anchor Frames"** (or "Export to JSON")
2. **Important**: When saving, make sure the filename matches your video:
   - If analyzing `part003.mp4`, save as: `PlayerTagsSeed_part003.json`
   - The tool will now auto-suggest the correct filename based on your video
3. **Save in the same directory as your video** (this is where analysis looks for it)

**What this creates:**
- Anchor frame file with all your track assignments
- Each frame where a tagged track appears gets an anchor point
- Includes: player_name, track_id, bbox, confidence=1.00

### Step 2: Verify Anchor File Location

**Check that:**
- File is named: `PlayerTagsSeed_[video_name].json`
- File is in the same directory as your video
- File contains `anchor_frames` structure (not just `player_mappings`)

### Step 3: Re-run Analysis with Re-ID Enabled

**In Soccer Analysis GUI:**

1. **Enable Re-ID**:
   - Tracking tab → Check "Re-ID (Re-identification)"
   - Check "Use Player Gallery"
   - Select Re-ID-enabled tracker (e.g., `deepocsort`)

2. **Run Analysis** on the same video (part003):
   - Analysis will automatically find `PlayerTagsSeed_part003.json`
   - Uses anchor frames as ground truth
   - Extracts Re-ID features (body, jersey, foot) from tagged players
   - Builds/updates player gallery with proper features

3. **Result**:
   - Player gallery now has Re-ID features for all tagged players
   - Future analyses will automatically recognize these players
   - Cross-video recognition enabled

## Why This Works

### Track-Level Tagging → Anchor Frames
- **Track Review** assigns player names to entire tracks (all frames)
- **Export to Anchor Frames** converts track assignments to frame-level anchors
- Each frame where a track appears gets an anchor point
- This provides ground truth for Re-ID learning

### Anchor Frames → Re-ID Learning
- Analysis uses anchor frames to know "this bbox at this frame = this player"
- Re-ID extracts features from those bboxes
- Features are stored in player gallery
- Gallery learns: "these features = this player name"

### Combined Benefits
- **Track-level tagging** is faster (tag once per track, not per frame)
- **Anchor frames** provide ground truth for learning
- **Re-ID** learns player appearances automatically
- **Gallery** enables cross-video recognition

## File Naming Convention

**Critical**: Anchor files must match video names for automatic detection:

- Video: `part003.mp4` → Anchor: `PlayerTagsSeed_part003.json`
- Video: `practice_11_18.mp4` → Anchor: `PlayerTagsSeed_practice_11_18.json`
- Video: `20251125_194132.mp4` → Anchor: `PlayerTagsSeed_20251125_194132.json`

**Analysis looks for:**
1. Exact match: `PlayerTagsSeed_[video_basename].json`
2. Pattern match: `PlayerTagsSeed*.json` in same directory
3. Falls back to any `PlayerTagsSeed*.json` if exact match not found

## Troubleshooting

### "File doesn't contain player_mappings"
- This means the file format is wrong
- Make sure you exported from Track Review using "Set Tags as Anchor Frames"
- File should have `anchor_frames` structure, not `player_mappings`

### Wrong video's anchor file being used
- Check filename matches your video exactly
- Make sure anchor file is in same directory as video
- Delete or rename other `PlayerTagsSeed*.json` files if needed

### Re-ID not learning
- Make sure Re-ID is enabled in GUI
- Check that anchor frames have valid bboxes
- Verify player gallery is being updated (check Player Management)

## Quick Checklist

- [ ] Tagged all players in Track Review
- [ ] Exported as anchor frames with correct video name
- [ ] Anchor file is in same directory as video
- [ ] Re-enabled Re-ID in analysis GUI
- [ ] Re-run analysis on same video
- [ ] Verify gallery has Re-ID features (Player Management)
- [ ] Test on new video to see cross-video recognition


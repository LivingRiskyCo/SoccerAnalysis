# Penalty Shot Analysis - Player Tuning Guide

## Target Players
- **Rocco Piazza** - Shooting penalty shot
- **Cameron Hill** - Goalkeeper
- **Ellie Hill** - Also in video
- **James Carlson** - Appears briefly

## Quick Start Workflow

### Step 1: Tag Players in Key Frames

Use the **Player Gallery Seeder** to tag these players in clear frames:

```bash
python player_gallery_seeder.py
```

**Recommended frames to tag:**
1. **Rocco Piazza** - Tag during penalty shot setup (clear view of jersey/uniform)
2. **Cameron Hill** - Tag in goalkeeper position (distinctive goalkeeper gear)
3. **Ellie Hill** - Tag when clearly visible (avoid occlusions)
4. **James Carlson** - Tag during his brief appearance (may need to pause/scrub carefully)

**Tips:**
- Tag each player in 3-5 different frames for better recognition
- Choose frames with good lighting and clear visibility
- Make sure the bounding box includes the full body and jersey
- Tag from different angles if possible

### Step 2: Optimize Tracking Parameters

Open the main GUI and adjust these settings in the **Tracking** tab:

```bash
python soccer_analysis_gui.py
```

#### Recommended Settings for Penalty Shot Analysis:

**Detection Settings:**
- **Confidence Threshold**: 0.25-0.30 (lower to catch all players, including brief appearances)
- **IOU Threshold**: 0.45-0.50 (standard)

**Tracking Settings:**
- **Track Threshold**: 0.30-0.35 (lower for better detection of all players)
- **Match Threshold**: 0.55-0.60 (moderate - allows reconnection after brief disappearances)
- **Track Buffer**: 6.0-8.0 seconds (longer to handle brief disappearances like James Carlson)
- **Minimum Track Length**: 3-5 frames (lower to catch brief appearances)

**Re-ID Settings:**
- **Re-ID Similarity Threshold**: 0.50-0.55 (moderate - good balance)
- **Re-ID Check Interval**: 20-25 frames (more frequent checks for better reconnection)
- **Re-ID Confidence Threshold**: 0.70-0.75 (check more tracks)

**Gallery Matching:**
- **Gallery Similarity Threshold**: 0.35-0.40 (slightly lower for better matching)

### Step 3: Run Analysis with Learning Enabled

In the **Analysis** tab:
1. ✅ Check **"Learn Player Features"** (enables gallery learning)
2. ✅ Check **"Track Players"**
3. ✅ Check **"Export CSV"**
4. Load your video
5. Click **"Start Analysis"**

### Step 4: Review and Correct with Interactive Learning

After analysis, use **Interactive Player Learning** to quickly identify any missed players:

```bash
# From the GUI, click: "🎓 Interactive Player Learning"
# Or run directly:
python interactive_player_learning.py
```

This tool will:
- Show you unknown/unassigned tracks
- Let you identify them quickly
- Automatically propagate assignments across all frames

### Step 5: Post-Process with Track Review Assigner

For fine-tuning assignments:

```bash
python track_review_assigner.py
```

**Workflow:**
1. Load your analysis CSV
2. Load the video
3. Review tracks one by one
4. Assign player names to track IDs
5. Export assignments to anchor frames

## Specific Tuning for Each Player

### Rocco Piazza (Penalty Shooter)
- **Key Challenge**: May be partially occluded during shot
- **Solution**: 
  - Tag multiple frames: setup, approach, follow-through
  - Lower detection threshold (0.25-0.30)
  - Longer track buffer (7-8 seconds)

### Cameron Hill (Goalkeeper)
- **Key Challenge**: Distinctive position but may be stationary
- **Solution**:
  - Tag in goalkeeper position (distinctive gear helps)
  - Standard detection threshold (0.30-0.35)
  - Gallery matching should work well (distinctive appearance)

### Ellie Hill
- **Key Challenge**: May be similar to other players
- **Solution**:
  - Tag in multiple frames with different poses
  - Use gallery matching (similarity threshold 0.35-0.40)
  - Tag frames where she's clearly visible and distinct

### James Carlson (Brief Appearance)
- **Key Challenge**: Very brief appearance
- **Solution**:
  - **Lower detection threshold** (0.25-0.28) - critical!
  - **Shorter minimum track length** (3 frames)
  - **Longer track buffer** (8-10 seconds)
  - Tag immediately when he appears
  - May need to manually scrub through video frame-by-frame

## Advanced: Anchor Frames

After tagging, convert to anchor frames for automatic recognition:

1. **Convert Tracks to Anchor Frames** (from GUI):
   - Click "Convert Tracks → Anchor Frames"
   - Use 30-50 frame interval
   - Max 500 frames

2. **Or use Track Review Assigner**:
   - Assign players to tracks
   - Export as anchor frames
   - These will be auto-loaded in future analyses

## Troubleshooting

### Players Not Being Detected
- Lower **Confidence Threshold** (0.20-0.25)
- Lower **Track Threshold** (0.25-0.30)
- Check video quality/lighting

### Players Getting Wrong IDs
- Increase **Match Threshold** (0.60-0.65)
- Increase **Re-ID Similarity Threshold** (0.55-0.60)
- Add more reference frames to gallery

### Brief Appearances Missed (James Carlson)
- Lower **Minimum Track Length** (3 frames)
- Increase **Track Buffer** (8-10 seconds)
- Lower **Detection Threshold** (0.25)
- Manually tag in Track Review Assigner

### Gallery Not Matching
- Lower **Gallery Similarity Threshold** (0.35-0.40)
- Add more reference frames per player (5-10 frames)
- Tag frames with different angles/poses
- Check that players are tagged correctly in gallery

## Verification Checklist

After tuning, verify:
- [ ] Rocco is detected during penalty shot
- [ ] Cameron Hill is identified as goalkeeper
- [ ] Ellie Hill is recognized when visible
- [ ] James Carlson is detected during brief appearance
- [ ] Player names appear correctly in output video
- [ ] CSV exports have correct player assignments

## Next Steps

1. Run analysis with tuned parameters
2. Review output video for accuracy
3. Use Interactive Learning to fix any missed assignments
4. Export anchor frames for future videos
5. Save settings as a preset if this is a recurring scenario


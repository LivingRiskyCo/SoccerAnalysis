# Batch Anchor Frame Workflow Tools

## Overview

Two tools to help you efficiently create anchor frames:

1. **`anchor_frame_helper.py`** - Command-line analysis tool
2. **`batch_anchor_frame_workflow.py`** - GUI workflow planner

## Tool 1: Anchor Frame Helper (Command Line)

### Usage

```bash
# Analyze a specific video
python anchor_frame_helper.py --video "path/to/video.mp4"

# Get frame suggestions for a video
python anchor_frame_helper.py --suggest "path/to/video.mp4"

# Check all videos in a directory
python anchor_frame_helper.py --check-dir "path/to/videos"
```

### What It Does

- ✅ Analyzes existing anchor frames
- ✅ Suggests which frames to tag
- ✅ Shows video statistics (frames, duration, FPS)
- ✅ Provides recommendations

### Example Output

```
============================================================
ANCHOR FRAME ANALYSIS: 20251104_190201.mp4
============================================================
Current anchor frames: 0 tags in 0 frames

RECOMMENDATIONS:
  1. Use Setup Wizard to tag 5-10 key players
  2. Tag at frames: 0, middle, and end of video
  3. Tag players from both teams
  4. Focus on most visible/important players first
```

## Tool 2: Batch Anchor Frame Workflow (GUI)

### Usage

```bash
python batch_anchor_frame_workflow.py
```

### Features

1. **Video Selection**: Browse and select your video
2. **Frame Strategy**: Choose from:
   - Suggested frames (beginning, middle, end)
   - Custom frame numbers
   - Evenly spaced frames
3. **Target Players**: Optionally specify which players to focus on
4. **Workflow Plan**: Generates step-by-step plan
5. **Export**: Save plan to text file

### Workflow

1. **Select Video**: Click "Browse..." to choose your video
2. **Choose Strategy**: 
   - Select frame selection method
   - Enter number of frames (for suggested/spaced)
   - OR enter custom frame numbers (comma-separated)
3. **Optional**: Enter target player names (one per line)
4. **Generate Plan**: Click "Generate Workflow Plan"
5. **Review**: Check the generated plan in the text area
6. **Export** (optional): Save plan to file
7. **Execute**: Follow the plan using Setup Wizard or Gallery Seeder

### Example Plan Output

```
BATCH ANCHOR FRAME WORKFLOW PLAN
======================================================================

Video: 20251104_190201.mp4
Total frames: 14918
Duration: 621.6 seconds (10.4 minutes)
FPS: 24.0

Target frames: 10 frames
Target players: All visible players

----------------------------------------------------------------------
STEP-BY-STEP WORKFLOW:
----------------------------------------------------------------------

1. Open Setup Wizard or Gallery Seeder
   - Main GUI -> 'Setup Wizard' (recommended)
   - OR Main GUI -> 'Tag Players (Gallery)'

2. Load your video:
   C:\Users\nerdw\Videos\Practice-11-4-2025-Tripod-Test\20251104_190201.mp4

3. Tag players at the following frames:

   Frame 1/10: Frame #1491 (1m 2s)
      - Navigate to frame 1491
      - Tag 3-5 players at this frame
      - Each tag = 1 anchor frame

   Frame 2/10: Frame #2982 (2m 4s)
      - Navigate to frame 2982
      - Tag 3-5 players at this frame
      - Each tag = 1 anchor frame

   ... (continues for all frames)

----------------------------------------------------------------------
TIPS:
----------------------------------------------------------------------
• Tag the same players across multiple frames for best results
• Focus on key players (goalkeepers, star players, etc.)
• Tag players from both teams
• Use clear frames where players are fully visible
• Don't worry about tagging every single frame

----------------------------------------------------------------------
ESTIMATED TIME:
----------------------------------------------------------------------
~300 seconds (5.0 minutes) for 10 frames
Assuming ~30 seconds per frame (tagging 3-5 players)
```

## Quick Start Guide

### For First-Time Setup

1. **Run Helper Script**:
   ```bash
   python anchor_frame_helper.py --suggest "your_video.mp4"
   ```
   This shows you which frames to tag.

2. **Open Batch Workflow GUI**:
   ```bash
   python batch_anchor_frame_workflow.py
   ```

3. **Follow Generated Plan**:
   - Load video in Setup Wizard
   - Navigate to each suggested frame
   - Tag 3-5 players per frame
   - Save and run analysis

### For Corrections/Additions

1. **During Analysis**: If you see tracking errors
2. **Open Conflict Resolution**: Live Viewer Controls → Player Corrections
3. **Enter Frame Number**: Where the error occurs
4. **Click "Open Gallery Seeder"**: Automatically opens at that frame
5. **Tag Correct Player**: Creates new anchor frame
6. **Re-run Analysis**: Should fix the issue

## Best Practices

### Frame Selection

- ✅ **Beginning, Middle, End**: Essential frames
- ✅ **Evenly Spaced**: Good coverage across video
- ✅ **Custom**: Target specific game situations (scrum, open play, etc.)

### Player Selection

- ✅ **Key Players First**: Goalkeepers, star players
- ✅ **Both Teams**: Tag players from both teams
- ✅ **Consistent**: Tag same players across multiple frames
- ✅ **3-5 Players per Frame**: Good balance

### Time Investment

- **Quick Setup**: 5-10 minutes (10 frames, 3-5 players each)
- **Thorough Setup**: 15-30 minutes (20 frames, 5-7 players each)
- **Comprehensive**: 30-60 minutes (50+ frames, all players)

## Integration with Main Tools

### Setup Wizard
- Automatically creates anchor frames when you tag players
- Best for initial setup
- Has tracking context (track IDs)

### Gallery Seeder
- Also creates anchor frames
- Best for corrections/additions
- Can jump to specific frames
- Matched by bbox position

### Conflict Resolution
- Can open Gallery Seeder at specific frames
- Quick way to add anchor frames during analysis

## Troubleshooting

**Q: Helper script says "No module named 'cv2'"**
- Install OpenCV: `pip install opencv-python`
- Or use GUI tools instead

**Q: Batch workflow doesn't show video info**
- Make sure video file exists
- Check file path is correct
- OpenCV needed for video analysis

**Q: Anchor frames not being applied?**
- Check seed config file is in same directory as video
- Verify `anchor_frames` key exists in JSON
- Frame numbers should match (0-indexed)

## Files Created

- `anchor_frame_helper.py` - Command-line helper
- `batch_anchor_frame_workflow.py` - GUI workflow planner
- `ANCHOR_FRAMES_GUIDE.md` - Complete guide
- `BATCH_WORKFLOW_README.md` - This file

## Next Steps

1. ✅ Run helper script to analyze your videos
2. ✅ Use batch workflow to generate a plan
3. ✅ Follow plan in Setup Wizard or Gallery Seeder
4. ✅ Run analysis and verify anchor frames are working
5. ✅ Add more anchor frames as needed for corrections

---

**Remember**: More anchor frames = better tracking, but you don't need to tag every frame. Focus on key frames and key players! 🎯


# Anchor Frames Guide

## What are Anchor Frames?

Anchor frames are **ground truth** player tags with **1.00 confidence** that tell the system: "At this specific frame, this player is definitely at this position." They act as reference points that guide player tracking throughout the video.

## Why Use Anchor Frames?

- ✅ **Prevent ID switching**: Anchor frames lock player identity at specific frames
- ✅ **Guide tracking**: System uses anchor frames to maintain consistency
- ✅ **Conflict resolution**: When tracking gets confused, anchor frames provide ground truth
- ✅ **Better persistence**: Players tagged in anchor frames maintain their identity longer

## How to Create Anchor Frames

### Method 1: Setup Wizard (Recommended for Initial Setup)

1. **Start Setup Wizard** from the main GUI
2. **Navigate through frames** using arrow keys or frame slider
3. **Click on a player** to select them
4. **Enter player name** and select team
5. **Click "Tag Player"** - this automatically creates an anchor frame!
6. **Repeat** for multiple players in multiple frames

**Best Practice**: Tag 3-5 key players across different frames (beginning, middle, end) for best results.

### Method 2: Player Gallery Seeder (For Corrections/Additions)

1. **Click "Tag Players (Gallery)"** button in main GUI
2. **Load your video** (File → Load Video)
3. **Navigate to frame** using slider or frame controls
4. **Draw bounding box** around player (click and drag)
5. **Enter player name**, jersey number, and team
6. **Click "Add to Gallery"** - automatically creates anchor frame!

**Best Practice**: Use this method when you see tracking errors during analysis - jump to the problematic frame and tag the correct player.

### Method 3: From Conflict Resolution

1. **During analysis**, open "Live Viewer Controls"
2. **Go to "Player Corrections" tab**
3. **Enter frame number** where conflict occurs
4. **Click "📸 Open Gallery Seeder"**
5. **Tag the player** at that frame - creates anchor frame!

## Where Are Anchor Frames Saved?

Anchor frames are saved in:
- `PlayerTagsSeed-{video_name}.json` (preferred)
- `seed_config.json` (fallback)

Located in the **same directory** as your video file.

## Anchor Frame Format

```json
{
  "anchor_frames": {
    "100": [
      {
        "track_id": 5,
        "player_name": "John Doe",
        "team": "Blue",
        "bbox": [100, 200, 150, 300],
        "confidence": 1.00
      }
    ],
    "500": [
      {
        "track_id": null,
        "player_name": "Jane Smith",
        "team": "Gray",
        "bbox": [300, 400, 350, 500],
        "confidence": 1.00
      }
    ]
  }
}
```

**Note**: 
- `track_id` from Setup Wizard (has tracking context)
- `track_id: null` from Gallery Seeder (matched by bbox position)

## Best Practices

### ✅ DO:
- Tag **multiple frames** per player (spread throughout video)
- Tag **key players** first (most visible/important)
- Tag at **different game situations** (scrum, open play, etc.)
- Use **clear frames** where player is fully visible
- Tag **both teams** for better tracking

### ❌ DON'T:
- Don't tag only one frame per player
- Don't tag only at the beginning
- Don't tag blurry/occluded players
- Don't worry about tagging every single frame

## Recommended Workflow

1. **Initial Setup** (Setup Wizard):
   - Tag 5-10 key players
   - Tag at frames: 0, middle, end
   - Tag players from both teams

2. **Run Analysis**:
   - Let the system use anchor frames to guide tracking
   - Monitor for conflicts/errors

3. **Corrections** (Gallery Seeder):
   - When you see ID switching or conflicts
   - Jump to problematic frame
   - Tag correct player → creates new anchor frame
   - Re-run analysis

4. **Iterate**:
   - More anchor frames = better tracking
   - Add anchor frames as needed

## Checking Your Anchor Frames

To see how many anchor frames you have:

```python
import json
import glob

# Find seed config files
for file in glob.glob("*PlayerTagsSeed*.json") + ["seed_config.json"]:
    try:
        with open(file, 'r') as f:
            data = json.load(f)
        anchor_frames = data.get("anchor_frames", {})
        if anchor_frames:
            total = sum(len(anchors) for anchors in anchor_frames.values())
            print(f"{file}: {total} anchor tags in {len(anchor_frames)} frames")
    except:
        pass
```

## Troubleshooting

**Q: Anchor frames not being applied?**
- Check that seed config file is in same directory as video
- Verify anchor_frames key exists in JSON
- Check frame numbers match (0-indexed)

**Q: How many anchor frames do I need?**
- Minimum: 3-5 per key player
- Recommended: 10-20 total across all players
- More is better, but diminishing returns after ~50

**Q: Can I edit anchor frames manually?**
- Yes! Edit the JSON file directly
- Be careful with format (frame numbers as strings)
- Re-run analysis to apply changes

## Example: Creating Anchor Frames for a Game

1. **Start Setup Wizard** with your game video
2. **Frame 0**: Tag goalkeeper and 2-3 key players
3. **Frame 1000** (middle): Tag same players + 2-3 more
4. **Frame 2000** (end): Tag same players again
5. **Save and run analysis**
6. **If conflicts occur**: Use Gallery Seeder to add anchor frames at conflict frames
7. **Re-run analysis** - should be much better!

---

**Remember**: Anchor frames are your **ground truth**. The more accurate anchor frames you have, the better your tracking will be! 🎯


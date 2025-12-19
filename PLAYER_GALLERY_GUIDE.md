# 🎯 Player Gallery System - Complete Guide

## What is the Player Gallery?

The **Player Gallery** is a cross-video player recognition system that allows you to:
- **Tag a player once** with their name in any frame
- **Automatically recognize them** in all future videos
- **Maintain consistent player IDs** across different game recordings
- **Build a persistent player database** for your team

---

## 📋 How It Works

### Traditional System (OLD):
- Track ID #23 in `video1.mp4` ≠ Track ID #23 in `video2.mp4`
- You had to manually identify players in EVERY video
- Player names were lost between videos

### Player Gallery System (NEW):
1. You tag "Kevin Hill" once in a reference frame
2. The system extracts his visual features (jersey color, body shape, Re-ID embeddings)
3. Saves this to `player_gallery.json`
4. **Automatically recognizes** Kevin Hill in ALL future videos
5. Assigns him a consistent name across videos!

---

## 🚀 Quick Start Guide

### Step 1: Seed Players into the Gallery

Run the **Player Gallery Seeder** tool:

```bash
cd C:\Users\nerdw\soccer_analysis
python player_gallery_seeder.py
```

#### Using the Seeder:
1. **Load Video**: Click "Load Video" and select a game recording
2. **Navigate**: Use the slider and arrow buttons to find a clear frame
3. **Select Player**: Click and drag a box around a player
4. **Enter Name**: Type the player's name (e.g., "Kevin Hill")
5. **Optional**: Add jersey number and team
6. **Add to Gallery**: Click "Add to Gallery"

**Tips for Best Results:**
- Select frames where the player is clearly visible
- Make sure their jersey/uniform is in the selection
- Choose well-lit frames without blur
- Add multiple reference frames for better accuracy

---

### Step 2: Run Analysis with Gallery Recognition

Use the main GUI as normal:

```bash
python soccer_analysis_gui.py
```

**The system will automatically:**
- Load the player gallery at startup
- Match detected players against the gallery
- Assign gallery names to recognized players
- Print matches in the console:
  ```
  ✓ Gallery match: Track #23 = Kevin Hill (similarity: 0.87)
  ✓ Gallery match: Track #45 = John Doe (similarity: 0.82)
  ```

**You'll see in the output video:**
- `"Kevin Hill #23"` instead of `"Player #23"`
- Consistent names across ALL videos!

---

## 📁 Files and Structure

### `player_gallery.json` (Main Database)
Location: `C:\Users\nerdw\soccer_analysis\player_gallery.json`

This is your player database. **Back it up!** It contains all player profiles.

Example structure:
```json
{
  "kevin_hill": {
    "name": "Kevin Hill",
    "jersey_number": "4",
    "team": "Blue",
    "features": [0.12, 0.45, ...],  // Re-ID embedding (512 dimensions)
    "reference_frames": [
      {
        "video_path": "C:/Videos/game1.mp4",
        "frame_num": 123,
        "bbox": [100, 200, 150, 300]
      }
    ],
    "dominant_color": [110, 200, 180],  // HSV color
    "created_at": "2025-11-10T10:30:00",
    "updated_at": "2025-11-10T10:30:00"
  }
}
```

### New Python Modules

#### `player_gallery.py`
- **PlayerGallery**: Main class for managing the gallery
- **PlayerProfile**: Data structure for each player
- Methods: `add_player()`, `match_player()`, `update_player()`, `remove_player()`

#### `player_gallery_seeder.py`
- Interactive GUI tool for tagging players
- Video navigation and frame selection
- Feature extraction and gallery management

#### `reid_tracker.py` (Enhanced)
- New method: `match_against_gallery()` - Match detections vs gallery
- New method: `add_track_to_gallery()` - Add tracked player to gallery
- New method: `update_gallery_player()` - Update existing gallery player

#### `combined_analysis_optimized.py` (Enhanced)
- Loads `player_gallery.json` at startup
- Matches each detected player against the gallery
- Updates `player_names` dict with gallery matches in real-time
- Prints gallery matches to console

---

## 🎓 Advanced Usage

### Managing the Gallery

#### View All Players
```python
from player_gallery import PlayerGallery

gallery = PlayerGallery()
players = gallery.list_players()

for player_id, player_name in players:
    print(f"{player_id}: {player_name}")
```

#### Get Gallery Statistics
```python
stats = gallery.get_stats()
print(f"Total Players: {stats['total_players']}")
print(f"With Features: {stats['players_with_features']}")
```

#### Remove a Player
```python
gallery.remove_player("kevin_hill")
```

#### Manually Add a Player (Advanced)
```python
import numpy as np

gallery.add_player(
    name="New Player",
    features=np.array([...]),  # Re-ID embedding
    jersey_number="42",
    team="Red",
    dominant_color=np.array([120, 180, 200])  # HSV
)
```

---

## 🔧 Configuration & Tuning

### Gallery Matching Threshold

In `combined_analysis_optimized.py` (line ~3763):
```python
gallery_matches = reid_tracker.match_against_gallery(
    features=reid_features,
    gallery=player_gallery,
    similarity_threshold=0.6  # Adjust this value
)
```

**Threshold Guidelines:**
- `0.7-0.8`: **Strict** - Very high confidence, fewer matches
- `0.6`: **Balanced** (default) - Good accuracy with reasonable matches
- `0.4-0.5`: **Lenient** - More matches, but potential misidentification

### Color Similarity Boost

The system uses both:
1. **Re-ID features** (70% weight) - Visual appearance embedding
2. **Color similarity** (30% weight) - Jersey/uniform color matching

This is configured in `player_gallery.py` (`match_player()` method, line ~237).

---

## 🐛 Troubleshooting

### Problem: "Player Gallery not available"
**Solution**: Make sure `player_gallery.py` is in the `soccer_analysis` directory.

### Problem: No gallery matches found
**Possible causes**:
1. Gallery is empty - use `player_gallery_seeder.py` to add players
2. Similarity threshold too high - lower it in the code
3. Player appearance has changed (different jersey, different angle)
4. Poor feature extraction (blurry/dark reference frames)

**Solution**: Add more reference frames for the player from different angles.

### Problem: Wrong player identified
**Possible causes**:
1. Players look very similar (same jersey, same team)
2. Similarity threshold too low
3. Poor reference frames

**Solution**: 
- Increase similarity threshold to 0.7+
- Add more distinctive reference frames
- Include jersey number in team classification

### Problem: "Re-ID tracker not available"
**Solution**: Install PyTorch and torchreid:
```bash
pip install torch torchreid
```

---

## 💡 Best Practices

### For Best Gallery Performance:

1. **High-Quality Reference Frames**
   - Well-lit scenes
   - Player facing camera
   - Jersey/uniform clearly visible
   - Minimal motion blur

2. **Multiple Reference Frames**
   - Add 2-3 reference frames per player
   - Different angles and poses
   - Different lighting conditions

3. **Distinctive Features**
   - Include jersey number in name (e.g., "Kevin Hill #4")
   - Note dominant jersey color
   - Tag players from different teams separately

4. **Regular Backups**
   - Back up `player_gallery.json` regularly
   - Keep it version controlled if possible

5. **Gallery Maintenance**
   - Remove duplicate entries
   - Update players if jerseys change
   - Add new players as they appear

---

## 🎯 Real-World Workflow

### Scenario: Season-Long Player Tracking

**Week 1:**
1. Record first practice/game
2. Open `player_gallery_seeder.py`
3. Tag all 20 players with their names
4. Run analysis - players get consistent IDs

**Week 2-N:**
1. Record new practices/games
2. Run analysis directly (NO manual tagging needed!)
3. System automatically recognizes players from Week 1
4. Only tag NEW players who weren't in gallery

**Result:**
- Consistent player IDs across entire season
- Automatic player recognition
- Easy to track individual player performance over time

---

## 📊 Gallery Statistics

View your gallery stats anytime:

```bash
cd C:\Users\nerdw\soccer_analysis
python player_gallery.py
```

Output:
```
=== Player Gallery Stats ===
total_players: 22
players_with_features: 22
players_with_reference_frames: 22
gallery_path: player_gallery.json

=== Current Players ===
  kevin_hill: Kevin Hill
  john_doe: John Doe
  sarah_jones: Sarah Jones
  ...
```

---

## 🚀 Next Steps

1. **Run the seeder**: `python player_gallery_seeder.py`
2. **Tag your players**: Add at least 5-10 key players
3. **Test the system**: Run analysis on a video and verify matches
4. **Expand the gallery**: Add more players over time
5. **Back up your gallery**: Copy `player_gallery.json` to a safe location

---

## 🤝 Support

If you encounter issues:
1. Check the console output for error messages
2. Verify `player_gallery.json` exists and is valid JSON
3. Ensure Re-ID is enabled in the GUI (it's required for gallery matching)
4. Try lowering the similarity threshold for more matches

---

**🎉 Congratulations!** You now have a powerful cross-video player recognition system. Tag players once, recognize them forever! ⚽


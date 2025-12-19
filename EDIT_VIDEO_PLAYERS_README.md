# Per-Video Player Gallery and CSV Editor

Utility script for editing player references in the gallery and CSV files for specific videos.

## Features

- **Rename players** in gallery references (e.g., Cameron Melnik → Anay Rao)
- **Remove players** from gallery references for a specific video
- **Remove players** from CSV files
- **List players** in a video
- **Automatic backups** before making changes

## Usage

### List Players in Video

```bash
python edit_video_players.py --video "20251001_183951" --list-players
```

### Rename Player in Gallery

Transfers all reference frames from one player to another for a specific video:

```bash
python edit_video_players.py --video "20251001_183951" --rename "Cameron Melnik" "Anay Rao"
```

- If the target player (Anay Rao) exists, frames are transferred to that player
- If the target player doesn't exist, the source player is renamed
- Only affects frames from the specified video

### Remove Players from Gallery

Removes all reference frames for specified players from a video:

```bash
python edit_video_players.py --video "20251001_183951" --remove-players "James Carlson,Ellie Hill,Rocco Piazza"
```

### Remove Players from CSV

Removes all rows for specified players from a CSV file:

```bash
python edit_video_players.py --csv "path/to/file.csv" --remove-players "James Carlson,Ellie Hill,Rocco Piazza"
```

### Combined Operations

You can combine operations in a single command:

```bash
python edit_video_players.py --video "20251001_183951" --rename "Cameron Melnik" "Anay Rao" --remove-players "James Carlson,Ellie Hill,Rocco Piazza"
```

## Video Search

The `--video` parameter accepts:
- Video filename (e.g., `"20251001_183951"`)
- Partial filename match
- Full video path (will match if contained in reference frame paths)

The script automatically finds matching videos in the gallery by searching reference frame `video_path` fields.

## Backup Files

The script automatically creates timestamped backups before making changes:
- Gallery: `player_gallery_backup_YYYYMMDD_HHMMSS.json`
- CSV: `filename_backup_YYYYMMDD_HHMMSS.csv`

Use `--no-backup` to skip backups (not recommended).

## Examples

### Example 1: Fix Misidentified Player

```bash
# List players to see what's in the video
python edit_video_players.py --video "20251001_183951" --list-players

# Rename Cameron Melnik to Anay Rao
python edit_video_players.py --video "20251001_183951" --rename "Cameron Melnik" "Anay Rao"
```

### Example 2: Clean Up Wrong Players

```bash
# Remove players that shouldn't be in this video
python edit_video_players.py --video "20251001_183951" --remove-players "James Carlson,Ellie Hill,Rocco Piazza"

# Also remove from CSV
python edit_video_players.py --csv "20251001_183951_analyzed_tracking_data.csv" --remove-players "James Carlson,Ellie Hill,Rocco Piazza"
```

### Example 3: Complete Cleanup

```bash
# Rename and remove in one command
python edit_video_players.py \
  --video "20251001_183951" \
  --rename "Cameron Melnik" "Anay Rao" \
  --remove-players "James Carlson,Ellie Hill,Rocco Piazza"

# Then clean CSV
python edit_video_players.py \
  --csv "20251001_183951_analyzed_tracking_data.csv" \
  --remove-players "James Carlson,Ellie Hill,Rocco Piazza"
```

## Notes

- **Gallery Structure**: The script handles reference frames in:
  - `reference_frames` (main list)
  - `uniform_variants` (organized by uniform combinations)
  - `foot_reference_frames` (foot/shoe region frames)

- **CSV Format**: The script handles player names in:
  - Direct string format: `"Cameron Melnik"`
  - List format: `"['Cameron Melnik', 'Blue', '']"` (extracts first element)

- **Video Matching**: Uses case-insensitive partial matching on video paths, so you can use:
  - Filename: `"20251001_183951"`
  - Partial: `"183951"`
  - Full path: `"C:\Users\nerdw\Videos\Outdoor\20251001_183951.mp4"`

## Integration with GUI

This utility can be integrated into the Player Management section of the GUI. The GUI can call this script with appropriate parameters when users want to edit players for a specific video.


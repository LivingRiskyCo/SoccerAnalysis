# Soccer Video Analysis Scripts

Python scripts for analyzing soccer game footage recorded with Samsung S24 Ultra ultra-wide lens. Includes dewarping, ball tracking, and player detection/tracking capabilities.

## Features

1. **Dewarping**: Corrects fisheye distortion from ultra-wide lens (120° FOV)
2. **Ball Tracking**: Detects and overlays ball path with trail visualization
3. **Player Detection & Tracking**: Uses YOLOv8 to detect players, track movement, and generate heatmaps

## Requirements

- Python 3.10+
- Mid-range PC (i5/Ryzen 5, 16GB RAM recommended)
- GPU optional but recommended for faster YOLO processing (~2x speedup)

## Installation

1. **Create virtual environment**:
   ```bash
   # Windows
   python -m venv env
   env\Scripts\activate
   
   # Linux/Mac
   python -m venv env
   source env/bin/activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **YOLO weights**: Will download automatically on first run, or download manually from [Ultralytics GitHub](https://github.com/ultralytics/ultralytics)

## Usage

### GUI Application (Recommended - Easy to Use)

**NEW**: Launch the user-friendly GUI application:

**Windows**:
```bash
# Double-click run_gui.bat
# Or from command line:
cd C:\Users\nerdw\soccer_analysis
env\Scripts\activate
python soccer_analysis_gui.py
```

The GUI provides:
- ✅ File browser for input/output videos
- ✅ Checkboxes for all options (dewarping, ball tracking, player tracking)
- ✅ Ball trail length slider
- ✅ Real-time progress bar
- ✅ Processing log output
- ✅ One-click processing

**Features**:
- Select input video with file browser
- Auto-generates output filename
- Enable/disable features with checkboxes
- Adjust ball trail length
- See progress in real-time
- View processing logs

---

### Command Line Usage

### 1. Dewarp Video (Fix Fisheye Distortion)

Corrects the ultra-wide lens distortion to get straight field lines.

```bash
python dewarp.py --input game.mp4 --output dewarped.mp4
```

**Options**:
- `--ifov`: Input field of view in degrees (default: 120)
- `--ofov`: Output field of view in degrees (default: 90)

**Example with custom FOV**:
```bash
python dewarp.py --input game.mp4 --output dewarped.mp4 --ifov 120 --ofov 90
```

### 2. Track Ball

Detects and tracks the soccer ball, overlaying a trail showing its path.

```bash
python ball_track.py --input dewarped.mp4 --output ball_tracked.mp4
```

**Options**:
- `--buffer`: Length of ball trail (default: 64)

**Example with shorter trail**:
```bash
python ball_track.py --input dewarped.mp4 --output ball_tracked.mp4 --buffer 32
```

**Note**: You may need to tune the HSV color range in the script for your lighting conditions. Look for the `lower_white` and `upper_white` values in `ball_track.py`.

### 3. Track Players

Detects players using YOLOv8, assigns track IDs, and generates a position heatmap.

```bash
python player_track.py --input dewarped.mp4 --output players_tracked.mp4
```

**Outputs**:
- `players_tracked.mp4`: Video with bounding boxes and track IDs
- `player_heatmap.png`: Heatmap showing player position density

### 4. Combined Analysis (Recommended)

**NEW**: Combined script that runs all analysis steps in one pass with CSV export and possession calculation.

```bash
python combined_analysis.py --input game.mp4 --output analyzed.mp4 --dewarp
```

**Options**:
- `--dewarp`: Apply fisheye correction
- `--no-ball`: Skip ball tracking
- `--no-players`: Skip player tracking
- `--no-csv`: Skip CSV export
- `--buffer`: Ball trail length (default: 64)

**Example - Full analysis with dewarping**:
```bash
python combined_analysis.py --input game.mp4 --output full_analysis.mp4 --dewarp --buffer 32
```

**Outputs**:
- `analyzed.mp4`: Video with all annotations (ball trail, player boxes, IDs)
- `analyzed_tracking_data.csv`: CSV with frame-by-frame tracking data including:
  - Ball position (x, y)
  - Player positions (x, y) with track IDs
  - Possession calculation (closest player to ball)
  - Distance to ball metrics
- `analyzed_heatmap.png`: Player position heatmap

**Benefits**:
- Single pass processing (faster than running scripts separately)
- CSV export for data analysis in Excel/Python/Pandas
- Possession calculation (distance-based)
- Optional features (can skip dewarping/ball/players if needed)

## Full Workflow

### Option 1: Individual Scripts (More Control)

1. **Record**: S24 Ultra → `game.mp4`
2. **Dewarp**: `python dewarp.py --input game.mp4 --output dewarped.mp4`
3. **Ball Track**: `python ball_track.py --input dewarped.mp4 --output ball_final.mp4`
4. **Player Track**: `python player_track.py --input dewarped.mp4 --output players_final.mp4`
5. **Post-process**: Combine in DaVinci Resolve or similar editor

### Option 2: Combined Script (Recommended - Faster)

1. **Record**: S24 Ultra → `game.mp4`
2. **Run Combined Analysis**: `python combined_analysis.py --input game.mp4 --output analyzed.mp4 --dewarp`
3. **Analyze CSV**: Open `analyzed_tracking_data.csv` in Excel/Python for metrics
4. **Post-process**: Use output video in DaVinci Resolve or similar editor

## Testing

Before processing a full 90-minute game, test on a short clip:

```bash
# Extract 1-minute test clip (requires ffmpeg)
ffmpeg -i game.mp4 -t 60 short.mp4

# Test dewarping
python dewarp.py --input short.mp4 --output test_dewarped.mp4

# Test ball tracking
python ball_track.py --input test_dewarped.mp4 --output test_ball.mp4

# Test player tracking
python player_track.py --input test_dewarped.mp4 --output test_players.mp4
```

## Performance

- **Dewarping**: ~10-15 minutes for 90-min 4K video
- **Ball Tracking**: ~20-30 minutes for 90-min video
- **Player Tracking**: ~30-60 minutes for 90-min video (depends on CPU/GPU)

## Tuning Tips

### Dewarping
- Adjust `--ifov` and `--ofov` based on your lens FOV
- Test on a 10-second clip first to find optimal values

### Ball Tracking
- Tune HSV values (`lower_white`, `upper_white`) for your field lighting
- Adjust minimum radius threshold (currently 10 pixels) based on ball size in video
- For green grass fields, you may need to adjust the white detection range

### Player Tracking
- Use `yolov8n.pt` (nano) for speed, `yolov8s.pt` or `yolov8m.pt` for better accuracy
- Fine-tune YOLO on SoccerNet dataset for better soccer-specific detection
- Add HSV clustering post-detection to identify team colors

## Troubleshooting

- **Import errors**: Make sure virtual environment is activated and all packages are installed
- **YOLO download**: First run will download weights (~6MB). Ensure internet connection.
- **Video codec issues**: If output video doesn't play, try changing `fourcc` codec to `'XVID'` or `'H264'`

## Enhanced Packages (Optional)

Based on recommendations from the community, consider these optional packages for advanced features:

- **SportsLabKit**: Advanced tracking algorithms (SORT, DeepSORT, ByteTrack, TeamTrack)
  ```bash
  pip install sportslabkit
  ```

- **soccer-cv**: Soccer-specific visualization and 2D layout rendering
  ```bash
  pip install soccer-cv
  ```

- **databallpy**: Framework for preprocessing, synchronizing tracking/event data, and soccer metrics
  ```bash
  pip install databallpy
  ```

## Next Steps

- ✅ Combined pipeline script (done - see `combined_analysis.py`)
- ✅ Possession calculation (done - distance-based in combined script)
- ✅ CSV export (done - includes all tracking data)
- Fine-tune YOLO on soccer-specific datasets (SoccerNet)
- Add team color detection (HSV clustering)
- Integrate SportsLabKit for advanced tracking algorithms
- Add 2D pitch visualization using soccer-cv

## License

Free to use and modify for your soccer analysis projects.


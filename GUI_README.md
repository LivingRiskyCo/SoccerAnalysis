# Soccer Analysis GUI - Quick Start

## Launching the GUI

### Option 1: Double-click launcher (Windows)
1. Double-click `run_gui.bat` in the project folder
2. GUI window will open

### Option 2: Command line
```powershell
cd C:\Users\nerdw\soccer_analysis
.\env\Scripts\activate
python soccer_analysis_gui.py
```

## Using the GUI

### Step 1: Select Input Video
1. Click **"Browse"** next to "Input Video"
2. Select your practice video file (e.g., `practice_20241104.mp4`)
3. Output filename will be auto-generated (you can change it)

### Step 2: Configure Options
- ✅ **Apply Dewarping**: Fix fisheye distortion (recommended for ultra-wide lens)
- ✅ **Track Ball**: Detect and track ball with trail overlay
- ✅ **Track Players**: Detect players with YOLO and assign track IDs
- ✅ **Export CSV**: Generate CSV file with tracking data

**Ball Trail Length**: Adjust the number of frames for the ball trail (default: 64)

### Step 3: Start Processing
1. Click **"Start Analysis"** button
2. Watch progress bar and log output
3. Processing will take 1-2 hours for a 90-minute practice

### Step 4: View Results
After processing completes:
- ✅ Annotated video with ball trail and player tracking
- ✅ CSV file with tracking data (if enabled)
- ✅ Heatmap image showing player positions (if player tracking enabled)

## Output Files

When processing completes, you'll get:

1. **`[your_video]_analyzed.mp4`**
   - Dewarped video (if enabled)
   - Ball tracking with trail (if enabled)
   - Player tracking with bounding boxes and IDs (if enabled)

2. **`[your_video]_tracking_data.csv`** (if CSV export enabled)
   - Frame-by-frame tracking data
   - Ball positions (x, y)
   - Player positions (x, y) with track IDs
   - Possession data (closest player to ball)
   - Distance metrics

3. **`[your_video]_heatmap.png`** (if player tracking enabled)
   - Player position density map
   - Shows where players spent most time

## Tips

- **Test First**: Process a short 1-minute clip before full video
- **Progress**: Watch the log output for real-time status
- **Stop**: Click "Stop" button if you need to cancel (current frame will complete)
- **Options**: You can disable dewarping, ball tracking, or player tracking if needed

## Troubleshooting

### GUI won't open
- Make sure virtual environment is activated: `.\env\Scripts\activate`
- Check Python is installed: `python --version`
- Verify packages installed: `pip list`

### Processing fails
- Check log output for specific error messages
- Verify input video file exists and is valid
- Make sure at least one tracking option is enabled (ball or players)

### No output files
- Check the output directory path
- Verify you have write permissions
- Check log for error messages

## Keyboard Shortcuts

- **Ctrl+O**: Open input file (coming soon)
- **Ctrl+S**: Save output as (coming soon)
- **Escape**: Close window

## Next Steps

After processing, you can:
1. Open the CSV file in Excel for analysis
2. View the heatmap image
3. Import tracking data into other analysis tools
4. Use the annotated video for coaching analysis



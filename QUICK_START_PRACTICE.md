# Quick Start: Practice Video Workflow

## Tomorrow's Recording & Processing Steps

### Step 1: Record the Practice (Samsung S24 Ultra)

1. **Setup**:
   - Mount S24 Ultra on 15.7 ft tripod
   - Position for full-field 120° view
   - Set to **4K/60fps** recording mode
   - Ultra-wide lens (120° FOV)

2. **Recording Tips**:
   - Record in **landscape mode**
   - Ensure good lighting (daylight practice recommended)
   - Keep phone steady on tripod
   - Start recording before practice begins
   - Stop after practice ends

3. **File Transfer**:
   - Transfer video from phone to PC
   - Save as `practice_YYYYMMDD.mp4` (e.g., `practice_20241104.mp4`)
   - Place in the `soccer_analysis` folder

---

### Step 2: Process Your Video

#### Option A: GUI Application (Easiest - Recommended!)

1. **Launch GUI**:
   - Double-click `run_gui.bat` in the project folder
   - Or run: `python soccer_analysis_gui.py` (after activating venv)

2. **In the GUI**:
   - Click "Browse" next to "Input Video" → Select your practice video
   - Output filename will auto-generate (you can change it)
   - ✅ Check options: Dewarping, Ball Tracking, Player Tracking, CSV Export
   - Adjust "Ball Trail Length" if needed (default: 64)
   - Click **"Start Analysis"**
   - Watch progress bar and log output

3. **Wait for completion** (1-2 hours for 90-min practice)

4. **View results**:
   - Annotated video: `[your_video]_analyzed.mp4`
   - CSV data: `[your_video]_tracking_data.csv`
   - Heatmap: `[your_video]_heatmap.png`

#### Option B: Command Line (Quick Test First)

Before processing the full practice, test on a short clip:

```powershell
# Navigate to project folder
cd C:\Users\nerdw\soccer_analysis

# Activate virtual environment (if not already active)
env\Scripts\activate

# Extract 60-second test clip (requires ffmpeg)
ffmpeg -i practice_20241104.mp4 -t 60 test_clip.mp4

# Test combined analysis
python combined_analysis.py --input test_clip.mp4 --output test_analyzed.mp4 --dewarp --buffer 32
```

**Check the output**:
- ✅ Does dewarping look correct? (field lines should be straight)
- ✅ Is the ball being tracked? (green circle + red trail)
- ✅ Are players being detected? (yellow boxes with IDs)
- ✅ Open `test_analyzed_tracking_data.csv` - does it have data?

**If issues**:
- **Ball not tracking**: Adjust HSV values in `ball_track.py` or `combined_analysis.py`
- **Players not detected**: Check lighting/position
- **Dewarping looks wrong**: Adjust `--ifov` and `--ofov` values

---

### Step 3: Process Full Practice Video

Once the test clip looks good, process the full practice:

```powershell
# Make sure you're in the project folder
cd C:\Users\nerdw\soccer_analysis

# Activate virtual environment
env\Scripts\activate

# Run full analysis (this takes 1-2 hours for 90-min practice)
python combined_analysis.py --input practice_20241104.mp4 --output practice_analyzed.mp4 --dewarp --buffer 32
```

**What to expect**:
- Processing time: ~1-2 hours for 90-minute practice
- Progress updates every 100 frames
- Final output: `practice_analyzed.mp4` + CSV + heatmap

---

### Step 4: Review Results

After processing completes, you'll have:

1. **`practice_analyzed.mp4`**:
   - Dewarped video (straight field lines)
   - Ball tracking (green circle, red trail)
   - Player tracking (yellow boxes, track IDs)

2. **`practice_analyzed_tracking_data.csv`**:
   - Frame-by-frame data
   - Ball positions (x, y)
   - Player positions (x, y) with IDs
   - Possession (closest player to ball)
   - Distance metrics

3. **`practice_analyzed_heatmap.png`**:
   - Player position density map
   - Shows where players spent most time

---

### Step 5: Analyze the Data (Optional)

**In Excel**:
- Open `practice_analyzed_tracking_data.csv`
- Filter by player ID to see individual movement
- Sort by possession to see ball possession stats
- Create charts for distance traveled

**In Python**:
```python
import pandas as pd
import matplotlib.pyplot as plt

# Load tracking data
df = pd.read_csv('practice_analyzed_tracking_data.csv')

# Filter by player ID
player_1 = df[df['player_id'] == 1]

# Calculate distance traveled
player_1['distance'] = player_1[['player_x', 'player_y']].diff().fillna(0).pow(2).sum(axis=1).pow(0.5)
total_distance = player_1['distance'].sum()

print(f"Player 1 total distance: {total_distance:.2f} pixels")
```

---

## Quick Troubleshooting

### If ball tracking doesn't work:
1. Open `combined_analysis.py` or `ball_track.py`
2. Find `lower_white` and `upper_white` HSV values
3. Adjust for your lighting:
   - **Brighter field**: Increase lower_white[2] (e.g., 220 → 230)
   - **Darker field**: Decrease lower_white[2] (e.g., 200 → 180)

### If dewarping looks wrong:
1. Test with different FOV values:
   ```powershell
   python dewarp.py --input test_clip.mp4 --output test_dewarp.mp4 --ifov 120 --ofov 90
   ```
2. Try variations: `--ifov 115 --ofov 85` or `--ifov 125 --ofov 95`

### If processing is too slow:
1. Use smaller YOLO model: Change `yolov8n.pt` to `yolov8n.pt` (already using nano)
2. Process in segments: Split video into 20-minute chunks
3. Skip dewarping if not critical: Remove `--dewarp` flag

---

## Full Command Reference

```powershell
# Activate environment
cd C:\Users\nerdw\soccer_analysis
env\Scripts\activate

# Test clip (60 seconds)
ffmpeg -i practice_20241104.mp4 -t 60 test_clip.mp4
python combined_analysis.py --input test_clip.mp4 --output test_analyzed.mp4 --dewarp

# Full practice
python combined_analysis.py --input practice_20241104.mp4 --output practice_analyzed.mp4 --dewarp --buffer 32

# Or individual scripts (if you prefer)
python dewarp.py --input practice_20241104.mp4 --output dewarped.mp4
python ball_track.py --input dewarped.mp4 --output ball_tracked.mp4 --buffer 32
python player_track.py --input dewarped.mp4 --output players_tracked.mp4
```

---

## Timeline Estimate

- **Recording**: 90 minutes (practice duration)
- **Transfer to PC**: 5-10 minutes
- **Test clip processing**: 2-5 minutes
- **Full video processing**: 60-120 minutes (1-2 hours)
- **Review & analysis**: 10-30 minutes

**Total**: ~2-3 hours from recording to results

---

## Pro Tips

1. **Record in segments**: If practice is broken into drills, record separate files for easier analysis
2. **Name files clearly**: Use dates/times (e.g., `practice_20241104_1430.mp4`)
3. **Backup originals**: Keep original video files before processing
4. **Batch processing**: Process multiple videos overnight
5. **GPU acceleration**: If you have an NVIDIA GPU, YOLO will automatically use it (faster)

---

Good luck with practice tomorrow! 🏈⚽


# Player Speed Tracking & Field Coverage Guide

## Overview

Track player speeds (km/h) and generate top-down field coverage heatmaps. Perfect for analyzing player movement patterns and performance metrics.

## Quick Start

### Step 1: Calibrate Field (Once Per Venue)

**Why**: Converts video perspective to real-world coordinates (meters) for accurate speed calculations.

1. **Take a screenshot** of your video when the full field is visible
   - Pause video at best frame
   - Save as `field_ref.jpg` (or any image format)

2. **Open GUI** → Click **"Calibrate Field"** button

3. **Select image** → Choose your field reference image

4. **Enter field dimensions**:
   - Length: e.g., `40` meters (indoor)
   - Width: e.g., `20` meters (indoor)

5. **Click 4 corners** in this order:
   - Top-Left corner
   - Top-Right corner
   - Bottom-Right corner
   - Bottom-Left corner

6. **Calibration saved** automatically:
   - `calibration.npy` - Perspective transformation points
   - `field_dimensions.npy` - Field size in meters

**Note**: You only need to do this once per venue. Re-calibrate if camera position changes.

---

### Step 2: Track Speed & Coverage

1. **Open GUI** → Click **"Speed Tracking"** button

2. **Select input video** → Your practice/game video

3. **Select output path** → Where to save analyzed video

4. **Processing starts** automatically:
   - Detects players with YOLOv11
   - Tracks movement with ByteTrack
   - Calculates speed (km/h) in real-time
   - Generates field coverage heatmap

---

## Command Line Usage

### Calibrate Field

```bash
python calibrate_field.py --image field_ref.jpg --length 40 --width 20
```

**Options**:
- `--image`: Path to reference image with full field visible
- `--length`: Real-world field length in meters (default: 40m)
- `--width`: Real-world field width in meters (default: 20m)

### Track Speed & Coverage

```bash
python track_speed_coverage.py --input practice.mp4 --output practice_speed.mp4
```

**Options**:
- `--input`: Input video path
- `--output`: Output video path

---

## Output Files

### 1. Analyzed Video (`[video]_speed_tracked.mp4`)
- Video with player IDs
- Real-time speed labels (km/h)
- Bounding boxes around players

### 2. Speed Data CSV (`[video]_speed_data.csv`)
Columns:
- `frame`: Frame number
- `timestamp`: Time in seconds
- `player_id`: Track ID
- `x_px`, `y_px`: Pixel coordinates
- `x_m`, `y_m`: Real-world coordinates (meters)
- `speed_kmh`: Speed in km/h

### 3. Field Coverage Heatmap (`[video]_field_coverage.png`)
- Top-down field view
- Heatmap showing player density (red = high traffic)
- Player paths overlaid
- Field lines and boundaries

---

## Speed Statistics

After processing, you'll see:
- **Average speed**: Mean speed across all players
- **Median speed**: Middle speed value
- **Maximum speed**: Fastest sprint speed
- **Per-player stats**: Top 5 fastest players by max speed

**Example Output**:
```
Speed Statistics:
Average speed: 8.4 km/h
Median speed: 7.2 km/h
Maximum speed: 24.1 km/h
Total measurements: 15,234

Top 5 Fastest Players (by max speed):
  1. Player ID 23: Max 24.1 km/h, Avg 9.2 km/h
  2. Player ID 15: Max 22.8 km/h, Avg 8.7 km/h
  3. Player ID 7: Max 21.5 km/h, Avg 7.9 km/h
  ...
```

---

## Field Dimensions

### Indoor Fields (Common)
- **Small**: 30m x 15m
- **Medium**: 40m x 20m (default)
- **Large**: 50m x 25m

### Outdoor Fields (Common)
- **Youth**: 60m x 40m
- **Adult**: 105m x 68m (FIFA standard)

**Tip**: Measure your field or check with facility manager for exact dimensions.

---

## Tips for Best Results

### Camera Position
- **Best**: Long side of field (not behind goal)
- **Coverage**: Try to get full field in frame
- **Height**: Elevated position helps (stands, balcony)

### Calibration
- **Use clear frame**: Field corners clearly visible
- **No obstructions**: Avoid players blocking corners
- **Good lighting**: Consistent lighting across field

### Speed Tracking
- **Frame rate**: Higher FPS = more accurate speed (60fps recommended)
- **Tracking**: ByteTrack handles ID switching well
- **Foot position**: Uses bottom of bounding box (feet) for more accurate tracking

---

## Troubleshooting

### Calibration Issues

**Problem**: "Calibration points not aligning"
- **Solution**: Make sure you click corners in correct order (Top-Left → Top-Right → Bottom-Right → Bottom-Left)

**Problem**: "Speeds seem wrong"
- **Solution**: Check field dimensions (length/width) match your actual field

### Speed Tracking Issues

**Problem**: "No speed data in CSV"
- **Solution**: Make sure players are being detected (check video for bounding boxes)

**Problem**: "Speeds too high/low"
- **Solution**: Verify field dimensions are correct in meters
- **Check**: Frame rate is correct (30fps vs 60fps makes a difference)

**Problem**: "Field coverage map looks wrong"
- **Solution**: Re-calibrate field with better reference image

---

## Advanced Usage

### Custom Field Dimensions

Edit `field_dimensions.npy` or pass `--length` and `--width` when calibrating:

```bash
python calibrate_field.py --image field.jpg --length 50 --width 25
```

### Multiple Venues

Create separate calibration files:
- `calibration_venue1.npy`
- `calibration_venue2.npy`

Then modify `track_speed_coverage.py` to load specific calibration file.

### Export to Other Formats

CSV data can be imported into:
- Excel/Google Sheets
- Python pandas for analysis
- R for statistical analysis
- Tableau for visualization

---

## Integration with Main Analysis

Speed tracking works alongside the main analysis:
1. Run **main analysis** for ball/player tracking
2. Run **speed tracking** for speed metrics and field coverage
3. Combine data from both CSV files for comprehensive analysis

---

## Example Workflow

1. **Record practice** (50 min 4K video)
2. **Take screenshot** of full field → Save as `field_ref.jpg`
3. **Calibrate field** → GUI → "Calibrate Field" → Click 4 corners
4. **Process video** → GUI → "Speed Tracking" → Select video
5. **View results**:
   - Video with speed labels
   - CSV with speed data
   - Field coverage heatmap
6. **Analyze**:
   - Who ran fastest?
   - Where did players spend most time?
   - Which areas had highest traffic?

---

**Next Steps**: Want team color classification, possession %, or other metrics? Let me know!


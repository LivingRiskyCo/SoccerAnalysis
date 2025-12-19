# Ball Color Detection Helper Guide

## Overview

The Ball Color Helper is a tool to easily detect and configure HSV color ranges for different colored balls. Perfect for when you use different balls (red/white, pink/white, blue/yellow, etc.).

## How to Use

### Step 1: Open the Helper
1. Open the main GUI
2. Click **"Ball Color Helper"** button (in the action buttons section)
3. A new window will open

### Step 2: Load Video/Image
- **Load Video**: Select a video file (MOV, MP4, etc.)
  - Click "Grab Frame" to get a frame from the video
- **Load Image**: Select a single image file (JPG, PNG, etc.)
  - Image loads immediately

### Step 3: Sample Ball Colors
1. **Name your colors** (optional):
   - Color 1: e.g., "White", "Blue", etc.
   - Color 2: e.g., "Red", "Pink", etc.

2. **Click "Sample" for Color 1**:
   - Click on the primary color part of the ball in the image
   - HSV values will be automatically calculated

3. **Click "Sample" for Color 2**:
   - Click on the secondary color part of the ball
   - HSV values will be automatically calculated

4. **Review HSV ranges**:
   - HSV ranges are displayed below
   - Adjust if needed (currently automatic, manual adjustment coming soon)

### Step 4: Save Preset (Optional)
1. Click **"Save Preset"**
2. Enter a name (e.g., "Red White Ball", "Pink White Ball")
3. Preset is saved for future use
4. Load presets from the dropdown menu

### Step 5: Apply to Analysis
1. Click **"Apply to Analysis"**
2. HSV ranges are saved to `ball_color_config.json`
3. The analysis script will automatically use these ranges
4. Helper window closes

## How It Works

### Automatic HSV Range Calculation
- **White/Light colors**: Detects bright colors (V > 200) and creates appropriate white range
- **Red colors**: Automatically handles two HSV ranges (red wraps around 0/180)
- **Other colors**: Creates appropriate HSV range based on sampled color

### Configuration File
- Saves to: `ball_color_config.json`
- Format:
  ```json
  {
    "color1_name": "White",
    "color2_name": "Red",
    "hsv_ranges": {
      "color1": {
        "lower": [0, 0, 200],
        "upper": [180, 30, 255]
      },
      "color2": {
        "lower1": [0, 50, 50],
        "upper1": [10, 255, 255],
        "lower2": [170, 50, 50],
        "upper2": [180, 255, 255]
      }
    }
  }
  ```

### Analysis Script Integration
- The analysis script automatically loads `ball_color_config.json` if it exists
- If no config file exists, uses default (red/white ball)
- Config file takes precedence over default settings

## Tips

### For Best Results:
1. **Sample multiple points**: Click on different parts of the ball to ensure good coverage
2. **Use video frames**: Grab a frame where the ball is clearly visible
3. **Test lighting**: Different lighting conditions may need different HSV ranges
4. **Save presets**: Save presets for different balls and lighting conditions

### Common Ball Colors:
- **Red/White**: Default (already configured)
- **Pink/White**: Sample pink part (usually H=150-170)
- **Blue/Yellow**: Sample both colors
- **Orange/White**: Sample orange part (usually H=10-25)
- **Green/Yellow**: Sample green part (usually H=60-80)

## Troubleshooting

### Ball not detected after sampling:
- Try sampling multiple points on the ball
- Check lighting conditions (may need different HSV range)
- Verify ball is in frame when sampling

### Helper window doesn't open:
- Make sure `ball_color_detector.py` is in the same folder
- Check for error messages in the main GUI log

### Image doesn't display:
- Install Pillow: `pip install pillow`
- Check that image/video file is valid

## Preset Management

### Save Preset:
- Configure HSV ranges
- Click "Save Preset"
- Enter name
- Preset saved to `ball_color_presets.json`

### Load Preset:
- Select preset from dropdown
- HSV ranges automatically loaded
- Color names updated

### Delete Preset:
- Select preset from dropdown
- Click "Delete Preset"
- Confirm deletion

## Integration with Analysis

Once you apply HSV ranges:
1. HSV ranges are saved to `ball_color_config.json`
2. Next time you run analysis, it will automatically use these ranges
3. No need to reconfigure unless you change balls

## Example Workflow

1. **Practice with red/white ball**:
   - Use default (no config needed)

2. **Practice with pink/white ball**:
   - Open Ball Color Helper
   - Load video frame
   - Sample white part → Click "Sample" for Color 1, click on white
   - Sample pink part → Click "Sample" for Color 2, click on pink
   - Click "Apply to Analysis"
   - Process video (uses pink/white detection)

3. **Next practice with blue/yellow ball**:
   - Open Ball Color Helper
   - Load preset "Blue Yellow" (if saved)
   - Or sample colors again
   - Apply to analysis

---

**Quick Tip**: Save presets for each ball type you use. Switch between them easily!


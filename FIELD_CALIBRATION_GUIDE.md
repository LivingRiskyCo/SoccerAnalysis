# Field Calibration Screenshot Recommendations

## Overview

Field calibration converts video pixel coordinates to real-world field coordinates (meters). This is essential for:
- **Accurate ball tracking** (filtering out sideline balls)
- **Speed calculations** (km/h, mph)
- **Distance measurements** (meters, miles)
- **Field coverage heatmaps**

## Best Screenshot Characteristics

### ✅ **Ideal Screenshot**

1. **Full Field Visible**
   - All 4 corners of the field should be clearly visible in the frame
   - No corners cut off or outside the frame
   - Field boundaries (lines) should be visible

2. **Clear Field Corners**
   - Field corners should be clearly defined (not blurred)
   - Field lines should be visible at corners
   - Minimal or no players/objects blocking corner areas

3. **Good Lighting**
   - Consistent lighting across the entire field
   - No harsh shadows obscuring field lines
   - Field lines should be clearly visible (white lines on green field)

4. **Minimal Obstructions**
   - Avoid frames with players standing directly on corner markers
   - Choose a frame with players in center field or away from corners
   - Ball should not be blocking corner visibility

5. **Stable Camera Position**
   - Use a frame from the same camera position as your analysis video
   - If camera moves during video, use a frame representative of the main camera position
   - Avoid frames with camera shake or motion blur

### 📸 **How to Capture the Screenshot**

1. **From Video:**
   - Pause your video at the best frame (full field visible)
   - Use video player's screenshot function (or Windows Snipping Tool)
   - Save as JPG or PNG format

2. **From Live Camera:**
   - Position camera at your typical recording location
   - Wait for a moment when field is clear of obstructions
   - Take screenshot/snapshot

3. **Best Timing:**
   - **Before game starts** - Field is empty, corners clearly visible
   - **During warm-up** - Players usually in center, corners clear
   - **Between plays** - Brief moments when field corners are unobstructed

### 🎯 **What to Look For**

**Good Screenshot:**
- ✅ All 4 field corners clearly visible
- ✅ Field lines visible and sharp
- ✅ Minimal players near corners
- ✅ Good contrast (white lines on green field)
- ✅ Consistent lighting

**Poor Screenshot:**
- ❌ Corners cut off or outside frame
- ❌ Players/ball blocking corner markers
- ❌ Blurry or motion-blurred field lines
- ❌ Harsh shadows obscuring field boundaries
- ❌ Camera angle too extreme (too close, too far, too angled)

### 📐 **Field Dimensions**

**Common Indoor Field Sizes:**
- **Small Indoor**: 30m x 15m (98ft x 49ft)
- **Standard Indoor**: 40m x 20m (131ft x 66ft) - **Default**
- **Large Indoor**: 50m x 25m (164ft x 82ft)

**Outdoor Field Sizes:**
- **Youth**: 50m x 30m (164ft x 98ft)
- **Full Size**: 105m x 68m (344ft x 223ft)

**How to Measure:**
- Check facility specifications
- Use measuring tape/wheel
- Ask facility manager
- Use online field size references

### 🔧 **Calibration Modes**

**4-Point Mode (Recommended for Most Cases):**
- Click 4 corners: Top-Left, Top-Right, Bottom-Right, Bottom-Left
- Faster and simpler
- Works well for rectangular fields
- Good for overhead or slightly angled views

**8-Point Mode (Better for Trapezoidal/Perspective Views):**
- Click 4 corners first, then 4 mid-points (top, right, bottom, left edges)
- More accurate for angled camera views
- Better for perspective correction
- Use when field appears trapezoidal in video

### 💡 **Tips for Best Results**

1. **Multiple Screenshots:**
   - Take 2-3 screenshots from different moments
   - Choose the one with clearest corners
   - Save backup screenshots for re-calibration

2. **Corner Visibility Priority:**
   - If you must choose, prioritize corner visibility over player positions
   - You can always re-calibrate if needed

3. **Camera Position Consistency:**
   - Use screenshot from same camera position as analysis video
   - If camera moves, use frame from most common position

4. **Field Line Quality:**
   - Ensure field lines are visible and sharp
   - If lines are faded, try adjusting screenshot brightness/contrast
   - Use frame with best line visibility

5. **Test Calibration:**
   - After calibrating, use "Preview transformation" option
   - Verify the top-down view looks correct
   - Re-calibrate if transformation looks distorted

### ⚠️ **Common Mistakes to Avoid**

1. **Using Frame with Players on Corners**
   - Makes it hard to click exact corner points
   - Can lead to inaccurate calibration

2. **Using Blurry Frame**
   - Motion blur makes corner points hard to identify
   - Choose a frame with minimal motion

3. **Wrong Field Dimensions**
   - Double-check your field size in meters
   - Wrong dimensions = wrong speed/distance calculations

4. **Camera Angle Too Extreme**
   - Very angled views make calibration less accurate
   - Try to use frame with more overhead perspective

5. **Inconsistent Camera Position**
   - Using screenshot from different camera position than analysis video
   - Calibration won't match video perspective

### 🔄 **When to Re-Calibrate**

Re-calibrate if:
- Camera position changes significantly
- Field dimensions are incorrect
- Ball tracking is excluding valid field areas
- Speed calculations seem wrong
- Field coverage heatmap looks distorted
- You move to a different venue

### 📝 **Quick Checklist**

Before calibrating, ensure your screenshot has:
- [ ] All 4 field corners visible
- [ ] Field lines clearly visible
- [ ] Minimal obstructions near corners
- [ ] Good lighting and contrast
- [ ] Sharp, non-blurry image
- [ ] Same camera position as analysis video
- [ ] Correct field dimensions ready (length x width in meters)

---

## Example Workflow

1. **Record/Pause Video** → Find frame with full field visible
2. **Take Screenshot** → Save as `field_calibration.jpg`
3. **Open GUI** → Click "Calibrate Field"
4. **Select Image** → Choose your screenshot
5. **Enter Dimensions** → e.g., 40m x 20m for indoor
6. **Click Corners** → Follow on-screen instructions
7. **Preview** → Verify transformation looks correct
8. **Done!** → Calibration saved automatically

---

**Note**: You only need to calibrate once per venue/camera position. The calibration file (`calibration.npy` and `field_calibration.json`) will be used for all future analyses until you re-calibrate.


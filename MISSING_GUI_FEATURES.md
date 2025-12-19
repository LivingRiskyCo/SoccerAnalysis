# Missing GUI Features

This document lists features and parameters that are available in the code but are **not currently exposed in the GUI**.

## Tracking Features

### 1. **Optical Flow** (`use_optical_flow`)
- **Status**: Available in code, stored in project_manager, but NO GUI control
- **Description**: Uses optical flow for motion prediction to reduce tracking blinking
- **Default**: `False`
- **Impact**: Adds ~5-10% processing overhead when enabled
- **Location in code**: `combined_analysis_optimized.py` line 5345
- **Project Manager**: Stored in `project_manager.py` but not exposed in GUI

### 2. **Velocity Constraints** (`enable_velocity_constraints`)
- **Status**: Available in code but hardcoded to `True`, NO GUI control
- **Description**: Enable velocity constraints to prevent impossible jumps
- **Default**: `True` (hardcoded)
- **Location in code**: `combined_analysis_optimized.py` line 5347
- **Note**: Always enabled, cannot be disabled via GUI

## Preview Mode Settings

### 3. **Preview Mode** (`preview_mode`, `preview_max_frames`)
- **Status**: Used internally for preview but not as a user-configurable setting
- **Description**: Process only a small sample of frames for quick testing
- **Default**: `False` (preview mode), `360` frames (15 seconds at 24fps)
- **Location in code**: `combined_analysis_optimized.py` lines 5387-5390
- **Note**: Currently only used for the preview button, not as a persistent setting

## Advanced Graphics Features (Partially Exposed)

### 4. **Text Effects** (Some missing)
- **Status**: Most are exposed, but some advanced combinations may not be fully accessible
- **Available in GUI**:
  - `enable_text_gradient` ✓
  - `enable_text_glow` ✓
  - `enable_text_pulse` ✓
  - `enable_glow_pulse` ✓
  - `enable_color_shift` ✓
- **All appear to be exposed in the Graphics Quality tab**

## Recommendations

### High Priority
1. **Add Optical Flow Toggle** - ✅ **IMPLEMENTED**
   - Added checkbox in Tracking Settings tab (row 28)
   - Placed in "Advanced Tracking Features" section
   - Location: After Adaptive Confidence, before Velocity Constraints

2. **Add Velocity Constraints Toggle** - ✅ **IMPLEMENTED**
   - Added checkbox in Tracking Settings tab (row 29)
   - Placed in "Advanced Tracking Features" section
   - Default: Enabled (True) - recommended setting

### Medium Priority
3. **Make Preview Mode Configurable** - ✅ **IMPLEMENTED**
   - Added spinbox for `preview_max_frames` near Preview button
   - Range: 60-1800 frames (increments of 60)
   - Default: 360 frames (15 seconds at 24fps)
   - Location: Right panel, below Preview button

### Low Priority
4. **Review Advanced Graphics Settings** - Verify all text/graphics effects are properly exposed
   - Most appear to be available, but worth double-checking

## Notes

- ✅ All high-priority missing features have been implemented
- Most major features ARE exposed in the GUI
- The previously missing features are now available:
  - Optical Flow toggle in Tracking Settings
  - Velocity Constraints toggle in Tracking Settings  
  - Preview frame count configurable in Analysis Controls
- All settings are saved/loaded via project_manager

## Code Locations

- **Function signature**: `combined_analysis_optimized.py` lines 5325-5453
- **GUI variable definitions**: `soccer_analysis_gui.py` lines 88-252
- **Function call**: `soccer_analysis_gui.py` lines 2800-2970
- **Project manager storage**: `project_manager.py` lines 179, 555


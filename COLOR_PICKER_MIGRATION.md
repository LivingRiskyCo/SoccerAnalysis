# Color Picker Migration Guide

This document tracks the migration from RGB spinboxes to color picker dialogs throughout the application.

## Status: IN PROGRESS

### Completed:
- ✅ Created `color_picker_utils.py` with reusable color picker widget
- ✅ Updated variable declarations for analytics colors (StringVar format)
- ✅ Updated variable declarations for box colors (StringVar format)
- ✅ Updated variable declarations for label colors (StringVar format)
- ✅ Updated variable declarations for statistics colors (StringVar format)
- ✅ Replaced analytics color spinboxes with color picker
- ✅ Replaced analytics title color spinboxes with color picker

### Remaining:
- ⏳ Replace box color spinboxes with color picker
- ⏳ Replace label color spinboxes with color picker
- ⏳ Replace statistics color spinboxes with color picker
- ⏳ Update all `.get()` calls to parse RGB string format
- ⏳ Update `preview_box_color()` function
- ⏳ Update `preview_label_color()` function
- ⏳ Update `_get_label_color()` function
- ⏳ Update project save/load functions
- ⏳ Update playback_viewer.py RGB inputs
- ⏳ Update setup_wizard.py RGB inputs
- ⏳ Update player_gallery_seeder.py RGB inputs

## Helper Functions Needed

```python
def parse_rgb_string(rgb_str: str, default: Tuple[int, int, int] = (255, 255, 255)) -> Tuple[int, int, int]:
    """Parse RGB string "R,G,B" to tuple (R, G, B)"""
    try:
        parts = rgb_str.split(',')
        if len(parts) == 3:
            return tuple([int(x.strip()) for x in parts])
    except Exception:
        pass
    return default
```

## Migration Pattern

**Before:**
```python
self.box_color_r = tk.IntVar(value=0)
self.box_color_g = tk.IntVar(value=255)
self.box_color_b = tk.IntVar(value=0)
# ... spinboxes ...
r = self.box_color_r.get()
g = self.box_color_g.get()
b = self.box_color_b.get()
```

**After:**
```python
self.box_color_rgb = tk.StringVar(value="0,255,0")
# ... color picker widget ...
from color_picker_utils import rgb_string_to_tuple
r, g, b = rgb_string_to_tuple(self.box_color_rgb.get(), default=(0, 255, 0))
```


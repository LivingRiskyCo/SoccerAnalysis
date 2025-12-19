# Per-Player Visualization Settings Guide

## Overview
Players can now have custom visualization settings (colors, effects, etc.) that override global settings. These settings can be edited via:
1. **CSV Import/Export** (Quick & Easy)
2. **Roster Management UI** (Interactive)
3. **Player Gallery** (Persistent storage)

## CSV Format

### Basic Roster CSV
```csv
name,jersey_number,team,position,active
John Doe,10,Blue,Forward,True
Jane Smith,5,Gray,Defender,True
```

### With Visualization Settings
```csv
name,jersey_number,team,position,active,custom_color,box_color,label_color,box_thickness,show_glow,glow_color,glow_intensity,show_trail,trail_color,trail_length,label_style
John Doe,10,Blue,Forward,True,255,0,0,3,True,255,100,50,True,255,0,0,30,full_name
Jane Smith,5,Gray,Defender,True,0,255,0,2,False,,,,False,,,jersey
```

### Color Formats
- **RGB format**: `R,G,B` (e.g., `255,0,0` for red)
- **Hex format**: `#RRGGBB` (e.g., `#FF0000` for red)
- **Empty**: Leave blank to use default/team color

### Visualization Columns

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| `custom_color` | RGB/Hex | Primary player color (overrides team color) | `255,0,0` or `#FF0000` |
| `box_color` | RGB/Hex | Bounding box color override | `255,0,0` |
| `label_color` | RGB/Hex | Label text color override | `255,255,255` |
| `box_thickness` | Integer | Box border thickness (1-10) | `3` |
| `show_glow` | Boolean | Enable glow effect | `True` or `False` |
| `glow_color` | RGB/Hex | Glow effect color | `255,255,0` |
| `glow_intensity` | Integer | Glow intensity (0-100) | `50` |
| `show_trail` | Boolean | Show movement trail | `True` or `False` |
| `trail_color` | RGB/Hex | Trail color | `255,0,0` |
| `trail_length` | Integer | Trail length in frames (1-100) | `30` |
| `label_style` | String | Label display style | `full_name`, `jersey`, `initials`, `number` |

### Label Styles
- `full_name`: Display full player name
- `jersey`: Display jersey number only
- `initials`: Display player initials
- `number`: Display track ID number

## Usage Examples

### Example 1: Simple Color Override
```csv
name,team,custom_color
John Doe,Blue,255,0,0
```
This makes John Doe always appear in red, regardless of team color.

### Example 2: Full Customization
```csv
name,team,custom_color,box_thickness,show_glow,glow_color,glow_intensity,show_trail,trail_color,trail_length
Star Player,Blue,255,215,0,5,True,255,255,0,75,True,255,215,0,50
```
This creates a golden player with:
- Thick box (5px)
- Yellow glow at 75% intensity
- Golden trail showing last 50 frames

### Example 3: Minimal Settings
```csv
name,team,box_thickness,label_style
John Doe,Blue,4,jersey
```
This only overrides box thickness and label style, keeping team colors.

## Import/Export

### Export Roster with Visualization
```python
from team_roster_manager import TeamRosterManager

manager = TeamRosterManager()
manager.export_to_csv("roster_with_viz.csv", include_visualization=True)
```

### Import Roster with Visualization
```python
from team_roster_manager import TeamRosterManager

manager = TeamRosterManager()
count = manager.import_from_csv("roster_with_viz.csv")
print(f"Imported {count} players with visualization settings")
```

## Priority Order

When rendering, per-player settings are checked in this order:
1. **Roster Manager** (highest priority - video-specific)
2. **Player Gallery** (persistent across videos)
3. **Global Settings** (fallback)

## Tips

1. **Start Simple**: Begin with just `custom_color` to test
2. **Use RGB Format**: `R,G,B` is easier to edit than hex
3. **Export First**: Export your current roster to see the format
4. **Test in Playback**: Use playback viewer to see changes immediately
5. **Save Often**: Changes are saved automatically in roster management UI

## Troubleshooting

**Colors not showing?**
- Check that `custom_color` is in RGB format: `R,G,B`
- Verify player name matches exactly (case-sensitive)
- Check that `use_custom_color` is set (auto-set when `custom_color` is provided)

**Settings not persisting?**
- Ensure you're saving via roster management UI
- Check that CSV import completed successfully
- Verify player exists in both roster and gallery

**Performance issues?**
- Too many glow effects can slow rendering
- Long trails (100+ frames) may impact performance
- Consider disabling effects for large rosters


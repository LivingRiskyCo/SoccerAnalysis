# Application Assets

This directory contains the application icon and splash screen for the Soccer Video Analysis Tool.

## Files

- **soccer_analysis_icon.ico** - Windows icon file with multiple sizes (16x16, 32x32, 48x48, 64x64, 128x128, 256x256)
  - Used for taskbar icon and window title bar
  - Automatically loaded by the main window

- **splash_screen.png** - Splash screen image shown on application startup
  - 800x500 pixels
  - Shows application name, subtitle, and version
  - Automatically displayed for 2 seconds on startup

## Regenerating Assets

To regenerate the icon and splash screen:

```bash
python create_assets.py
```

This will create:
- `soccer_analysis_icon.ico` in the root directory
- `splash_screen.png` in the root directory

## Integration

The assets are automatically integrated:

1. **Icon**: Set via `_set_window_icon()` in `main_window.py`
   - Searches multiple locations for the icon file
   - Falls back gracefully if icon not found

2. **Splash Screen**: Shown via `splash_screen.py` utility
   - Displayed on application startup
   - Automatically closes after 2 seconds
   - Falls back to text-based splash if image not found

## Customization

To customize the assets:

1. Edit `create_assets.py` to change:
   - Colors (green field, white ball)
   - Text content
   - Image dimensions
   - Fonts

2. Run `python create_assets.py` to regenerate

3. The application will automatically use the new assets on next launch


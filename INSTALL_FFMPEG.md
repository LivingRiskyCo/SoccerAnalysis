# Installing FFmpeg for Audio Preservation

## Why FFmpeg?
OpenCV's VideoWriter doesn't preserve audio. FFmpeg merges the original audio back into the processed video.

## Option 1: Manual Installation (No Admin Required - Recommended)

1. **Download FFmpeg for Windows:**
   - Go to: https://www.gyan.dev/ffmpeg/builds/
   - Download "ffmpeg-release-essentials.zip" (or latest build)
   - Or direct link: https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip

2. **Extract and Copy:**
   - Extract the ZIP file
   - Find `ffmpeg.exe` in the `bin` folder
   - Copy `ffmpeg.exe` to your `soccer_analysis` folder (same folder as `soccer_analysis_gui.py`)

3. **Verify:**
   - Run: `python -c "import subprocess; subprocess.run(['ffmpeg.exe', '-version'])"`
   - Should show FFmpeg version info

That's it! The analysis script will automatically find and use it.

## Option 2: System-Wide Installation (Requires Admin)

1. **Open PowerShell as Administrator:**
   - Right-click PowerShell → "Run as Administrator"

2. **Run:**
   ```powershell
   choco install ffmpeg -y
   ```

3. **Verify:**
   - Close and reopen terminal
   - Run: `ffmpeg -version`

## Option 3: Use Chocolatey Without Admin (Custom Location)

```powershell
choco install ffmpeg -y --install-directory="C:\Users\nerdw\ffmpeg"
```

Then add that folder to your PATH or copy `ffmpeg.exe` to the soccer_analysis folder.

## After Installation

Once FFmpeg is installed, the analysis will automatically:
- ✅ Preserve audio from your original video
- ✅ Merge it with the processed video
- ✅ Show "✓ Audio merged successfully!" in the log

No configuration needed - it just works!


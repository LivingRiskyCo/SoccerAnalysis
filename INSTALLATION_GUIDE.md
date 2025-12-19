# Installation Guide - Soccer Analysis Software

## Required Software

### 1. Python 3.10 or Higher

**Download**: https://www.python.org/downloads/

**Installation Steps**:
1. Download Python 3.10+ (or latest version)
2. **IMPORTANT**: Check "Add Python to PATH" during installation
3. Run installer
4. Verify installation:
   ```powershell
   python --version
   ```
   Should show: `Python 3.10.x` or higher

**Note**: If you already have Python installed, check version first:
```powershell
python --version
```

---

### 2. Python Packages (via pip)

**After Python is installed**, install all required packages:

```powershell
# Navigate to project folder
cd C:\Users\nerdw\soccer_analysis

# Create virtual environment (recommended)
python -m venv env

# Activate virtual environment
env\Scripts\activate

# Install all packages
pip install -r requirements.txt
```

**What this installs**:
- `opencv-python` - Video processing
- `ultralytics` - YOLOv8 for player detection
- `defisheye` - Fisheye distortion correction
- `numpy` - Numerical operations
- `matplotlib` - Plotting and heatmaps
- `supervision` - Tracking and annotations
- `imutils` - Image utilities

**Installation time**: ~5-10 minutes (depending on internet speed)

---

### 3. FFmpeg (Optional but Recommended)

**For extracting test clips** from your practice videos.

**Download**: https://www.gyan.dev/ffmpeg/builds/

**Installation Steps**:
1. Download "ffmpeg-release-essentials.zip"
2. Extract to `C:\ffmpeg` (or any folder)
3. Add to PATH:
   - Open "Environment Variables" (search in Windows)
   - Edit "Path" under System Variables
   - Add: `C:\ffmpeg\bin`
   - Click OK
4. Restart PowerShell/Command Prompt
5. Verify:
   ```powershell
   ffmpeg -version
   ```

**Alternative**: Use Chocolatey (if installed):
```powershell
choco install ffmpeg
```

**Why needed**: For extracting short test clips:
```powershell
ffmpeg -i practice.mp4 -t 60 test_clip.mp4
```

---

## Optional Software

### 4. NVIDIA GPU Drivers + CUDA (Optional - for faster processing)

**Only if you have an NVIDIA graphics card** (speeds up YOLO ~2-3x)

1. **GPU Drivers**: Download from NVIDIA website
   - https://www.nvidia.com/Download/index.aspx
   - Enter your GPU model and download latest drivers

2. **CUDA Toolkit**: (Optional, for advanced GPU acceleration)
   - https://developer.nvidia.com/cuda-downloads
   - Ultralytics/YOLO will auto-detect GPU if available

**Note**: CPU-only processing works fine, just slower (1-2 hours vs 30-60 min for full video)

---

### 5. Video Player (Optional - for viewing results)

**Recommended**: VLC Media Player (free)
- https://www.videolan.org/vlc/
- Plays MP4 files reliably

Or use Windows Media Player (built-in).

---

## Quick Installation Checklist

### Step 1: Install Python
- [ ] Download Python 3.10+ from python.org
- [ ] Check "Add Python to PATH" during installation
- [ ] Verify: `python --version`

### Step 2: Install Python Packages
- [ ] Navigate to project folder: `cd C:\Users\nerdw\soccer_analysis`
- [ ] Create virtual environment: `python -m venv env`
- [ ] Activate: `env\Scripts\activate`
- [ ] Install packages: `pip install -r requirements.txt`
- [ ] Verify: `python -c "import cv2; print('OpenCV installed')"`

### Step 3: Install FFmpeg (Optional)
- [ ] Download from gyan.dev/ffmpeg
- [ ] Extract to `C:\ffmpeg`
- [ ] Add to PATH
- [ ] Verify: `ffmpeg -version`

### Step 4: Test Installation
- [ ] Run test: `python dewarp.py --help`
- [ ] Should show help message (no errors)

---

## Verification Commands

Run these commands to verify everything is installed:

```powershell
# Check Python
python --version

# Check pip
pip --version

# Check packages (after activating venv)
python -c "import cv2; print('OpenCV:', cv2.__version__)"
python -c "import ultralytics; print('Ultralytics installed')"
python -c "import defisheye; print('Defisheye installed')"
python -c "import supervision; print('Supervision installed')"

# Check FFmpeg (if installed)
ffmpeg -version
```

---

## Troubleshooting

### "python is not recognized"
- **Solution**: Python not in PATH
- Reinstall Python and check "Add Python to PATH"
- Or manually add Python to PATH

### "pip is not recognized"
- **Solution**: pip comes with Python
- Try: `python -m pip install -r requirements.txt`

### "Module not found" errors
- **Solution**: Virtual environment not activated
- Run: `env\Scripts\activate` before running scripts

### "ffmpeg is not recognized"
- **Solution**: FFmpeg not in PATH or not installed
- Either add to PATH or skip (not required, just convenient)

### Installation fails for specific package
- **Solution**: Try installing individually:
  ```powershell
  pip install opencv-python
  pip install ultralytics
  pip install defisheye
  # etc...
  ```

### GPU not detected (YOLO still works on CPU)
- **Solution**: GPU acceleration is optional
- Scripts will work on CPU (just slower)
- Install NVIDIA drivers if you have NVIDIA GPU

---

## Minimum System Requirements

- **OS**: Windows 10/11 (or Linux/Mac)
- **RAM**: 8GB minimum, 16GB recommended
- **CPU**: Intel i5 / AMD Ryzen 5 or better
- **Storage**: 5-10GB free space (for packages + videos)
- **GPU**: Optional (NVIDIA GPU for faster processing)

---

## Installation Time Estimate

- **Python**: 5-10 minutes
- **Python packages**: 5-10 minutes (download + install)
- **FFmpeg**: 5-10 minutes (optional)
- **GPU drivers**: 10-15 minutes (optional, only if you have NVIDIA GPU)

**Total**: ~15-30 minutes for basic setup

---

## First Run After Installation

After installing everything, test with a sample video:

```powershell
# Navigate to project
cd C:\Users\nerdw\soccer_analysis

# Activate virtual environment
env\Scripts\activate

# Test dewarping (replace with your video path)
python dewarp.py --input your_video.mp4 --output test_output.mp4
```

**Note**: YOLO weights will download automatically on first run (~6MB).

---

## Need Help?

If you encounter issues:
1. Check Python version: `python --version` (needs 3.10+)
2. Verify virtual environment is activated (should see `(env)` in prompt)
3. Check all packages installed: `pip list`
4. Try running individual scripts to see specific error messages



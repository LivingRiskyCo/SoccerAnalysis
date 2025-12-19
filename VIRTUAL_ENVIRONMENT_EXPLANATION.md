# Virtual Environment Explanation

## Why is the GUI using a virtual environment?

The GUI is using a virtual environment because of the `run_gui.bat` file, which activates the `env` virtual environment before launching the GUI.

**Current setup:**
- `run_gui.bat` activates `env\Scripts\activate`
- Then runs `python soccer_analysis_gui.py`
- This ensures all dependencies are isolated in the `env` folder

## Should you use a virtual environment?

### ✅ **YES - Recommended (Current Setup)**

**Advantages:**
- **Isolation**: Dependencies don't conflict with other Python projects
- **Clean**: Easy to delete and recreate if something breaks
- **Reproducible**: Same environment every time
- **Professional**: Standard practice for Python projects

**Disadvantages:**
- Need to install packages in the venv (not system Python)
- Slightly more setup

### ❌ **NO - System Python (Alternative)**

**Advantages:**
- Simpler: Just run `python soccer_analysis_gui.py`
- Packages installed once for all projects

**Disadvantages:**
- **Dependency conflicts**: Different projects need different package versions
- **Harder to manage**: Can't easily reset if something breaks
- **System pollution**: Installs packages globally

## How to switch between options

### Option 1: Keep using virtual environment (Recommended)

**Current setup is fine!** Just make sure to:
- Install packages in the venv: `.\env\Scripts\python.exe -m pip install <package>`
- Use `run_gui.bat` to launch the GUI

**Status**: ✅ BoxMOT is now installed in your venv, so this should work!

### Option 2: Use system Python instead

**Step 1**: Install BoxMOT in system Python (if not already):
```bash
python -m pip install boxmot
```

**Step 2**: Create a new launcher that doesn't use venv:

**Create `run_gui_system.bat`:**
```batch
@echo off
REM Launch GUI using system Python (no virtual environment)
cd /d "%~dp0"
python soccer_analysis_gui.py
pause
```

**Step 3**: Use `run_gui_system.bat` instead of `run_gui.bat`

### Option 3: Modify existing batch file

**Edit `run_gui.bat`** to comment out the venv activation:

```batch
@echo off
REM Quick launcher for Soccer Analysis GUI
cd /d "%~dp0"
REM call env\Scripts\activate  <-- Comment this out
python soccer_analysis_gui.py
pause
```

## Recommendation

**Keep using the virtual environment!** It's the better practice. You've already installed BoxMOT in the venv, so everything should work now.

Just make sure to:
1. Always use `run_gui.bat` to launch (or activate venv manually)
2. Install new packages in the venv: `.\env\Scripts\python.exe -m pip install <package>`

## Quick Check

To verify which Python the GUI will use:

**With venv (current):**
```bash
.\env\Scripts\python.exe -c "import sys; print(sys.executable)"
# Should show: C:\Users\nerdw\soccer_analysis\env\Scripts\python.exe
```

**Without venv (system):**
```bash
python -c "import sys; print(sys.executable)"
# Should show: C:\Users\nerdw\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.13_...\python.exe
```

## Summary

- **Current setup**: Virtual environment (via `run_gui.bat`)
- **Why**: Isolation and best practices
- **Status**: ✅ BoxMOT installed in venv, ready to use
- **Action**: Just restart GUI using `run_gui.bat`

If you want to switch to system Python, follow Option 2 or 3 above.


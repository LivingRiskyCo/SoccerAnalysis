# Checking BoxMOT in GUI

## Issue
BoxMOT tracker options not showing in GUI dropdown.

## Solution

### 1. Restart the GUI
**The GUI must be restarted** after installing BoxMOT for it to detect the new options.

Close and reopen the GUI application.

### 2. Check Console Output
When you start the GUI, you should see in the console:
```
✓ BoxMOT detection in GUI: True
✓ BoxMOT trackers available: ['bytetrack', 'ocsort', 'deepocsort', 'strongsort', 'botsort']
```

If you see:
```
⚠ BoxMOT not available in GUI: [error message]
⚠ BoxMOT not available, showing standard trackers only: ['bytetrack', 'ocsort']
```

Then BoxMOT isn't being detected. See troubleshooting below.

### 3. Verify BoxMOT Installation
Run this command to verify BoxMOT is installed:
```bash
python -c "from boxmot import DeepOcSort; print('BoxMOT works!')"
```

If this fails, BoxMOT isn't installed correctly.

### 4. Where to Find Tracker Options
In the GUI:
1. Go to **"Player Tracking Settings"** section
2. Find **"Tracker Type"** dropdown (row 4)
3. Click the dropdown - you should see:
   - `bytetrack`
   - `ocsort`
   - `deepocsort` ⭐ (if BoxMOT available)
   - `strongsort` ⭐ (if BoxMOT available)
   - `botsort` ⭐ (if BoxMOT available)

### 5. Troubleshooting

**If options still don't appear:**

1. **Check Python Environment**
   - Make sure you're using the same Python environment where BoxMOT was installed
   - If using a virtual environment, activate it before running GUI

2. **Check Import Path**
   - The GUI tries to import `boxmot_tracker_wrapper.py`
   - Make sure this file is in the same directory as `soccer_analysis_gui.py`

3. **Check Console for Errors**
   - Look for import errors in the console output
   - The GUI now prints diagnostic messages

4. **Manual Test**
   Run this to test BoxMOT detection:
   ```python
   import sys
   import os
   sys.path.insert(0, os.path.dirname(os.path.abspath('.')))
   from boxmot_tracker_wrapper import BOXMOT_AVAILABLE
   print('BoxMOT Available:', BOXMOT_AVAILABLE)
   ```

## Expected Behavior

**With BoxMOT installed:**
- Dropdown shows 5 options: `bytetrack`, `ocsort`, `deepocsort`, `strongsort`, `botsort`
- Help text says: "(DeepOCSORT/StrongSORT: best for occlusions, ByteTrack: fastest, OC-SORT: balanced)"

**Without BoxMOT:**
- Dropdown shows 2 options: `bytetrack`, `ocsort`
- Help text says: "(OC-SORT: better for scrums/bunched players, ByteTrack: faster for open play)"

## Still Not Working?

If you've restarted the GUI and still don't see the options:
1. Check the console output for error messages
2. Verify BoxMOT installation: `pip list | findstr boxmot`
3. Try running the GUI from command line to see full error messages


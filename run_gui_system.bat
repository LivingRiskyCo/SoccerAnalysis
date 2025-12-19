@echo off
REM Launch GUI using system Python (no virtual environment)
REM Use this if you want to use system Python instead of the virtual environment
cd /d "%~dp0"
python soccer_analysis_gui.py
pause


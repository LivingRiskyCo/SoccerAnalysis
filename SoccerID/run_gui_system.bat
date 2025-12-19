@echo off
REM Launch SoccerID GUI using system Python (no virtual environment)
REM Use this if you want to use system Python instead of the virtual environment
cd /d "%~dp0"
cd ..
python -m SoccerID.main
pause


@echo off
REM Launch SoccerID GUI using system Python (no virtual environment)
REM This matches the old behavior - runs directly without venv
cd /d "%~dp0"
python -m SoccerID.main
pause


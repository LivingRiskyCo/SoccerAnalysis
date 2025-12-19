@echo off
REM Quick launcher for Soccer Analysis GUI
REM This version uses virtual environment (if you have one)
REM For system Python (like the old version), use run_gui_system.bat instead
cd /d "%~dp0"
if exist "..\env\Scripts\activate.bat" (
    call ..\env\Scripts\activate
    python main.py
) else (
    echo Virtual environment not found. Using system Python...
    cd ..
    python -m SoccerID.main
)
pause



@echo off
REM Install all required packages from parent directory
echo Installing required packages...
cd /d "%~dp0"
cd ..

REM Check if virtual environment exists
if exist "env\Scripts\activate.bat" (
    echo Activating virtual environment...
    call env\Scripts\activate
    echo Virtual environment activated.
) else (
    echo No virtual environment found. Using system Python.
    echo Note: You may need administrator rights or use --user flag.
)

echo.
echo Installing packages from requirements.txt...
if exist "requirements.txt" (
    pip install -r requirements.txt
) else (
    echo ERROR: requirements.txt not found in parent directory.
    echo Current directory: %CD%
    pause
    exit /b 1
)
echo.
echo Installation complete!
pause


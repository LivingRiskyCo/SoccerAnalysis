@echo off
REM Batch script to add Python Scripts directory to PATH
REM Run this script as Administrator

set "SCRIPTS_PATH=C:\Users\nerdw\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\LocalCache\local-packages\Python313\Scripts"

REM Check if path already exists in user PATH
for /f "tokens=2*" %%A in ('reg query "HKCU\Environment" /v Path 2^>nul') do set "CURRENT_PATH=%%B"

echo %CURRENT_PATH% | findstr /C:"%SCRIPTS_PATH%" >nul
if %ERRORLEVEL% EQU 0 (
    echo ✓ Python Scripts directory is already in PATH
) else (
    REM Add to user PATH
    setx PATH "%CURRENT_PATH%;%SCRIPTS_PATH%" >nul
    echo ✓ Added Python Scripts directory to PATH
    echo   Path: %SCRIPTS_PATH%
    echo.
    echo ⚠ Please restart your terminal/IDE for changes to take effect
)

pause


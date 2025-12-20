@echo off
echo ========================================
echo Installing PaddleOCR
echo ========================================
echo.
echo WARNING: This will close any running Python processes!
echo Press Ctrl+C to cancel, or any key to continue...
pause >nul

echo.
echo Step 1: Closing Python processes...
taskkill /F /IM python.exe /T 2>nul
taskkill /F /IM pythonw.exe /T 2>nul
timeout /t 2 /nobreak >nul

echo.
echo Step 2: Uninstalling conflicting OpenCV packages...
pip uninstall -y opencv-python opencv-python-headless 2>nul

echo.
echo Step 3: Installing paddlepaddle and paddleocr...
echo This may take 5-10 minutes...
pip install --user --no-cache-dir paddlepaddle paddleocr

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo ✓ Installation successful!
    echo ========================================
) else (
    echo.
    echo ========================================
    echo ✗ Installation failed
    echo ========================================
    echo.
    echo Try running as Administrator or use:
    echo   pip install --user --force-reinstall --no-cache-dir paddlepaddle paddleocr
)

pause


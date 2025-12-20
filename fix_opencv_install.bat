@echo off
echo ========================================
echo Fixing OpenCV installation conflict
echo ========================================
echo.

echo Step 1: Closing any Python processes that might be using OpenCV...
taskkill /F /IM python.exe /T 2>nul
taskkill /F /IM pythonw.exe /T 2>nul
timeout /t 2 /nobreak >nul

echo.
echo Step 2: Uninstalling conflicting OpenCV packages...
pip uninstall -y opencv-python opencv-python-headless opencv-contrib-python 2>nul

echo.
echo Step 3: Installing paddlepaddle and paddleocr...
echo This may take several minutes...
pip install --user --no-cache-dir paddlepaddle paddleocr

echo.
echo ========================================
echo Installation complete!
echo ========================================
pause


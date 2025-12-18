@echo off
REM Install all required packages in the virtual environment
echo Installing required packages...
cd /d "%~dp0"
call env\Scripts\activate
echo Virtual environment activated.
echo.
echo Installing packages from requirements.txt...
pip install -r requirements.txt
echo.
echo Installation complete!
pause


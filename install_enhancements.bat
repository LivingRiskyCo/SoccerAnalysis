@echo off
REM Install optional enhancements for soccer analysis
echo Installing optional enhancements...
echo.

cd /d "%~dp0"
call env\Scripts\activate

echo Installing data analysis packages...
pip install pandas seaborn jupyter notebook plotly

echo.
echo Installing video utilities...
pip install moviepy

echo.
echo Installing enhanced tracking packages (optional)...
pip install sportslabkit soccer-cv databallpy

echo.
echo Installation complete!
echo.
echo Installed packages:
echo - pandas: Data analysis
echo - seaborn: Statistical visualizations
echo - jupyter: Interactive notebooks
echo - plotly: Interactive charts
echo - moviepy: Video editing in Python
echo - sportslabkit: Advanced tracking algorithms
echo - soccer-cv: Soccer-specific visualization
echo - databallpy: Soccer metrics framework
echo.
pause



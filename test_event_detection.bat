@echo off
REM Test event detection on CSV tracking files
REM Usage: test_event_detection.bat [csv_file] [options]

if "%1"=="" (
    echo.
    echo Event Detection Test
    echo ====================
    echo.
    echo Usage: test_event_detection.bat [csv_file] [options]
    echo.
    echo Examples:
    echo   test_event_detection.bat video_analyzed_tracking_data.csv
    echo   test_event_detection.bat video_analyzed_tracking_data.csv --min-confidence 0.3
    echo   test_event_detection.bat video_analyzed_tracking_data.csv --export
    echo.
    echo Options:
    echo   --min-confidence 0.3    Lower threshold for more detections
    echo   --min-ball-speed 2.0     Lower ball speed requirement
    echo   --min-pass-distance 3.0  Lower pass distance requirement
    echo   --export                 Export events to CSV
    echo.
    echo See EVENT_DETECTION_GUIDE.md for full documentation
    echo.
    pause
    exit /b 1
)

REM Activate virtual environment if it exists
if exist "env\Scripts\activate.bat" (
    call env\Scripts\activate.bat
)

REM Run the test script
python test_event_detection.py %*

if errorlevel 1 (
    echo.
    echo Error occurred. Check the output above for details.
    pause
    exit /b 1
)


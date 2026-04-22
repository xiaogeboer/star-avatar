@echo off
cd /d "%~dp0"
echo ========================================
echo   Sports Avatar Downloader - Web UI
echo ========================================
echo.
echo   Starting server...
echo   Browser will open automatically.
echo   Press Ctrl+C to stop.
echo.
python web_server.py
if errorlevel 1 (
    echo.
    echo Python not found. Trying python3...
    python3 web_server.py
)
pause

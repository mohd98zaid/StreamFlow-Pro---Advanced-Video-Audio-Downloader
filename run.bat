@echo off
title Video Downloader
cd /d "%~dp0"

:: Check if virtual environment exists in venv or .venv folder
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

echo Starting Video Downloader...
python main.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo An error occurred while running the application.
    pause
)

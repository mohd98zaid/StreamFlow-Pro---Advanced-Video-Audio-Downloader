@echo off
title StreamFlow Pro Launcher
cd /d "%~dp0"

:: Check if virtual environment exists in venv or .venv folder
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

:: Check direct command line arguments (e.g. run.bat player or run.bat 2)
if /i "%1"=="downloader" goto launch_downloader
if /i "%1"=="1" goto launch_downloader
if /i "%1"=="player" goto launch_player
if /i "%1"=="2" goto launch_player
if /i "%1"=="both" goto launch_both
if /i "%1"=="3" goto launch_both
if /i "%1"=="exit" goto exit_launcher
if /i "%1"=="4" goto exit_launcher

:menu
cls
echo ========================================================
echo               StreamFlow Pro Suite
echo ========================================================
echo.
echo   [1] Video Downloader (Main App)
echo   [2] YouTube Ad-Free Player
echo   [3] Launch Both (Downloader + Player)
echo   [4] Exit
echo.
echo ========================================================
set "choice="
set /p choice="Select an option [1-4] (Default: 1): "

if "%choice%"=="" set choice=1
if "%choice%"=="1" goto launch_downloader
if "%choice%"=="2" goto launch_player
if "%choice%"=="3" goto launch_both
if "%choice%"=="4" goto exit_launcher

echo.
echo [!] Invalid selection "%choice%". Please choose 1, 2, 3, or 4.
timeout /t 2 >nul
goto menu

:launch_downloader
echo.
echo Starting StreamFlow Video Downloader...
python main.py
goto handle_exit

:launch_player
echo.
echo Starting YouTube Ad-Free Player...
python utils\player_process.py "https://www.youtube.com" "YouTube Ad-Free Player"
goto handle_exit

:launch_both
echo.
echo Starting StreamFlow Video Downloader and YouTube Player...
start "StreamFlow Video Downloader" python main.py
python utils\player_process.py "https://www.youtube.com" "YouTube Ad-Free Player"
goto handle_exit

:handle_exit
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] An error occurred while running the application (Exit Code: %ERRORLEVEL%).
    pause
)

:exit_launcher

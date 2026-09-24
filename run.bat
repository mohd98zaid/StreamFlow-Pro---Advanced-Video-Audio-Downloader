@echo off
title StreamFlow Pro Launcher
cd /d "%~dp0"

:: Check if virtual environment exists in venv or .venv folder
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

:: Check direct command line arguments
if /i "%1"=="modern" goto launch_modern
if /i "%1"=="1" goto launch_modern
if /i "%1"=="player" goto launch_player
if /i "%1"=="2" goto launch_player
if /i "%1"=="classic" goto launch_classic
if /i "%1"=="3" goto launch_classic
if /i "%1"=="exit" goto exit_launcher
if /i "%1"=="4" goto exit_launcher

:menu
cls
echo ========================================================
echo               StreamFlow Pro Suite
echo ========================================================
echo.
echo   [1] StreamFlow Pro Modern (Tauri / React + Python) [Default]
echo   [2] YouTube Ad-Free Player (StreamFlow Yuma Studio)
echo   [3] StreamFlow Pro Classic (Legacy Tkinter GUI)
echo   [4] Exit
echo.
echo ========================================================
set "choice="
set /p choice="Select an option [1-4] (Default: 1): "

if "%choice%"=="" set choice=1
if "%choice%"=="1" goto launch_modern
if "%choice%"=="2" goto launch_player
if "%choice%"=="3" goto launch_classic
if "%choice%"=="4" goto exit_launcher

echo.
echo [!] Invalid selection "%choice%". Please choose 1, 2, 3, or 4.
timeout /t 2 >nul
goto menu

:launch_modern
echo.
echo Starting StreamFlow Pro Modern Interface...
python run_modern.py
goto handle_exit

:launch_player
echo.
echo Starting YouTube Ad-Free Player (Yuma Studio)...
python utils\player_process.py "https://www.youtube.com" "YouTube Ad-Free Player"
goto handle_exit

:launch_classic
echo.
echo Starting StreamFlow Pro Classic Tkinter GUI...
python main.py
goto handle_exit

:handle_exit
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] An error occurred while running the application (Exit Code: %ERRORLEVEL%).
    pause
)

:exit_launcher

@echo off
title StreamFlow Pro Launcher
cd /d "%~dp0"

:: Check if virtual environment exists in venv, .venv, or env folder
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else if exist "env\Scripts\activate.bat" (
    call env\Scripts\activate.bat
)

:: Detect Python executable (python or py)
where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    set "PYTHON_CMD=python"
) else (
    where py >nul 2>nul
    if %ERRORLEVEL% EQU 0 (
        set "PYTHON_CMD=py"
    ) else (
        echo.
        echo ========================================================
        echo  [!] ERROR: Python is not detected in your system PATH.
        echo      Please install Python (https://www.python.org/)
        echo      and ensure "Add Python to PATH" is checked.
        echo ========================================================
        echo.
        pause
        exit /b 1
    )
)

:: Check direct command line arguments
if /i "%1"=="modern" goto launch_modern
if /i "%1"=="m" goto launch_modern
if /i "%1"=="1" goto launch_modern

if /i "%1"=="player" goto launch_player
if /i "%1"=="p" goto launch_player
if /i "%1"=="2" goto launch_player

if /i "%1"=="classic" goto launch_classic
if /i "%1"=="c" goto launch_classic
if /i "%1"=="3" goto launch_classic

if /i "%1"=="exit" goto exit_launcher
if /i "%1"=="quit" goto exit_launcher
if /i "%1"=="q" goto exit_launcher
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

:: Strip whitespace
if defined choice set "choice=%choice: =%"

:: Handle selection and shortcuts
if "%choice%"=="" set choice=1
if /i "%choice%"=="1" goto launch_modern
if /i "%choice%"=="modern" goto launch_modern
if /i "%choice%"=="m" goto launch_modern

if /i "%choice%"=="2" goto launch_player
if /i "%choice%"=="player" goto launch_player
if /i "%choice%"=="p" goto launch_player

if /i "%choice%"=="3" goto launch_classic
if /i "%choice%"=="classic" goto launch_classic
if /i "%choice%"=="c" goto launch_classic

if /i "%choice%"=="4" goto exit_launcher
if /i "%choice%"=="exit" goto exit_launcher
if /i "%choice%"=="quit" goto exit_launcher
if /i "%choice%"=="q" goto exit_launcher

echo.
echo [!] Invalid selection "%choice%". Please choose 1, 2, 3, or 4.
timeout /t 2 >nul
goto menu

:launch_modern
echo.
echo Starting StreamFlow Pro Modern Interface...
%PYTHON_CMD% run_modern.py
goto handle_exit

:launch_player
echo.
echo Starting YouTube Ad-Free Player (Yuma Studio)...
%PYTHON_CMD% utils\player_process.py "https://www.youtube.com" "YouTube Ad-Free Player"
goto handle_exit

:launch_classic
echo.
echo Starting StreamFlow Pro Classic Tkinter GUI...
%PYTHON_CMD% main.py
goto handle_exit

:handle_exit
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] An error occurred while running the application (Exit Code: %ERRORLEVEL%).
    pause
)

:exit_launcher
exit /b 0

@echo off
setlocal
cd /d "%~dp0"
title Market Insight Setup

echo.
echo  MARKET INSIGHT
echo  ==============
echo.
py -3 --version >nul 2>&1
if errorlevel 1 (
    echo Python 3 was not found.
    echo Install Python 3.11 or newer from https://www.python.org/downloads/
    echo During installation, enable "Add Python to PATH".
    pause
    exit /b 1
)

echo Installing required packages. This may take a few minutes...
py -3 -m pip install --upgrade pip
if errorlevel 1 goto failed
py -3 -m pip install -r requirements.txt
if errorlevel 1 goto failed

echo.
echo Creating the Market Insight app icon...
py -3 generate_icon.py
if errorlevel 1 goto failed

echo.
echo Setup complete. Starting Market Insight...
start "" wscript.exe "%~dp0Start_Market_Insight.vbs"
exit /b 0

:failed
echo.
echo Setup could not finish. Check your internet connection and Python installation.
pause
exit /b 1

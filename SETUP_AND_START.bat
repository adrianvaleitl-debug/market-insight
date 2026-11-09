@echo off
setlocal
cd /d "%~dp0"
title Market Insight Setup

echo.
echo  MARKET INSIGHT
echo  ==============
echo.
echo Checking Python...
py -3 --version >nul 2>&1
if errorlevel 1 (
    echo Python 3 is required but was not found.
    echo Install Python from https://www.python.org/downloads/
    echo Then run this setup again.
    pause
    exit /b 1
)

echo Installing required components...
py -3 -m pip install -r requirements.txt --disable-pip-version-check --quiet
if errorlevel 1 goto failed

echo Starting Market Insight...
start "" wscript.exe "%~dp0Start_Market_Insight.vbs"
exit /b 0

:failed
echo.
echo Setup could not finish. Check your internet connection and Python installation.
pause
exit /b 1

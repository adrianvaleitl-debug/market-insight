@echo off
setlocal
cd /d "%~dp0\.."
title Market Insight - Startup Diagnostics
echo.
echo MARKET INSIGHT STARTUP DIAGNOSTICS
echo ==================================
echo.
echo Python version:
py -3 --version
echo.
echo Checking required packages...
py -3 -m pip show customtkinter yfinance pandas requests keyring Pillow
echo.
echo Starting Market Insight. Any error will appear below.
echo Close the app window normally to return here.
echo.
py -3 -u market_insight.py
echo.
echo Market Insight has stopped. If an error appeared above, copy it or take a screenshot.
pause

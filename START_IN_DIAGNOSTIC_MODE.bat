@echo off
setlocal
cd /d "%~dp0"
title Market Insight - Startup Diagnostics
echo.
echo MARKET INSIGHT STARTUP DIAGNOSTICS
echo ==================================
echo.
echo This starts the app in visible diagnostic mode.
echo Keep this window open if the app closes.
echo.
set MARKET_INSIGHT_DEBUG=1
py -3 -u market_insight.py
echo.
echo Market Insight has stopped. Any startup error should be shown above.
echo Check startup_error.log in this folder or %%APPDATA%%\Market Insight.
pause

@echo off
setlocal
cd /d "%~dp0"
echo Creating a desktop shortcut for Market Insight...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Create_Desktop_Shortcut.ps1"
if errorlevel 1 (
  echo Shortcut creation failed. You can still open Start_Market_Insight.vbs.
  pause
)

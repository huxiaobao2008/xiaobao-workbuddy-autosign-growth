@echo off
setlocal
title Buddy Gas Station - Launcher

cd /d "%~dp0"

set "PY="
if exist "C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12\python.exe" set "PY=C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12\python.exe"
if not defined PY if exist "D:\empire_tools\green_tools\python\python.exe" set "PY=D:\empire_tools\green_tools\python\python.exe"
if not defined PY for /f "delims=" %%i in ('where python 2^>nul') do if not defined PY set "PY=%%i"
if not defined PY (
  echo [ERROR] Python not found.
  pause
  exit /b 2
)

echo ==================================================
echo   Buddy Gas Station - Launcher
echo   Starts client + web UI only. Tasks do NOT auto-run.
echo ==================================================
echo.

echo [1/4] Stopping any old web server (frees port 8765)...
"%PY%" "%~dp0port_clean.py"
echo.

echo [2/4] Starting WorkBuddy client with CDP debug port...
start "" "%PY%" "%~dp0client_cdp.py" --restart --wait 120
echo       Client is launching (about 30-90s). Continuing...
echo.

echo [3/4] Starting local web management UI...
rem --no-open: this launcher opens the browser itself in step 4/4.
rem Without it the page would open TWICE (server also calls webbrowser.open).
start "" "%PY%" "%~dp0server.py" 8765 --no-open
timeout /t 4 >nul
echo.

echo [4/4] Opening browser...
start "" http://127.0.0.1:8765
echo.

echo ==================================================
echo   Ready. Nothing runs automatically.
echo.
echo   In the web page:
echo     - Choose mode: Manual or Auto (top left)
echo     - Manual: click an account, then "Run this account"
echo     - Auto  : click an account row to run it
echo     - "Run All" processes every account
echo     - "Stop Task" halts a run in progress (about 10s)
echo ==================================================
pause

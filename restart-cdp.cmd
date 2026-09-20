@echo off
setlocal
title WorkBuddy CDP restart

rem ---------------------------------------------------------------
rem  WorkBuddy client - close and reopen with CDP debug port 9222
rem  All text is intentionally ASCII-only: non-ASCII bytes get
rem  mis-decoded by cmd.exe (OEM codepage) and corrupt the script.
rem ---------------------------------------------------------------

set "PY="
if exist "C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12\python.exe" set "PY=C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12\python.exe"
if not defined PY if exist "D:\empire_tools\green_tools\python\python.exe" set "PY=D:\empire_tools\green_tools\python\python.exe"
if not defined PY for /f "delims=" %%i in ('where python 2^>nul') do if not defined PY set "PY=%%i"

if not defined PY goto nopython

echo ==================================================
echo   WorkBuddy client - restart with CDP debug port
echo.
echo   * The app will be closed and reopened.
echo   * Debug port: 9222, localhost only.
echo   * Takes about 30 to 90 seconds. Please wait.
echo ==================================================
echo.
echo Using Python: %PY%
echo.

"%PY%" "%~dp0client_cdp.py" --restart --wait 120
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" goto ok

echo [NOT READY] exit code = %RC%
echo Possible causes: security software blocked it, or the app failed to start.
echo Log file: %~dp0logs\client_cdp.log
goto end

:ok
echo [OK] CDP port is ready. You can go back to the chat.

:end
echo.
pause
exit /b

:nopython
echo [ERROR] Python not found.
echo Edit the PY line near the top of this file to point at python.exe.
echo.
pause
exit /b 2

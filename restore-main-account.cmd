@echo off
setlocal
title WorkBuddy - restore main account

rem ---------------------------------------------------------------
rem  Restore the client login to the MAIN account (account_a).
rem  Use this if the client ends up logged in as some other account.
rem  All text is intentionally ASCII-only: non-ASCII bytes get
rem  mis-decoded by cmd.exe (OEM codepage) and corrupt the script.
rem ---------------------------------------------------------------

set "PY="
if exist "C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12\python.exe" set "PY=C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12\python.exe"
if not defined PY if exist "D:\empire_tools\green_tools\python\python.exe" set "PY=D:\empire_tools\green_tools\python\python.exe"
if not defined PY for /f "delims=" %%i in ('where python 2^>nul') do if not defined PY set "PY=%%i"

if not defined PY goto nopython

echo ==================================================
echo   Restore WorkBuddy login to the MAIN account
echo.
echo   * Writes the saved credential back to the client
echo     login file and reloads the page.
echo   * No restart of the app is needed.
echo ==================================================
echo.
echo Using Python: %PY%
echo.

"%PY%" "%~dp0account_switch.py" --to account_a
set "RC=%ERRORLEVEL%"

echo.
if "%RC%"=="0" goto ok

echo [FAILED] exit code = %RC%
echo Try closing WorkBuddy and opening it again.
goto end

:ok
echo [OK] Done. The client should be back on the main account.

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

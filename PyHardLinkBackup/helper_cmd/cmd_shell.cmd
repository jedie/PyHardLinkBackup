@echo off
title %~0

set BASE_PATH=%APPDATA%\PyHardLinkBackup
if NOT exist %BASE_PATH% (
    echo.
    echo ERROR: venv not found here:
    echo.
    echo %BASE_PATH%
    echo.
    pause
    exit 1
)
cd /d %BASE_PATH%

set SCRIPT_PATH="%BASE_PATH%\Scripts"
if not "%errorlevel%"=="0" (
    echo.
    echo ERROR: venv/Script path not found here:
    echo.
    echo %SCRIPT_PATH%
    echo.
    pause
    exit
)

set ACTIVATE=%SCRIPT_PATH%\activate.bat
if NOT exist %ACTIVATE% (
    echo.
    echo ERROR: venv activate not found here:
    echo.
    echo %ACTIVATE%
    echo.
    pause
    exit 1
)

echo on
call %ACTIVATE%

echo.

python --version
pip --version

echo on
phlb.exe --version
@echo off

echo.

cmd.exe /K echo Have python fun!
title end - %~0
pause
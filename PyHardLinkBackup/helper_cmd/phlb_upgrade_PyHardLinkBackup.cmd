@echo off
title %~0

set SCRIPT_PATH="%~dp0Scripts"
cd /d %SCRIPT_PATH%
if not "%errorlevel%"=="0" (
    echo.
    echo ERROR: venv/Script path not found here:
    echo.
    echo %SCRIPT_PATH%
    echo.
    pause
    exit
)

set PIP_EXE=pip.exe
if NOT exist %PIP_EXE% (
    echo.
    echo ERROR: Can't find %PIP_EXE%
    echo.
    echo Not found in: %SCRIPT_PATH%
    echo.
    pause
    exit 1
)

echo on

%PIP_EXE% install --upgrade PyHardLinkBackup

@echo off
echo.

set SETUP_EXE=phlb_setup_helper_files.exe
if NOT exist %SETUP_EXE% (
    echo.
    echo ERROR: Can't find %SETUP_EXE%
    echo.
    echo Not found in: %SCRIPT_PATH%
    echo.
    pause
    exit 1
)

echo on

%SETUP_EXE%

@echo off
echo.
pause
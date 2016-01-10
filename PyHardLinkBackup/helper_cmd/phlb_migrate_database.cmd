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

set EXE=manage.exe
if NOT exist %EXE% (
    echo.
    echo ERROR: Can't find %EXE% in Scripts
    echo.
    echo Not found in: %SCRIPT_PATH%
    echo.
    pause
    exit 1
)

echo on

%EXE% migrate

@echo off
echo.
pause
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


REM '--noreload' is needed under windows if venv is used!
REM Otherwise the start script will not be found, becuase
REM the ".exe" extension will be script from sys.argv[0]

echo on

%EXE% runserver --noreload

@echo off
echo.
pause
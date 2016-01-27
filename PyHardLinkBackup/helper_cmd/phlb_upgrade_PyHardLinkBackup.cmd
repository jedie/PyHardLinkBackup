@echo off
title %~0

set BASE_PATH=%APPDATA%\PyHardLinkBackup
call:test_exist "%BASE_PATH%" "venv not found here:"
cd /d "%BASE_PATH%"

set SCRIPT_PATH=%BASE_PATH%\Scripts
call:test_exist "%SCRIPT_PATH%" "venv/Script path not found here:"

set ACTIVATE=%SCRIPT_PATH%\activate.bat
call:test_exist "%ACTIVATE%" "venv activate not found here:"

echo on
call "%ACTIVATE%"


set EXE=%SCRIPT_PATH%\pip.exe
call:test_exist "%EXE%" "pip.exe not found here:"

echo on
"%EXE%" install --upgrade pip
"%EXE%" install --upgrade PyHardLinkBackup

@echo off
set EXE=%SCRIPT_PATH%\phlb.exe
call:test_exist "%EXE%" "phlb.exe not found here:"

echo on
cd /d "%~dp0"
"%EXE%" helper "%BASE_PATH%"

@echo off
title end - %~0
pause
goto:eof


:test_exist
    if NOT exist "%~1" (
        echo.
        echo ERROR: %~2
        echo.
        echo "%~1"
        echo.
        pause
        exit 1
    )
goto:eof

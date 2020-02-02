@echo off
title %~0

set BASE_PATH=%ProgramFiles%\pyhardlinkbackup
call:test_exist "%BASE_PATH%" "venv not found here:"
cd /d "%BASE_PATH%"

set SCRIPT_PATH=%BASE_PATH%\Scripts
call:test_exist "%SCRIPT_PATH%" "venv/Script path not found here:"

set ACTIVATE=%SCRIPT_PATH%\activate.bat
call:test_exist "%ACTIVATE%" "venv activate not found here:"

echo on
call "%ACTIVATE%"

echo.

python --version
pip --version

set EXE=%SCRIPT_PATH%\phlb.exe
call:test_exist "%EXE%" "phlb.exe not found here:"

echo on
cd /d "%~dp0"
"%EXE%" --version
@echo off

echo.

cmd.exe /K echo Have python fun!
title end - %~0
pause
@goto:eof


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

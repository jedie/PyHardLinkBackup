@echo off
title %~0

set BASE_PATH=%ProgramFiles%\PyHardLinkBackup
call:test_exist "%BASE_PATH%" "venv not found here:"
cd /d "%BASE_PATH%"

set SCRIPT_PATH=%BASE_PATH%\Scripts
call:test_exist "%SCRIPT_PATH%" "venv/Script path not found here:"

set ACTIVATE=%SCRIPT_PATH%\activate.bat
call:test_exist "%ACTIVATE%" "venv activate not found here:"

echo on
call "%ACTIVATE%"


set EXE=%SCRIPT_PATH%\manage.exe
call:test_exist "%EXE%" "manage.exe not found here:"

REM '--noreload' is needed under windows if venv is used!
REM Otherwise the start script will not be found, becuase
REM the ".exe" extension will be script from sys.argv[0]

echo on
cd /d "%~dp0"
"%EXE%" runserver --noreload

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

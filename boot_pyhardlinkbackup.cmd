@echo off
title %~0
cd /d "%~dp0"

REM ~ Windows Batch file to boot pyhardlinkbackup
REM ~
REM ~ It's create a virtualenv under "C:\Program Files\pyhardlinkbackup"

for /f "delims=;" %%i in ('py -V') do set VERSION=%%i
for /f "delims=;" %%i in ('py -3 -V') do set VERSION3=%%i

cls
echo.

if "%VERSION%"=="" (
    echo Sorry, Python 'py' launcher seems not to exist:
    echo.
    echo on
    py -V
    @echo off
    echo.
    echo Please install Python!
    echo.
    pause
    exit
)
echo Python 'py' launcher exists, default version is: %VERSION%

if "%VERSION3%"=="" (
    echo.
    echo Python v3 not installed!
    echo Sorry, pyhardlinkbackup doesn't run with Python v2 :(
    echo.
    pause
    exit
) else (
    echo Python v3 is: %VERSION%
)

whoami /groups | find "S-1-16-12288" > nul
if errorlevel 1 (
    echo.
    echo Error: You must start this batchfile with admin rights!
    echo.
    pause
    exit /b
)

set BASE_PATH=%ProgramFiles%\pyhardlinkbackup
echo on
mkdir "%BASE_PATH%"
@echo off
call:test_exist "%BASE_PATH%" "venv not found here:"

echo on
py -3 -m venv "%BASE_PATH%"
@echo off

set SCRIPT_PATH=%BASE_PATH%\Scripts
call:test_exist "%SCRIPT_PATH%" "venv/Script path not found here:"

set ACTIVATE=%SCRIPT_PATH%\activate.bat
call:test_exist "%ACTIVATE%" "venv activate not found here:"

echo on
call "%ACTIVATE%"

set PYTHON_EXE=%SCRIPT_PATH%\python.exe
call:test_exist "%PYTHON_EXE%" "Python not found here:"
echo on
"%PYTHON_EXE%" -m pip install --upgrade pip
@echo off

set PIP_EXE=%SCRIPT_PATH%\pip.exe
call:test_exist "%PIP_EXE%" "pip not found here:"
echo on
"%PIP_EXE%" install pyhardlinkbackup
@echo off

set PHLB_EXE=%SCRIPT_PATH%\phlb.exe
call:test_exist "%PHLB_EXE%" "phlb not found here:"
echo on
"%PHLB_EXE%" helper "%BASE_PATH%"
@echo off

set EXE=%SCRIPT_PATH%\manage.exe
call:test_exist "%EXE%" "manage.exe not found here:"
echo on
"%EXE%" migrate

echo on
explorer.exe %BASE_PATH%
@echo off
pause
exit 0


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

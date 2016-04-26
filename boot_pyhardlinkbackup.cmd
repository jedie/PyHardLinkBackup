@echo off
title %~0
cd /d "%~dp0"

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
    echo Sorry, PyHardLinkBackup doesn't run with Python v2 :(
    echo.
    pause
    exit
) else (
    echo Python v3 is: %VERSION%
)

set BASE_PATH=%APPDATA%\PyHardLinkBackup
mkdir %BASE_PATH%
call:test_exist "%BASE_PATH%" "venv not found here:"

echo on
py -3 -m venv %BASE_PATH%
@echo off

set SCRIPT_PATH=%BASE_PATH%\Scripts
call:test_exist "%SCRIPT_PATH%" "venv/Script path not found here:"

set ACTIVATE=%SCRIPT_PATH%\activate.bat
call:test_exist "%ACTIVATE%" "venv activate not found here:"

echo on
call %ACTIVATE%

set PIP_EXE="%SCRIPT_PATH%\pip.exe"
call:test_exist "%PIP_EXE%" "pip not found here:"
echo on
%PIP_EXE% install PyHardLinkBackup
@echo off

set PHLB_EXE="%SCRIPT_PATH%\phlb.exe"
call:test_exist "%PHLB_EXE%" "phlb not found here:"
echo on
%PHLB_EXE% helper %BASE_PATH%
@echo off

set EXE="%SCRIPT_PATH%\manage.exe"
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

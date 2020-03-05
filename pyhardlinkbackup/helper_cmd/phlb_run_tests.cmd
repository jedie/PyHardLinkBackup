@echo off
title %~0

set BASE_PATH=%ProgramFiles%\PyHardLinkBackup
call:test_exist "%BASE_PATH%" "venv not found here:"
cd /d "%BASE_PATH%"

set SCRIPT_PATH=%BASE_PATH%\Scripts
call:test_exist "%SCRIPT_PATH%" "venv/Script path not found here:"

set ACTIVATE=%SCRIPT_PATH%\activate.bat
call:test_exist "%ACTIVATE%" "venv activate not found here:"

set PIP_EXE=%SCRIPT_PATH%\pip.exe
call:test_exist "%PIP_EXE%" "pip.exe not found here:"

echo on
call "%ACTIVATE%"

for /f "delims=;" %%i in ('python.exe -c "import os,pyhardlinkbackup;print(os.path.dirname(pyhardlinkbackup.__file__))"') do set PKG_PATH=%%i
call:test_exist "%PKG_PATH%" "Can't find pyhardlinkbackup package path!"

echo pyhardlinkbackup package path: "%PKG_PATH%"
set REQ_PATH=%PKG_PATH%\requirements\dev_extras.txt

call:test_exist "%REQ_PATH%" "Requirement file 'dev_extras.txt' not found!"

echo on

"%PIP_EXE%" install --upgrade pip
"%PIP_EXE%" install -r "%REQ_PATH%"
"%PIP_EXE%" install --upgrade -r "%REQ_PATH%"

cd "%PKG_PATH%"
cd ..
coverage.exe run --source=pyhardlinkbackup --parallel-mode -m pyhardlinkbackup.django_project.manage test --verbosity=2
set test_errorlevel=%errorlevel%
@echo off
if "%1" == "no_report" (
    REM called from AppVeyor
    exit %test_errorlevel%
)
echo on
coverage.exe combine
coverage.exe html
start htmlcov\index.html

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

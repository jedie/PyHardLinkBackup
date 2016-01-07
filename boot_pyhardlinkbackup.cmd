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

set destination=%APPDATA%\PyHardLinkBackup
mkdir %destination%
if NOT exist %destination% (
    echo ERROR: '%destination%' doesn't exists?!?
    pause
    exit 1
)

echo on
py -3 -m venv %destination%
%destination%\Scripts\pip.exe install PyHardLinkBackup
@echo off

set out="%destination%\pyhlb config.cmd"
echo @cd /d "%%~dp0\Scripts" > %out%
echo phlb.exe config >> %out%
echo @pause >> %out%

set out="%destination%\pyhlb migrate.cmd"
echo @cd /d "%%~dp0\Scripts" > %out%
echo phlb.exe migrate >> %out%
echo @pause >> %out%

set out="%destination%\pip upgrade.cmd"
echo @cd /d "%%~dp0\Scripts" > %out%
echo pip.exe install --upgrade PyHardLinkBackup >> %out%
echo @pause >> %out%

echo on
explorer.exe %destination%
@pause
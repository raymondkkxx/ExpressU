@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
set "VBS_FILE="

if exist "%CD%\.git-command\create-shortcut\run.vbs" set "VBS_FILE=%CD%\.git-command\create-shortcut\run.vbs"
if not defined VBS_FILE if exist "%SCRIPT_DIR%create-shortcut\run.vbs" set "VBS_FILE=%SCRIPT_DIR%create-shortcut\run.vbs"
if not defined VBS_FILE if exist "%SCRIPT_DIR%.git-command\create-shortcut\run.vbs" set "VBS_FILE=%SCRIPT_DIR%.git-command\create-shortcut\run.vbs"
if not defined VBS_FILE if exist "%SCRIPT_DIR%..\.git-command\create-shortcut\run.vbs" set "VBS_FILE=%SCRIPT_DIR%..\.git-command\create-shortcut\run.vbs"
if not defined VBS_FILE if exist "%SCRIPT_DIR%run.vbs" set "VBS_FILE=%SCRIPT_DIR%run.vbs"

if not defined VBS_FILE (
    echo [ERROR] File not found: ".git-command\create-shortcut\run.vbs"
    echo [INFO]  BAT dir : "%SCRIPT_DIR%"
    echo [INFO]  Work dir: "%CD%"
    pause
    exit /b 1
)

for %%I in ("%VBS_FILE%") do (
    set "VBS_FILE=%%~fI"
    set "VBS_DIR=%%~dpI"
)

pushd "%VBS_DIR%"
wscript.exe //nologo "%VBS_FILE%"
set "EXIT_CODE=%ERRORLEVEL%"
popd

if not "%EXIT_CODE%"=="0" (
    echo [ERROR] Script exited with code %EXIT_CODE%.
    pause
    exit /b %EXIT_CODE%
)

exit /b 0
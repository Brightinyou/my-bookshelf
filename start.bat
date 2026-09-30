@echo off
setlocal
cd /d "%~dp0"

REM Prefer the venv exe: some PCs have VBScript removed (2026-09-30).
if exist "%~dp0.venv\Scripts\MyBookshelf.exe" (
    start "" "%~dp0.venv\Scripts\MyBookshelf.exe" "%~dp0core\desktop.py"
    exit /b 0
)

if exist "%~dp0start-app.vbs" (
    start "" wscript.exe "%~dp0start-app.vbs"
    exit /b 0
)

if exist "%~dp0MyBookshelf.exe" (
    start "" "%~dp0MyBookshelf.exe"
    exit /b 0
)

exit /b 1

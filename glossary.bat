@echo off
REM 용어집 — 보관함의 «한글(원어)» 표기를 모아 정본으로 통일한다.
REM   glossary.bat            현황만 본다
REM   glossary.bat --apply    백업한 뒤 실제로 고친다
REM   glossary.bat --check    원어를 LCSH·InPhO 에 대조한다
setlocal EnableExtensions
chcp 65001 >nul
if exist "%~dp0core\services\glossary.py" (
    cd /d "%~dp0core"
) else (
    cd /d "%~dp0"
)

set "PY=%~dp0.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

if /i "%~1"=="--check" (
    "%PY%" -m services.termcheck %2 %3 %4 %5
) else (
    "%PY%" -m services.glossary %*
)
set "RC=%ERRORLEVEL%"

echo.
pause
exit /b %RC%

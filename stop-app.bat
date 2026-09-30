@echo off
chcp 65001 >nul
REM My Bookshelf 종료 스크립트 — 창(desktop.py)과 서버(streamlit)를 모두 끕니다.
REM ★2026-08-27: 예전에는 Name='python.exe'만 찾았는데, 앱은 창 없이 뜨려고
REM    pythonw.exe로 돕니다. 그래서 이 스크립트는 아무것도 못 끄고 있었고,
REM    앱을 열 때마다 창과 서버가 하나씩 쌓였습니다(실측: 창 6 · 서버 2).
REM ★2026-09-30: 명령줄(Get-CimInstance) 대신 실행 파일 경로(Get-Process Path)로 찾습니다.
REM    WMI 가 막힌 PC(Windows Sandbox 실측)에서는 아무것도 못 껐고, 이름 조건에
REM    MyBookshelf.exe 가 빠져 있어 지금의 앱 창은 WMI 가 되는 PC 에서도 못 껐습니다.
REM    이 폴더의 .venv\Scripts·runtime 에서 뜬 파이썬·MyBookshelf.exe 를 모두 끕니다.
set "MB_ROOT=%~dp0"
echo [My Bookshelf] 앱을 종료합니다...
powershell -NoProfile -Command "$r = $env:MB_ROOT.TrimEnd('\'); $dirs = @((Join-Path $r '.venv\Scripts'), (Join-Path $r 'runtime')) | ForEach-Object { $_.ToLower() }; Get-Process | Where-Object { $_.Path -and $_.ProcessName -match '^(python|pythonw|MyBookshelf)$' -and ($dirs -contains (Split-Path $_.Path -Parent).ToLower()) } | ForEach-Object { Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue }"
echo [완료] 종료되었습니다. 이 창은 잠시 후 닫힙니다.
timeout /t 3 >nul

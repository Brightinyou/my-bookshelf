@echo off
chcp 65001 >nul
REM My Bookshelf 종료 스크립트 — 창(desktop.py)과 서버(streamlit)를 모두 끕니다.
REM ★2026-08-27: 예전에는 Name='python.exe'만 찾았는데, 앱은 창 없이 뜨려고
REM    pythonw.exe로 돕니다. 그래서 이 스크립트는 아무것도 못 끄고 있었고,
REM    앱을 열 때마다 창과 서버가 하나씩 쌓였습니다(실측: 창 6 · 서버 2).
echo [My Bookshelf] 앱을 종료합니다...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('python.exe','pythonw.exe') -and ($_.CommandLine -like '*pipeline_app.py*' -or $_.CommandLine -like '*desktop.py*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
echo [완료] 종료되었습니다. 이 창은 잠시 후 닫힙니다.
timeout /t 3 >nul

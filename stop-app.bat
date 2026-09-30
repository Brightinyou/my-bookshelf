@echo off
chcp 65001 >nul
REM My Bookshelf 종료 스크립트 — 창(desktop.py)과 서버(streamlit)를 모두 끕니다.
REM ★2026-08-27: 예전에는 Name='python.exe'만 찾았는데, 앱은 창 없이 뜨려고
REM    pythonw.exe로 돕니다. 그래서 이 스크립트는 아무것도 못 끄고 있었고,
REM    앱을 열 때마다 창과 서버가 하나씩 쌓였습니다(실측: 창 6 · 서버 2).
REM ★2026-09-30: 실행 파일 경로와 명령줄의 합집합으로 찾습니다(stop-app.ps1).
REM    WMI 가 막힌 PC(Windows Sandbox 실측)에서는 아무것도 못 껐고, 이름 조건에
REM    MyBookshelf.exe 가 빠져 있어 지금의 앱 창은 WMI 가 되는 PC 에서도 못 껐습니다.
REM    설치·제거 프로그램도 같은 stop-app.ps1 을 씁니다.
REM    ★-Root "%~dp0." — %~dp0 은 \ 로 끝나 "…\" 가 되면 닫는 따옴표가 이스케이프된다.
echo [My Bookshelf] 앱을 종료합니다...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop-app.ps1" -Root "%~dp0."
echo [완료] 종료되었습니다. 이 창은 잠시 후 닫힙니다.
timeout /t 3 >nul

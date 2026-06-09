@echo off
setlocal
cd /d "%~dp0"
set /p XHS_URL=请粘贴小红书链接，然后按回车：
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_xhs_analysis.ps1" -Url "%XHS_URL%"
pause

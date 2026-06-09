@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".git" (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "& { $dirty = git status --porcelain; if ($dirty) { Write-Host '检测到本地代码有改动，已暂停自动更新，避免覆盖。'; exit 2 }; git pull --ff-only origin main; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }"
  if errorlevel 1 (
    echo.
    echo 自动更新失败，请把这个窗口截图发给我。
    pause
    exit /b 1
  )
)
if not exist ".venv\Scripts\python.exe" (
  powershell -NoProfile -ExecutionPolicy Bypass -Command "& { $BundledPython='C:\Users\Yunxi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'; if (Test-Path $BundledPython) { & $BundledPython -m venv '.\.venv' } else { py -3 -m venv '.\.venv' }; .\.venv\Scripts\python.exe -m pip install --upgrade pip; .\.venv\Scripts\python.exe -m pip install -r '.\requirements.txt' }"
)
start "" "http://127.0.0.1:8765"
powershell -NoProfile -ExecutionPolicy Bypass -Command "& { $port=8765; $existing=Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue; if (-not $existing) { $env:XIAOYANG_WORKBENCH_PORT='8765'; .\.venv\Scripts\python.exe .\workbench\server.py } }"

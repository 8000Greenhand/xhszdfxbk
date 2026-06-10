@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "WORKBENCH_URL=http://127.0.0.1:8765/?v=20260610-card-title"

echo ========================================
echo 小羊森林内容工作台启动中...
echo 当前目录：%cd%
echo 打开地址：%WORKBENCH_URL%
echo ========================================
echo.

if exist ".git" (
  echo [1/4] 正在检查本地代码状态...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "& { $dirty = git status --porcelain; if ($dirty) { Write-Host '检测到本地代码有改动，已暂停自动更新，避免覆盖。'; Write-Host $dirty; exit 2 }; git pull --ff-only origin main; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }"
  if errorlevel 1 (
    echo.
    echo 自动更新失败。请把这个窗口截图发给 GPT。
    echo.
    pause
    exit /b 1
  )
) else (
  echo [1/4] 当前目录不是 Git 仓库，跳过自动更新。
)

echo.
echo [2/4] 正在检查 Python 环境...
if not exist ".venv\Scripts\python.exe" (
  echo 未找到 .venv，正在创建本地 Python 环境...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "& { $BundledPython='C:\Users\Yunxi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'; if (Test-Path $BundledPython) { & $BundledPython -m venv '.\.venv' } else { py -3 -m venv '.\.venv' }; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; .\.venv\Scripts\python.exe -m pip install --upgrade pip; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; .\.venv\Scripts\python.exe -m pip install -r '.\requirements.txt'; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE } }"
  if errorlevel 1 (
    echo.
    echo Python 环境准备失败。请把这个窗口截图发给 GPT。
    echo.
    pause
    exit /b 1
  )
)

echo.
echo [3/4] 正在检查 8765 端口...
powershell -NoProfile -ExecutionPolicy Bypass -Command "& { $port=8765; $existing=Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue; if ($existing) { exit 0 } else { exit 3 } }"
if not errorlevel 3 (
  echo 端口 8765 已经有服务在运行，直接打开页面。
  start "" "%WORKBENCH_URL%"
  echo.
  echo 已打开工作台。如果页面打不开，请把这个窗口截图发给 GPT。
  pause
  exit /b 0
)

echo.
echo [4/4] 正在启动工作台服务...
echo 浏览器即将打开：%WORKBENCH_URL%
echo 如果下面出现 Python 报错，请把整个窗口截图发给 GPT。
echo.
start "" "%WORKBENCH_URL%"
".\.venv\Scripts\python.exe" ".\workbench\server.py"

echo.
echo 工作台服务已退出或启动失败。请把这个窗口截图发给 GPT。
echo.
pause
exit /b 1

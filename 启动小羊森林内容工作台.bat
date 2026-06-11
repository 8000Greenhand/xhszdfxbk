@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMddHHmmss"') do set "CACHE_BUST=%%i"
set "WORKBENCH_URL=http://127.0.0.1:8765/?v=%CACHE_BUST%"

echo ========================================
echo 小羊森林内容学习与创作转译工作台启动中...
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
powershell -NoProfile -ExecutionPolicy Bypass -Command "& { $port=8765; $existing=Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue; if (-not $existing) { exit 3 }; $closed=$false; foreach ($conn in $existing) { $owningPid=$conn.OwningProcess; $proc=Get-CimInstance Win32_Process -Filter \"ProcessId=$owningPid\" -ErrorAction SilentlyContinue; $cmd=($proc.CommandLine | Out-String); if ($cmd -match 'workbench\\server(_v2)?\.py') { Write-Host \"检测到旧工作台服务，正在关闭 PID $owningPid\"; Stop-Process -Id $owningPid -Force; $closed=$true } }; if ($closed) { Start-Sleep -Seconds 1; exit 3 } else { exit 4 } }"
if errorlevel 4 (
  echo 端口 8765 已被其他程序占用，无法安全关闭。
  echo 请关闭占用 8765 的程序，或把这个窗口截图发给 GPT。
  echo.
  pause
  exit /b 1
)

echo.
echo [4/4] 正在启动工作台服务...
echo 浏览器即将打开：%WORKBENCH_URL%
echo 当前启动入口：workbench\server_v2.py
echo 如果下面出现 Python 报错，请把整个窗口截图发给 GPT。
echo.
start "" "%WORKBENCH_URL%"
".\.venv\Scripts\python.exe" ".\workbench\server_v2.py"

echo.
echo 工作台服务已退出或启动失败。请把这个窗口截图发给 GPT。
echo.
pause
exit /b 1
param(
  [Parameter(Mandatory=$true)]
  [string]$Url
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$BundledPython = "C:\Users\Yunxi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if (-not (Test-Path $Python)) {
  if (Test-Path $BundledPython) {
    & $BundledPython -m venv (Join-Path $Root ".venv")
  } else {
    py -3 -m venv (Join-Path $Root ".venv")
  }
  & $Python -m pip install --upgrade pip
  & $Python -m pip install -r (Join-Path $Root "requirements.txt")
}

& $Python (Join-Path $Root "tools\xhs_analyzer.py") --url $Url

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $raiz "src"
Set-Location $raiz
& (Join-Path $raiz ".venv\Scripts\python.exe") -m talentia.platform.jobs.worker


$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $raiz "src"
Set-Location $raiz
& (Join-Path $raiz ".venv\Scripts\python.exe") -m uvicorn talentia.main:app --host 127.0.0.1 --port 8000


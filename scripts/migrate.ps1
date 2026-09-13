$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $raiz "src"
& (Join-Path $raiz ".venv\Scripts\python.exe") -m alembic -c (Join-Path $raiz "alembic_greenfield.ini") upgrade head


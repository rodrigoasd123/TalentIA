$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $raiz "src"
$python = Join-Path $raiz ".venv\Scripts\python.exe"
& $python -m alembic -c (Join-Path $raiz "alembic_greenfield.ini") upgrade head
& $python -m pytest -q (Join-Path $raiz "tests\greenfield")
& (Join-Path $raiz ".venv\Scripts\ruff.exe") check (Join-Path $raiz "src\talentia") (Join-Path $raiz "tests\greenfield")


param([Parameter(Mandatory=$true)][string]$Origen, [string]$Destino = "")
$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
if (-not $Destino) { $Destino = Join-Path $raiz "talentia_greenfield_restaurada.db" }
if (Test-Path -LiteralPath $Destino) { throw "El destino ya existe; no se sobrescribe" }
$python = Join-Path $raiz ".venv\Scripts\python.exe"
$env:PYTHONPATH = Join-Path $raiz "src"
& $python -m talentia.platform.operaciones.base_datos restaurar $Origen $Destino

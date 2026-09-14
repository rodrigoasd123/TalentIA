param([string]$Origen = "", [string]$Destino = "")
$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
if (-not $Origen) { $Origen = Join-Path $raiz "talentia_greenfield.db" }
if (-not (Test-Path -LiteralPath $Origen)) { throw "No existe la base greenfield" }
if (-not $Destino) {
    $carpeta = Join-Path $raiz "backups"
    New-Item -ItemType Directory -Force -Path $carpeta | Out-Null
    $Destino = Join-Path $carpeta ("talentia-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".db")
}
$python = Join-Path $raiz ".venv\Scripts\python.exe"
$env:PYTHONPATH = Join-Path $raiz "src"
& $python -m talentia.platform.operaciones.base_datos respaldar $Origen $Destino

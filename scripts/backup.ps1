param([string]$Destino = "")
$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
$origen = Join-Path $raiz "talentia_greenfield.db"
if (-not (Test-Path -LiteralPath $origen)) { throw "No existe la base greenfield" }
if (-not $Destino) {
    $carpeta = Join-Path $raiz "backups"
    New-Item -ItemType Directory -Force -Path $carpeta | Out-Null
    $Destino = Join-Path $carpeta ("talentia-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".db")
}
$python = Join-Path $raiz ".venv\Scripts\python.exe"
& $python -c "import sqlite3,sys; a=sqlite3.connect(sys.argv[1]); b=sqlite3.connect(sys.argv[2]); a.backup(b); print(b.execute('PRAGMA integrity_check').fetchone()[0]); b.close(); a.close()" $origen $Destino
Write-Output $Destino


param([Parameter(Mandatory=$true)][string]$Origen, [string]$Destino = "")
$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
if (-not $Destino) { $Destino = Join-Path $raiz "talentia_greenfield_restaurada.db" }
if (Test-Path -LiteralPath $Destino) { throw "El destino ya existe; no se sobrescribe" }
$python = Join-Path $raiz ".venv\Scripts\python.exe"
& $python -c "import shutil,sqlite3,sys; c=sqlite3.connect('file:'+sys.argv[1]+'?mode=ro',uri=True); assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'; c.close(); shutil.copy2(sys.argv[1],sys.argv[2])" $Origen $Destino
Write-Output $Destino


param(
    [int]$ApiPort = 8000,
    [int]$UiPort = 8501,
    [int]$MlflowPort = 5000
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$logDirectory = Join-Path $projectRoot ".lab-logs"

if (-not (Test-Path -LiteralPath $python)) {
    throw "No existe .venv. Ejecuta primero: py -3.12 -m venv .venv"
}

function Test-PortAvailable([int]$Port) {
    $listener = $null
    try {
        $listener = [System.Net.Sockets.TcpListener]::new(
            [System.Net.IPAddress]::Loopback,
            $Port
        )
        $listener.Start()
        return $true
    }
    catch {
        return $false
    }
    finally {
        if ($null -ne $listener) {
            $listener.Stop()
        }
    }
}

function Find-FreePort([int]$PreferredPort) {
    foreach ($candidate in $PreferredPort..($PreferredPort + 20)) {
        if (Test-PortAvailable $candidate) {
            return $candidate
        }
    }
    throw "No se encontró un puerto libre entre $PreferredPort y $($PreferredPort + 20)."
}

New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
$resolvedApiPort = Find-FreePort $ApiPort
$resolvedUiPort = Find-FreePort $UiPort
$resolvedMlflowPort = Find-FreePort $MlflowPort
$mlflowDatabase = (Join-Path $projectRoot "mlflow.db").Replace("\", "/")
$mlflowTrackingUri = "sqlite:///$mlflowDatabase"

$mlflowStart = @{
    FilePath = $python
    ArgumentList = @(
        "-m", "mlflow", "ui",
        "--backend-store-uri", $mlflowTrackingUri,
        "--host", "127.0.0.1", "--port", "$resolvedMlflowPort"
    )
    WorkingDirectory = $projectRoot
    WindowStyle = "Hidden"
    RedirectStandardOutput = Join-Path $logDirectory "mlflow.stdout.log"
    RedirectStandardError = Join-Path $logDirectory "mlflow.stderr.log"
    PassThru = $true
}
$mlflowProcess = Start-Process @mlflowStart

& $python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) {
    throw "Las migraciones de base de datos fallaron."
}

$apiStart = @{
    FilePath = $python
    ArgumentList = @(
        "-m", "uvicorn", "app.api.main:app",
        "--host", "127.0.0.1", "--port", "$resolvedApiPort"
    )
    WorkingDirectory = $projectRoot
    WindowStyle = "Hidden"
    RedirectStandardOutput = Join-Path $logDirectory "api.stdout.log"
    RedirectStandardError = Join-Path $logDirectory "api.stderr.log"
    PassThru = $true
}
$previousMlflowUiUrl = $env:TALENTIA_MLFLOW_UI_URL
$previousMlflowTrackingUri = $env:TALENTIA_MLFLOW_TRACKING_URI
$env:TALENTIA_MLFLOW_UI_URL = "http://127.0.0.1:$resolvedMlflowPort"
$env:TALENTIA_MLFLOW_TRACKING_URI = $mlflowTrackingUri
try {
    $apiProcess = Start-Process @apiStart
}
finally {
    $env:TALENTIA_MLFLOW_UI_URL = $previousMlflowUiUrl
    $env:TALENTIA_MLFLOW_TRACKING_URI = $previousMlflowTrackingUri
}

$apiUrl = "http://127.0.0.1:$resolvedApiPort"
$ready = $false
foreach ($attempt in 1..30) {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri "$apiUrl/health/ready" -TimeoutSec 2
        if ($response.StatusCode -eq 200) {
            $ready = $true
            break
        }
    }
    catch {
        Start-Sleep -Milliseconds 500
    }
}
if (-not $ready) {
    throw "La API no quedó lista. Revisa .lab-logs/api.stderr.log (PID $($apiProcess.Id))."
}

$previousApiBaseUrl = $env:TALENTIA_API_BASE_URL
$env:TALENTIA_API_BASE_URL = $apiUrl
try {
    $uiStart = @{
        FilePath = $python
        ArgumentList = @(
            "-m", "streamlit", "run", "ats_frontend/streamlit_app.py",
            "--server.headless", "true", "--server.port", "$resolvedUiPort",
            "--browser.gatherUsageStats", "false"
        )
        WorkingDirectory = $projectRoot
        WindowStyle = "Hidden"
        RedirectStandardOutput = Join-Path $logDirectory "ui.stdout.log"
        RedirectStandardError = Join-Path $logDirectory "ui.stderr.log"
        PassThru = $true
    }
    $uiProcess = Start-Process @uiStart
}
finally {
    $env:TALENTIA_API_BASE_URL = $previousApiBaseUrl
}

Write-Host "TalentIA iniciado."
Write-Host "Interfaz: http://127.0.0.1:$resolvedUiPort"
Write-Host "API:      $apiUrl/docs"
Write-Host "MLflow:   http://127.0.0.1:$resolvedMlflowPort"
Write-Host "Procesos: API=$($apiProcess.Id), UI=$($uiProcess.Id), MLflow=$($mlflowProcess.Id)"
Write-Host "Logs:     $logDirectory"

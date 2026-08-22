param(
    [string]$BackendHost = "127.0.0.1",
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 8501,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvDir = Join-Path $ProjectDir ".venv"
$Pip = Join-Path $VenvDir "Scripts\pip.exe"
$Streamlit = Join-Path $VenvDir "Scripts\streamlit.exe"

if (-not $SkipInstall) {
    if (-not (Test-Path $VenvDir)) {
        python -m venv $VenvDir
    }
    & $Pip install --upgrade pip -q
    & $Pip install -r (Join-Path $ProjectDir "requirements.txt") -q
}

$BackendArgs = @(
    "-m", "uvicorn", "app.main:app",
    "--app-dir", "`"$(Join-Path $ProjectDir "backend")`"",
    "--host", $BackendHost,
    "--port", "$BackendPort"
)
$FrontendArgs = @(
    "run", "`"$(Join-Path $ProjectDir "frontend\app.py")`"",
    "--server.port", "$FrontendPort",
    "--server.headless", "true"
)

$Backend = Start-Process -FilePath (Join-Path $VenvDir "Scripts\python.exe") -ArgumentList $BackendArgs -PassThru
$Frontend = Start-Process -FilePath $Streamlit -ArgumentList $FrontendArgs -PassThru

Write-Host "Backend:  http://$BackendHost:$BackendPort"
Write-Host "Frontend: http://localhost:$FrontendPort"
Write-Host "Press Ctrl+C to stop both services."

try {
    Wait-Process -Id $Backend.Id -ErrorAction SilentlyContinue
}
finally {
    Stop-Process -Id $Backend.Id, $Frontend.Id -Force -ErrorAction SilentlyContinue
}

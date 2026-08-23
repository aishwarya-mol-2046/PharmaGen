param(
    [string]$BackendHost = "127.0.0.1",
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvDir = Join-Path $ProjectDir ".venv"
$Pip = Join-Path $VenvDir "Scripts\pip.exe"


if (-not $SkipInstall) {
    if (-not (Test-Path $VenvDir)) {
        python -m venv $VenvDir
    }
    & $Pip install --upgrade pip -q
    & $Pip install -r (Join-Path $ProjectDir "requirements.txt") -q
}

# Load environment configuration (.env) into the process environment so the
# backend inherits optional settings (e.g. PHARMAGEN_ONCOKB_FILE).
# Mirrors the .env loader in run.sh / the `make backend` target.
$EnvFile = Join-Path $ProjectDir ".env"
if (Test-Path $EnvFile) {
    Write-Host "Loading environment from .env"
    Get-Content $EnvFile | ForEach-Object {
        $line = $_.Trim()
        if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith("#")) { return }
        $idx = $line.IndexOf("=")
        if ($idx -le 0) { return }
        $key = $line.Substring(0, $idx).Trim()
        $val = $line.Substring($idx + 1).Trim()
        if ($val.Length -ge 2 -and $val.StartsWith('"') -and $val.EndsWith('"')) {
            $val = $val.Substring(1, $val.Length - 2)
        }
        if (-not [string]::IsNullOrWhiteSpace($key)) {
            Set-Item -Path "Env:$key" -Value $val
        }
    }
}

$BackendArgs = @(
    "-m", "uvicorn", "app.main:app",
    "--app-dir", "`"$(Join-Path $ProjectDir "backend")`"",
    "--host", $BackendHost,
    "--port", "$BackendPort"
)
if (-not (Test-Path (Join-Path $ProjectDir "frontend\node_modules"))) {
    Write-Host "Installing frontend dependencies..."
    Push-Location (Join-Path $ProjectDir "frontend"); npm install --no-audit --no-fund; Pop-Location
}

$Backend = Start-Process -FilePath (Join-Path $VenvDir "Scripts\python.exe") -ArgumentList $BackendArgs -PassThru
$Frontend = Start-Process -FilePath "npm" -ArgumentList @("run","dev","--","--port","$FrontendPort") -WorkingDirectory (Join-Path $ProjectDir "frontend") -PassThru

Write-Host "Backend:  http://$BackendHost:$BackendPort"
Write-Host "Frontend: http://localhost:$FrontendPort"
Write-Host "Press Ctrl+C to stop both services."

try {
    Wait-Process -Id $Backend.Id -ErrorAction SilentlyContinue
}
finally {
    Stop-Process -Id $Backend.Id, $Frontend.Id -Force -ErrorAction SilentlyContinue
}

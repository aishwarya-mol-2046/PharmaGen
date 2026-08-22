# Pharma

Project for managing pharmacy data with a FastAPI backend and a Streamlit frontend.

## Requirements

- Python 3 (with `venv` support)
- Linux/macOS for `run.sh` or Windows with PowerShell for `run.ps1`

## Quick start

Run the script for your platform:

```bash
# for Linux/macos
./run.sh

# Windows 
.\run.ps1
```

Creates an environment

Once started:

- Backend: http://127.0.0.1:8000
- Frontend: http://localhost:8501

Press `Ctrl+C` to stop both services.

## run.sh (Linux / macOS)

Usage:

```bash
./run.sh [options]
```

Options:

| Option | Description | Default |
| --- | --- | --- |
| `--backend-host HOST` | Backend bind host | `127.0.0.1` |
| `--backend-port PORT` | Backend bind port | `8000` |
| `--frontend-port PORT` | Streamlit frontend port | `8501` |
| `--skip-install` | Skip venv creation and pip install | off |
| `-h`, `--help` | Show help | - |

Example with custom ports:

```bash
./run.sh --backend-port 9000 --frontend-port 9001
```

## run.ps1 (Windows)

Usage:

```powershell
.\run.ps1 [-BackendHost HOST] [-BackendPort PORT] [-FrontendPort PORT] [-SkipInstall]
```

Parameters:

| Parameter | Description | Default |
| --- | --- | --- |
| `-BackendHost HOST` | Backend bind host | `127.0.0.1` |
| `-BackendPort PORT` | Backend bind port | `8000` |
| `-FrontendPort PORT` | Streamlit frontend port | `8501` |
| `-SkipInstall` | Skip venv creation and pip install | off |

Example with custom ports:

```powershell
.\run.ps1 -BackendPort 9000 -FrontendPort 9001
```

If PowerShell blocks script execution, allow it with:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

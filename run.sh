#!/usr/bin/env bash
set -euo pipefail

BACKEND_HOST="127.0.0.1"
BACKEND_PORT="8000"
FRONTEND_PORT="8501"
SKIP_INSTALL=""

usage() {
    cat <<EOF
Usage: $0 [options]

Options:
  --backend-host HOST   Backend bind host (default: $BACKEND_HOST)
  --backend-port PORT   Backend bind port (default: $BACKEND_PORT)
  --frontend-port PORT  Streamlit frontend port (default: $FRONTEND_PORT)
  --skip-install        Skip venv creation / pip install
  -h, --help            Show this help
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --backend-host) BACKEND_HOST="$2"; shift 2 ;;
        --backend-port) BACKEND_PORT="$2"; shift 2 ;;
        --frontend-port) FRONTEND_PORT="$2"; shift 2 ;;
        --skip-install) SKIP_INSTALL="1"; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
    esac
done

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
PYTHON="$VENV_DIR/bin/python"

if [[ -z "$SKIP_INSTALL" ]]; then
    if [[ ! -d "$VENV_DIR" ]]; then
        python3 -m venv "$VENV_DIR"
    fi
    "$VENV_DIR/bin/pip" install --upgrade pip -q
    "$VENV_DIR/bin/pip" install -r "$PROJECT_DIR/requirements.txt" -q
fi

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
    echo "Stopping services..."
    [[ -n "$BACKEND_PID" ]] && kill "$BACKEND_PID" 2>/dev/null || true
    [[ -n "$FRONTEND_PID" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT

"$PYTHON" -m uvicorn app.main:app \
    --app-dir "$PROJECT_DIR/backend" \
    --host "$BACKEND_HOST" \
    --port "$BACKEND_PORT" &
BACKEND_PID=$!

"$VENV_DIR/bin/streamlit" run "$PROJECT_DIR/frontend/app.py" \
    --server.port "$FRONTEND_PORT" \
    --server.headless true &
FRONTEND_PID=$!

echo "Backend:  http://$BACKEND_HOST:$BACKEND_PORT"
echo "Frontend: http://localhost:$FRONTEND_PORT"
echo "Press Ctrl+C to stop both services."

wait

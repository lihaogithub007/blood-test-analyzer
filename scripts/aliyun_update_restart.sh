#!/usr/bin/env bash
set -euo pipefail

# One-click deploy/update & restart for Aliyun Linux.
#
# What it does:
# - If project dir doesn't exist: git clone
# - Else: git pull (fast-forward)
# - Ensure Python venv exists (python3.10 preferred)
# - Install/upgrade deps from requirements.txt
# - Restart via systemd if service exists; otherwise restart with nohup (port 8000)
#
# Usage (on server):
#   bash scripts/aliyun_update_restart.sh
#
# Optional env vars:
#   REPO_SSH_URL="git@github.com:owner/repo.git"   # required when cloning
#   APP_DIR="/opt/blood-test-analyzer"
#   BRANCH="main"
#   PORT="8000"
#   HOST="0.0.0.0"                                # for nohup mode only
#   SERVICE_NAME="blood-test"                      # for systemd mode
#
# Notes:
# - Keep workers=1 for SQLite stability.

REPO_SSH_URL="${REPO_SSH_URL:-}"
APP_DIR="${APP_DIR:-/opt/blood-test-analyzer}"
BRANCH="${BRANCH:-main}"
PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"
SERVICE_NAME="${SERVICE_NAME:-blood-test}"

log() { echo "[deploy] $*"; }
die() { echo "[deploy] ERROR: $*" >&2; exit 1; }

need() {
  command -v "$1" >/dev/null 2>&1 || die "Missing command: $1"
}

need git

if [[ ! -d "$APP_DIR/.git" ]]; then
  [[ -n "$REPO_SSH_URL" ]] || die "APP_DIR not found; set REPO_SSH_URL to clone"
  log "Cloning repo to $APP_DIR (branch: $BRANCH)"
  mkdir -p "$(dirname "$APP_DIR")"
  git clone --branch "$BRANCH" --single-branch "$REPO_SSH_URL" "$APP_DIR"
else
  log "Repo exists at $APP_DIR"
fi

cd "$APP_DIR"

log "Fetching latest code"
git fetch origin "$BRANCH"
git checkout "$BRANCH" >/dev/null 2>&1 || true
git pull --ff-only origin "$BRANCH"

# Ensure system CA is available (helps Python/requests/urllib verify TLS)
export SSL_CERT_FILE="${SSL_CERT_FILE:-/etc/pki/tls/certs/ca-bundle.crt}"
export SSL_CERT_DIR="${SSL_CERT_DIR:-/etc/pki/ca-trust/extracted/pem}"

# Pick python (prefer python3.10)
PY_BIN=""
if command -v python3.10 >/dev/null 2>&1; then
  PY_BIN="python3.10"
elif command -v python3 >/dev/null 2>&1; then
  PY_BIN="python3"
else
  die "python3 not found (install Python 3.10+ recommended)"
fi

log "Using python: $PY_BIN"

if [[ ! -d ".venv" ]]; then
  log "Creating venv at $APP_DIR/.venv"
  "$PY_BIN" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

log "Upgrading pip tooling"
python -m pip install -U pip setuptools wheel

if [[ -f requirements.txt ]]; then
  log "Installing dependencies from requirements.txt"
  pip install -r requirements.txt
else
  die "requirements.txt not found in $APP_DIR"
fi

# Ensure .env exists (do not overwrite)
if [[ ! -f ".env" && -f ".env.example" ]]; then
  log "Creating .env from .env.example (please fill API key)"
  cp .env.example .env
fi

log "Restarting app"

if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files | grep -q "^${SERVICE_NAME}\\.service"; then
  log "systemd service found: ${SERVICE_NAME}.service"
  systemctl restart "$SERVICE_NAME"
  systemctl status "$SERVICE_NAME" --no-pager || true
else
  log "No systemd service found; using nohup on ${HOST}:${PORT}"
  # Stop old uvicorn if running
  PIDS="$(ps -ef | grep 'uvicorn app:app' | grep -v grep | awk '{print $2}' || true)"
  if [[ -n "${PIDS}" ]]; then
    log "Stopping old uvicorn PIDs: ${PIDS}"
    # shellcheck disable=SC2086
    kill ${PIDS} || true
    sleep 1
  fi

  nohup uvicorn app:app --host "$HOST" --port "$PORT" --workers 1 > uvicorn.log 2>&1 &
  NEWPID=$!
  log "Started uvicorn PID=${NEWPID} (log: $APP_DIR/uvicorn.log)"
fi

log "Health check (local)"
curl -sS "http://127.0.0.1:${PORT}/api/patients" >/dev/null 2>&1 \
  && log "OK: http://127.0.0.1:${PORT}/api/patients" \
  || log "WARN: health check failed (check logs)"

log "Done"


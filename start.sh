#!/usr/bin/env bash
#
# CareerForge Pro — one-click local launcher (macOS / Linux).
#
# Double-click `start.command` (macOS) or run `bash start.sh` (Linux/macOS).
# It creates the API virtualenv and installs the web dependencies on first
# run, then starts BOTH servers and keeps the window open with clean logs.
# Press Ctrl-C to stop everything.
#
# No build step is required. Ports: API :8001 (docs at /docs), Web :3000.
set -euo pipefail

cd "$(dirname "$0")"
ROOT="$(pwd)"

API_DIR="$ROOT/apps/api"
WEB_DIR="$ROOT/apps/web"
VENV="$API_DIR/.venv"
API_PORT=8001
WEB_PORT=3000

green="\033[0;32m"; yellow="\033[1;33m"; red="\033[0;31m"; nc="\033[0m"
say()  { printf "%b\n" "${green}[CareerForge]${nc} $*"; }
warn() { printf "%b\n" "${yellow}[CareerForge]${nc} $*"; }
die()  { printf "%b\n" "${red}[CareerForge] ERROR:${nc} $*" >&2; exit 1; }

# --- preflight -------------------------------------------------------------
command -v python3 >/dev/null 2>&1 || die "python3 not found. Install Python 3.11+ (https://python.org)."
command -v node    >/dev/null 2>&1 || die "node not found. Install Node 18+ (https://nodejs.org)."

PY_MINOR=$(python3 -c 'import sys; print(sys.version_info[1])' 2>/dev/null || echo 0)
[ "$PY_MINOR" -ge 11 ] || die "Python 3.11+ required (found $(python3 --version 2>&1))."

# --- API venv --------------------------------------------------------------
if [ ! -x "$VENV/bin/python" ]; then
  say "First run: creating the API virtualenv…"
  python3 -m venv "$VENV"
fi
if ! "$VENV/bin/python" -c 'import fastapi, uvicorn, sqlalchemy' >/dev/null 2>&1; then
  say "First run: installing API dependencies (one-time)…"
  "$VENV/bin/pip" install --quiet --upgrade pip
  "$VENV/bin/pip" install --quiet -e "apps/api[dev]"
fi

# --- Web dependencies ------------------------------------------------------
if [ ! -d "$WEB_DIR/node_modules" ]; then
  say "First run: installing web dependencies (one-time)…"
  (cd "$WEB_DIR" && npm install --no-audit --no-fund --loglevel=error)
fi

# --- start both ------------------------------------------------------------
cleanup() {
  say "Stopping servers…"
  [ -n "${API_PID:-}" ] && kill "$API_PID" 2>/dev/null || true
  [ -n "${WEB_PID:-}" ] && kill "$WEB_PID" 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup INT TERM EXIT

say "Starting API on :$API_PORT …"
( cd "$API_DIR" && exec "$VENV/bin/uvicorn" app.main:app --host 127.0.0.1 --port "$API_PORT" ) &
API_PID=$!

say "Starting Web on :$WEB_PORT …"
( cd "$WEB_DIR" && CF_API_URL="http://127.0.0.1:$API_PORT" exec npm run dev ) &
WEB_PID=$!

# --- wait for readiness, then show URLs -----------------------------------
say "Waiting for the API to answer /api/v1/health …"
for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:$API_PORT/api/v1/health" >/dev/null 2>&1; then break; fi
  kill -0 "$API_PID" 2>/dev/null || { warn "API exited early — check the log above."; exit 1; }
  sleep 1
done
say "Waiting for the web app to answer :$WEB_PORT …"
for _ in $(seq 1 90); do
  if curl -fsS "http://127.0.0.1:$WEB_PORT" >/dev/null 2>&1; then break; fi
  kill -0 "$WEB_PID" 2>/dev/null || { warn "Web exited early — check the log above."; exit 1; }
  sleep 1
done

printf "\n%b\n" "${green}════════════════════════════════════════════════════════${nc}"
printf "%b\n" "${green}  CareerForge Pro is running locally${nc}"
printf "%b\n" "${green}════════════════════════════════════════════════════════${nc}"
printf "  App:     ${yellow}http://localhost:%s${nc}\n" "$WEB_PORT"
printf "  API:     ${yellow}http://localhost:%s${nc}   (docs at /docs)\n" "$API_PORT"
printf "  Health:  ${yellow}http://localhost:%s/api/v1/health${nc}\n" "$API_PORT"
printf "\n${green}Press Ctrl-C to stop both servers.${nc}\n\n"

# Keep the window open, streaming both processes' exit status.
wait

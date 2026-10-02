#!/bin/zsh
# Keep Product OS API (:8000) and UI (:3000) running. Started via Terminal.app
# so macOS Desktop TCC allows reading the repo. launchd only opens this file
# when a port is down — do not start a second copy if this lock is live.
set -uo pipefail

REPO="/Users/arsalaanmohammed/Desktop/Sourabh_Bot"
LOG_DIR="${HOME}/Library/Logs/sourabh-bot"
SUPPORT="${HOME}/Library/Application Support/sourabh-bot"
LOCK="${SUPPORT}/dev-servers.pid"
API="http://127.0.0.1:8000/api/health"
UI="http://127.0.0.1:3000/"

export HOME="${HOME:-/Users/arsalaanmohammed}"
export TZ="Asia/Kolkata"
export PATH="${HOME}/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export NEXT_TELEMETRY_DISABLED=1

mkdir -p "$LOG_DIR" "$SUPPORT"

http_code() {
  curl -sS -o /dev/null -w '%{http_code}' --max-time 2 "$1" 2>/dev/null || echo 000
}

if [[ -f "$LOCK" ]]; then
  old="$(cat "$LOCK" 2>/dev/null || true)"
  if [[ -n "${old}" ]] && kill -0 "$old" 2>/dev/null; then
    echo "dev-servers already running (pid $old)"
    exit 0
  fi
fi

echo $$ >"$LOCK"
cleanup() {
  local code=$?
  if [[ -n "${CAFFEINE_PID:-}" ]]; then
    kill "$CAFFEINE_PID" 2>/dev/null || true
  fi
  kill 0 2>/dev/null || true
  rm -f "$LOCK"
  exit "$code"
}
trap cleanup EXIT INT TERM

/usr/bin/caffeinate -dims -w $$ >/dev/null 2>&1 &
CAFFEINE_PID=$!

echo "===== $(date '+%Y-%m-%d %H:%M:%S %Z') dev servers supervisor pid $$ =====" | tee -a "$LOG_DIR/dev-servers.log"

start_api() {
  cd "$REPO/backend" || exit 1
  while true; do
    if [[ "$(http_code "$API")" != "000" ]]; then
      sleep 8
      continue
    fi
    echo "$(date '+%H:%M:%S') starting uvicorn :8000" | tee -a "$LOG_DIR/api.log"
    "$REPO/backend/.venv/bin/uvicorn" app.main:app --reload --host 127.0.0.1 --port 8000 >>"$LOG_DIR/api.log" 2>&1 || true
    echo "$(date '+%H:%M:%S') uvicorn exited, retry in 2s" | tee -a "$LOG_DIR/api.log"
    sleep 2
  done
}

start_ui() {
  cd "$REPO/frontend" || exit 1
  while true; do
    if [[ "$(http_code "$UI")" != "000" ]]; then
      sleep 8
      continue
    fi
    echo "$(date '+%H:%M:%S') starting next :3000" | tee -a "$LOG_DIR/ui.log"
    npm run dev -- --hostname 127.0.0.1 --port 3000 >>"$LOG_DIR/ui.log" 2>&1 || true
    echo "$(date '+%H:%M:%S') next exited, retry in 2s" | tee -a "$LOG_DIR/ui.log"
    sleep 2
  done
}

start_api &
start_ui &
wait

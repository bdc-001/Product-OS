#!/bin/zsh
# Scheduled Cursor Agent job for Sourabh_Bot (09:00 / 17:00 / 01:00 IST).
# launchd: com.arsalaan.sourabh-bot.daily-sync
#
# Cursor cloud streams can drop (Connection lost → RetriableError). We retry the
# agent once, then fall back to in-process refresh_platform so ingest still runs.
set -euo pipefail

REPO="/Users/arsalaanmohammed/Desktop/Sourabh_Bot"
PROMPT_FILE="$REPO/scripts/daily-api-sync.prompt.txt"
LOG_DIR="${HOME}/Library/Logs/sourabh-bot"
SYNC_DIR="$REPO/data/daily-sync"
CONFIG_ENV="${HOME}/.config/sourabh-bot/cursor.env"
AGENT_BIN="${HOME}/.local/bin/cursor-agent"
VENV_PY="${REPO}/backend/.venv/bin/python"

export HOME="${HOME:-/Users/arsalaanmohammed}"
export TZ="Asia/Kolkata"
export PATH="${HOME}/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

mkdir -p "$LOG_DIR" "$SYNC_DIR"
STAMP="$(date +%Y-%m-%d)"
LOG="$LOG_DIR/daily-sync-${STAMP}.log"

exec >>"$LOG" 2>&1

echo "===== $(date '+%Y-%m-%d %H:%M:%S %Z') daily API sync start ====="

if [[ -f "$CONFIG_ENV" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$CONFIG_ENV"
  set +a
fi

if [[ ! -x "$AGENT_BIN" ]]; then
  AGENT_BIN="$(command -v cursor-agent || command -v agent || true)"
fi

if [[ ! -f "$PROMPT_FILE" ]]; then
  echo "missing prompt file: $PROMPT_FILE" >&2
  exit 1
fi

PROMPT="$(<"$PROMPT_FILE")"

amp_start() {
  /usr/bin/osascript >/dev/null 2>&1 <<'APPLESCRIPT' &
tell application "Amphetamine"
  start new session with options {duration:3, interval:hours, displaySleepAllowed:true}
end tell
APPLESCRIPT
}

amp_end() {
  /usr/bin/osascript >/dev/null 2>&1 <<'APPLESCRIPT' &
tell application "Amphetamine"
  if session is active then
    end session
  end if
end tell
APPLESCRIPT
}

cleanup() {
  amp_end
  echo "===== $(date '+%Y-%m-%d %H:%M:%S %Z') daily API sync end (exit $?) ====="
}
trap cleanup EXIT

run_agent() {
  /usr/bin/caffeinate -dims -- "$AGENT_BIN" \
    --print \
    --force \
    --sandbox disabled \
    --approve-mcps \
    --output-format text \
    --workspace "$REPO" \
    "$PROMPT"
}

# Direct ingest when Cursor agent stream is down (AGENTS.md: still ingest).
run_fallback_ingest() {
  echo "fallback: in-process refresh_platform (Cursor agent unavailable)"
  if [[ ! -x "$VENV_PY" ]]; then
    echo "fallback failed: missing $VENV_PY" >&2
    return 127
  fi
  cd "$REPO/backend"
  STAMP="$STAMP" REPO="$REPO" "$VENV_PY" - <<'PY'
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.database import SessionLocal
from app.services.refresh import refresh_platform

repo = Path(os.environ["REPO"])
stamp = os.environ["STAMP"]
IST = ZoneInfo("Asia/Kolkata")
started = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S %Z")

db = SessionLocal()
try:
    result = refresh_platform(db)
finally:
    db.close()

steps = (result or {}).get("steps") or {}
ok = bool((result or {}).get("ok", True))
finished = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S %Z")


def step_line(name: str) -> str:
    row = steps.get(name) if isinstance(steps, dict) else None
    if not isinstance(row, dict):
        return f"- {name}: (no data)"
    status = "ok" if row.get("ok", True) and not row.get("error") else "fail"
    bits = [status]
    for key in ("jira_count", "cliq_count", "count", "branch"):
        if row.get(key) not in (None, ""):
            bits.append(f"{key}={row.get(key)}")
    if row.get("error"):
        bits.append(f"error={str(row.get('error'))[:200]}")
    if row.get("stashed"):
        bits.append("stashed=true")
    if row.get("remote_blocked"):
        bits.append("remote_blocked=true")
    return f"- {name}: " + ", ".join(str(b) for b in bits)


text = "\n".join(
    [
        f"# Daily sync {stamp}",
        "",
        f"- Started: {started}",
        f"- Finished: {finished}",
        "- Mode: **fallback** (Cursor agent stream failed; ran `refresh_platform` directly)",
        f"- Overall: {'ok' if ok else 'fail'}",
        "",
        "## Steps",
        step_line("jira"),
        step_line("cliq"),
        step_line("codebase"),
        step_line("branches"),
        step_line("releases"),
        step_line("roadmap"),
        "",
        "## Files changed",
        "- None (ingest only)",
        "",
        "## Tests",
        "- Not run in fallback mode",
        "",
        "## Needs Arsalaan",
        "- Cursor agent connectivity flaked (`agentn.global.api5.cursor.sh`). If this repeats: check VPN/Wi‑Fi, Cursor status, or drop the 01:00 slot.",
        "",
    ]
)
out = repo / "data" / "daily-sync" / f"{stamp}.md"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(text, encoding="utf-8")
print(json.dumps({"ok": ok, "summary": str(out), "steps": steps}, default=str, indent=2))
raise SystemExit(0 if ok else 1)
PY
}

amp_start
cd "$REPO"

agent_status=127
if [[ -n "${AGENT_BIN}" && -x "$AGENT_BIN" ]]; then
  set +e
  run_agent
  agent_status=$?
  if [[ "${agent_status}" -ne 0 ]]; then
    echo "agent failed (exit ${agent_status}); retrying once after 45s…"
    sleep 45
    run_agent
    agent_status=$?
  fi
  set -e
  echo "agent exit ${agent_status}"
else
  echo "cursor-agent not found; skipping to fallback ingest"
  agent_status=127
fi

if [[ "${agent_status}" -eq 0 ]]; then
  exit 0
fi

echo "agent unavailable after retry — running fallback ingest"
set +e
run_fallback_ingest
fallback_status=$?
set -e
echo "fallback exit ${fallback_status}"
if [[ "${fallback_status}" -eq 0 ]]; then
  exit 0
fi
exit "${agent_status}"

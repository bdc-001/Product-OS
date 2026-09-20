# Daily API Sync

## Objective

Three times a day at 09:00, 17:00, and 01:00 Asia/Kolkata, run the PM Platform ingest so Jira, Cliq, and the indexed `go_services` clone are current. Fix broken integrations if the fetch fails. Do not redesign the product.

This file is the contract for the scheduled Cursor Agent CLI job (`scripts/daily-api-sync.sh`). Keep the scheduled prompt short and follow these rules.

## APIs

Auth lives in the repo-root `.env` (never commit it). Do not print secrets.

| Source | What to pull | How |
|---|---|---|
| **Jira** | Sense (`AC`) and Product Support (`PS`) tickets in PM scope | `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` |
| **Zoho Cliq** | Recent chats the PM is in | `CLIQ_*` OAuth tokens (`cliq.zoho.in`) |
| **go_services git** | Fetch origin branches; pull/index the current product branch | `CODEBASE_PATH` (Desktop `go_services` clone) |
| **Roadmap** | Sync epic/ticket statuses from Jira after ingest | Part of platform refresh |
| **Release detect** | Queue merged `release/YYYY-MM-DD` branches | Part of platform refresh |

Product Marketing is an authorized post-refresh step: the central Opus 4.8 PMM may discover released Sense features into the marketing mastersheet and the Product Marketing Google Sheet (`MARKETING_SHEET_ID`, columns Module / Feature / Description / Use Case / Industry). Discovery keeps buyer-facing capabilities (including small operator tools such as phone-number rotation) and skips engineer/internal/infra work; non-sellable rows are dismissed, never deleted. Campaign production is started manually from `/marketing` (Start on a feature). Approved artifacts still store in the existing Google Drive artifact folder. Do not publish Comms, approve release jobs, post to social channels, or send mail. SMTP remains outside scheduled ingest.

LLM (`LLM_API_KEY`) is optional. If it is down, still ingest; standup may be heuristic.

## How to fetch

Prefer the in-process refresh so this job works even if uvicorn is not running:

```bash
cd backend
.venv/bin/python - <<'PY'
import json
from app.database import SessionLocal
from app.services.refresh import refresh_platform
db = SessionLocal()
try:
    print(json.dumps(refresh_platform(db), default=str, indent=2))
finally:
    db.close()
PY
```

If `http://127.0.0.1:8000/api/health` is already up, `POST /api/refresh` is equivalent (poll the job until it finishes). Do not start a second uvicorn on port 8000.

`refresh_platform` already: ingests Jira + Cliq, syncs roadmap statuses, pulls/indexes the product branch, fetches origin branches, enqueues detected releases, then runs Product Marketing discovery into the mastersheet and Google Sheet (sellable buyer features only; production remains manual from `/marketing`). If the Google Sheet returns 403, share it with the Drive service-account email as Editor and continue; do not invent tokens.

## Authentication

- Read `.env` via the existing Settings object. Do not rewrite credentials.
- If Jira/Cliq report unconfigured or 401, log it and continue the other sources. Do not invent tokens.
- Cliq login expiry is a known failure mode. Record it; do not open a browser OAuth flow from this unattended job.
- Git remote fetch may fail without VPN/whitelist. Record `remote_blocked`; keep local branches.

## Output

Write a dated summary to `data/daily-sync/YYYY-MM-DD.md` (IST date):

- Time started / finished
- Per step: Jira, Cliq, codebase, branches, releases, roadmap, marketing — ok/fail, counts, error text
- Files the agent changed (if any)
- Tests run and result
- Items that need Arsalaan

Do not dump raw API payloads or tokens into that file.

## Validation

From `backend/`:

```bash
.venv/bin/python -m pytest tests/test_refresh_jobs.py tests/test_release_asks.py -q
```

If ingest returned errors, say so in the summary even when tests pass (tests are local/unit).

## Rules

- Never delete existing SQLite data, `data/stores/`, or dismissed release-ask records.
- Never modify `.env`, service-account JSON, Cliq tokens, or `data/cliq_token.json`.
- Never send Cliq (no `deliver_standup`, no `POST /standup/deliver`, no release-ask nudges, no DMs).
- Never `git commit` or `git push`.
- Never change architecture, the MUI design system, or unrelated app code unless a fetch path is actually broken.
- Retry failed HTTP/git steps once or twice with backoff; then log and move on.
- Do not stash/pop `go_services` except through the existing indexer.
- Sense stays AC-only. Copilot remains the only Jira write path, and only after Approve — this job must not write Jira.
- Timezone is `Asia/Kolkata`.

## Operator setup

Mac keep-awake: Amphetamine is installed. The launchd wrapper also runs `caffeinate` for the duration of the job and starts a timed Amphetamine session if AppleScript is allowed.

If the Cursor Agent CLI cannot stay connected to Cursor cloud, the launchd runner retries once, then falls back to in-process `refresh_platform` and still writes `data/daily-sync/YYYY-MM-DD.md` (tests may be skipped in fallback).

Install/refresh the agent with `./scripts/install-daily-sync.sh`. That copies the runner to `~/Library/Application Support/sourabh-bot/bin/` and points launchd at a `.command` opened via `/usr/bin/open` so Terminal.app can read the Desktop repo (bare launchd cannot). Re-run install after editing `scripts/daily-api-sync.sh`.

Prefer free/subscription auth: `~/.local/bin/cursor-agent login` once. Do not set `CURSOR_API_KEY` unless you want API billing.

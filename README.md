# Product OS

The personal product operating system for a PM.

It is the desk you sit at in the morning: Jira and Cliq already correlated, the `codebase` clone indexed, prototypes you can click, notes you can file from, Copilot that will not write Jira until you Approve, and a marketing lane that discovers shippable features without posting anything on its own.

---

## What it is for

Product OS is not a generic chatbot with a Jira plugin. It is a workspace that already knows the product:

| Area | What you do here |
| --- | --- |
| **This week** | Evidence-backed standup. Tickets, chats, and code in one briefing. |
| **Jira / Support** | Boards in your PM scope. Copilot is the only Jira write path, and only after **Approve**. |
| **Cliq** | Threads the PM is in. Ingest is read-only from the scheduled job. |
| **Codebase** | Local `codebase` clone. Index a branch, search, cite files. |
| **Prototype** | Your product's sandboxes with production-shaped routes. Table of projects, last modified, filters. **Write PRD** attaches the prototype to Copilot. |
| **PRD** | Ground a spec in indexed code, tagged AC tickets, and/or a Sense prototype. Export markdown or PDF. |
| **Roadmap / Features / Artifacts / Comms** | Epic status, feature extract, docs, and release communication drafts. |
| **Notes** | Meetings, dailies, decisions, learnings. Date filter, delete, structure/summarise/extract, file a ticket from an actionable. |
| **LMS / Competitors / Marketing** | Library, competitive signals, sellable-feature discovery. Campaign production starts manually from `/marketing`. |
| **Settings** | Tokens, models, and workspace overlay. Sensitive fields stay encrypted on disk. |
| **Copilot** | Floating assistant. Reads code, notes, documents, and prototype files. Does not send Cliq. Does not write Jira until you Approve. |

Timezone for the product is **Asia/Kolkata**.

---

## Architecture

```
browser  :3000  Next.js (MUI)
              │  /api/*  rewrite
              ▼
API      :8000  FastAPI + SQLite (data/pm_agent.db, local only)
              │
              ├── Jira
              ├── Zoho Cliq (cliq.zoho.in)
              ├── local codebase git clone
              ├── Google Drive / Sheets (marketing, optional)
              └── LLM (optional — ingest still works without it)
```

- **Frontend** (`frontend/`): App Router, client pages, Copilot widget, prototype studio.
- **Backend** (`backend/`): ingest, standup, Copilot plans, prototype kit, PRD, marketing discovery.
- **Data** (`data/`): SQLite, tokens, prototype files, indexes. **Not in git.**
- **Product clone**: `CODEBASE_PATH` (Desktop `codebase`). **Not in this repo.**

---

## Quick start

**1. Clone and configure**

```bash
git clone https://github.com/bdc-001/Product-OS.git
cd Product-OS
cp .env.example .env
```

Fill `.env` or, after first run, use **Settings** in the app (preferred). The app writes `data/workspace.json` and encrypted `data/workspace.secrets.json`. It does not rewrite `.env`.

**2. Backend**

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**3. Frontend** (another terminal)

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Do not start a second uvicorn on 8000.

**4. Point at product code**

Set `CODEBASE_PATH` to your local `codebase` clone. Index a branch from **Codebase**. Git fetch may need VPN/whitelist; if remote fetch fails, keep local branches.

---

## Environment

Copy from [`.env.example`](.env.example). Never commit `.env`, service-account JSON, or `data/cliq_token.json`.

| Group | Variables | Notes |
| --- | --- | --- |
| Jira | `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `JIRA_PROJECTS` | Sense `AC` + support `PS`. |
| Cliq | `CLIQ_*` | OAuth against `cliq.zoho.in`. Login expiry is a known failure; record it, do not open a browser OAuth flow from the unattended job. |
| LLM | `LLM_API_KEY`, `LLM_MODEL`, `LLM_COPILOT_MODEL`, optional docs model | Optional. If down, ingest still runs; standup may be heuristic. |
| Code | `CODEBASE_PATH`, `CODEBASE_PULL` | Absolute path to `go_services`. |
| Mail | `SMTP_*`, `RELEASE_NOTES_*` | Outside scheduled ingest. Not used to auto-post Comms. |
| Drive | `GDRIVE_*`, `MARKETING_SHEET_ID` | Share the sheet with the Drive service-account email as Editor if you get 403. |

Configure models and secrets in **Settings** when you can. Masked fields stay masked until you paste a new value.

---

## Copilot and Jira

Copilot may **read** Jira, Cliq, notes, library documents, indexed `go_services`, and Sense prototype code.

It may **write Jira** only after you click **Approve** on a plan. That is the only Jira write path.

It must **not**, from the scheduled ingest job:

- send Cliq (no standup delivery, no DMs, no release-ask nudges)
- `git commit` / `git push`
- rewrite `.env` or Cliq tokens
- delete SQLite data, `data/stores/`, or dismissed release-ask records

**Write PRD** on a prototype attaches that sandbox and asks Copilot to ground a spec in the prototype files and prompt history. The PRD is saved under **PRD**; it is not a Jira ticket.

---

## Daily API sync

Three times a day at **09:00, 17:00, and 01:00** Asia/Kolkata, a Cursor Agent CLI job runs the platform ingest. Contract: [`AGENTS.md`](AGENTS.md). Runner: [`scripts/daily-api-sync.sh`](scripts/daily-api-sync.sh).

It pulls Jira + Cliq, syncs roadmap statuses, fetches/indexes the product branch, enqueues detected `release/YYYY-MM-DD` merges, then runs Product Marketing discovery into the mastersheet (sellable buyer features only). Campaign production stays manual.

Install on the Mac:

```bash
chmod +x scripts/daily-api-sync.sh scripts/install-daily-sync.sh
~/.local/bin/cursor-agent login   # once (subscription; skip CURSOR_API_KEY unless you want API billing)
./scripts/install-daily-sync.sh
```

Amphetamine + `caffeinate` keep the machine awake for the job. Logs: `~/Library/Logs/sourabh-bot/`.

In-process refresh (works even if uvicorn is down):

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

If `http://127.0.0.1:8000/api/health` is already up, `POST /api/refresh` is equivalent. Poll the job until it finishes.

---

## Tests

From `backend/`:

```bash
.venv/bin/python -m pytest tests/test_refresh_jobs.py tests/test_release_asks.py -q
```

Broader suite as you touch an area, for example:

```bash
.venv/bin/python -m pytest tests/test_knowledge.py tests/test_prototypes.py tests/test_copilot_run.py tests/test_prd_pdf.py -q
```

---

## Repository layout

```
backend/          FastAPI app, tests, prototype kit
frontend/         Next.js UI
scripts/          Daily sync + launchd install
docs/             Design notes (prototype editing, marketing, UI)
.github/          Optional GitHub Action for release-notes email
AGENTS.md         Contract for the unattended ingest agent
```

**Not in this repository (on purpose):** `.env`, SQLite and workspace secrets, Cliq tokens, prototype file trees, marketing renders, and the `go_services` product clone. This GitHub remote is public — keep credentials and vendor source on the machine.

---

## Docs

- [`docs/prototype-editing.md`](docs/prototype-editing.md) — how Prototype applies precise edits
- [`docs/product-marketing.md`](docs/product-marketing.md) — discovery vs campaign production
- [`docs/frontend-design-system.md`](docs/frontend-design-system.md) — UI tokens

---

## License

Private product tooling. All rights reserved unless a license file is added later.

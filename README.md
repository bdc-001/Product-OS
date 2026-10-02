# Product OS

A self-hosted workspace for product work: notes, requirements, interactive prototypes, document libraries, release planning, and marketing drafts.

Connect your own tools and repository through **Settings**. Start with notes and documents, then enable the integrations your workflow needs.

## Workspace

| Area | Purpose |
| --- | --- |
| Notes | Capture meetings, decisions, actions, and learnings. |
| PRD | Write and edit requirements, optionally generate a draft from tickets and code, and save PDF snapshots to LMS. |
| Prototype | Create interactive prototypes and refine them in the studio. |
| LMS | Search uploaded documents and saved PRD PDFs; filter by document type and reading status. |
| Jira and chat | Bring configured project tickets and supported chat sources into context. |
| Codebase | Index a branch of your own local Git checkout. |
| Roadmap, Comms, and Artifacts | Plan work and prepare release documents. |
| Marketing | Discover candidate features and manually start campaign production. |
| Copilot | Use workspace context to draft answers and proposed actions. Jira writes require approval. |

Settings has its own navigation for general configuration, repository and branch, integrations, models, content and storage, mail, and security.

## Quick start

Requires Python 3.11+ and Node.js 20.9+.

```bash
git clone https://github.com/bdc-001/Product-OS.git
cd Product-OS
cp .env.example .env
```

Start the API:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal, start the UI:

```bash
cd frontend
npm install
npm run dev
```

Open [Product OS](http://localhost:3000). The [API health endpoint](http://127.0.0.1:8000/api/health) reports backend availability.

## Configure your workspace

Use the in-app Settings pages or the variables documented in [`.env.example`](.env.example). Settings stores a local overlay and encrypted secret values under `data/`; it does not rewrite `.env`.

| Connection | Configuration |
| --- | --- |
| Jira | Your base URL, account credentials, and comma-separated project keys in `JIRA_PROJECTS`. |
| Repository | Your local checkout path in `CODEBASE_PATH`; choose and index the product branch in Settings → Codebase & branch. |
| Chat | Supported Zoho Cliq OAuth credentials and regional API endpoints. |
| AI | Provider endpoint, API key, and model routes. Generation requires a compatible configured provider. |
| Google Drive / Sheets | Your service account, destination folders, and spreadsheet ID. Grant the service account access to those resources. |
| Mail | Your SMTP settings and intended recipients, when using mail workflows. |
| Locale | Set `TIMEZONE` and the schedules appropriate for your workspace. |

Jira project keys, repository paths, Drive domains, and spreadsheet IDs have no personal defaults. Existing installations retain explicit environment and workspace settings.

### Extending Product OS

Current connectors support Jira, Zoho Cliq, local Git, and Google Drive/Sheets. This is not yet a drop-in plugin marketplace: adding another tracker or chat provider requires a backend adapter and its settings/UI wiring.

- Configuration and validation: `backend/app/config.py`, `backend/app/services/workspace.py`.
- Integration and workflow implementations: `backend/app/services/`.
- HTTP routes: `backend/app/api/routers/`.
- Shared UI primitives and styling: `frontend/app/ui/`, `frontend/app/theme.ts`.

Some prototype templates, discovery rules, and assistant workflows still contain product-specific assumptions. Review and adapt these before using those workflows with another product. The generic document editor and library do not require an indexed repository.

## Data and approvals

Local data includes SQLite records, uploaded documents, generated artifacts, indexes, and prototype files. Back up the local data directory before moving or upgrading an installation.

Do not commit `.env`, workspace data, tokens, service-account files, generated private artifacts, or a connected product repository. Encrypted secrets do not replace host access controls. The development server is intended for local use; review authentication and deployment controls before exposing it to a network.

Copilot proposes Jira writes for approval. Campaign production starts manually. Saving a PRD PDF stores a snapshot in the local LMS library; it does not upload it to Google Drive. Changed documents produce a new snapshot, while saving identical content reuses the existing PDF.

## Development

```bash
# Backend regression tests
cd backend
.venv/bin/python -m pytest tests/test_knowledge.py tests/test_prd_pdf.py tests/test_prd_editor.py -q
```

```bash
# Frontend checks, from the repository root
cd frontend
npx tsc --noEmit
node --test tests/http.test.cjs
```

Optional local automation and server helpers live in `scripts/`. Review their schedules, paths, and agent instructions for your environment before installing them. They are not required for interactive use.

## Documentation

- [Design system](docs/platform-design-system.md)
- [Prototype editing](docs/prototype-editing.md)
- [Product marketing](docs/product-marketing.md)

## License

No open-source license is currently granted. See any future LICENSE file for applicable terms.

"""Sense UI prototype sandbox. Files stay in Sourabh_Bot; never write go_services."""

from __future__ import annotations

import html
import json
import posixpath
import io
import logging
import re
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.clients.llm import chat_json
from app.config import ROOT
from app.models import Prototype, PrototypeFile, PrototypeMessage
from app.services.prompts import parse_json_object
from app.services.prototype_lovable import KIT_ROOT, copy_kit, kit_files, link_node_modules
from app.services.prototype_runtime import ensure_preview

log = logging.getLogger(__name__)

PROTO_DIR = ROOT / "data" / "prototypes"
MAX_FILE_CHARS = 400_000
MAX_FILES = 400
ROOT_FILES = {
    "package.json",
    "vite.config.ts",
    "tsconfig.json",
    "components.json",
    "eslint.config.js",
    "bunfig.toml",
    "index.html",
    "PORTING.md",
    "tailwind.port-extend.js",
}
ALLOWED_ROOTS = ("src/", "public/")
ALLOWED_EXT = {".jsx", ".tsx", ".js", ".ts", ".css", ".json", ".svg", ".md", ".toml", ".html", ".mjs", ".cjs"}
SECRET_BITS = ("node_modules", ".env", ".git", "secret", "credentials", "id_rsa")

SYSTEM_PROMPT = """Implement the user's requested change in the CURRENT Sense prototype.
Treat the latest request as a precise change specification, not an invitation to redesign.
Resolve the named screen, control, states and interactions against current_files. Current
files are authoritative; history describes prior intent, and kit is style guidance only.
Preserve earlier working changes, routes, layout, labels, fixtures and unrelated behavior.
If a field or action is requested, wire its state, validation and visible result as well
as its appearance. Use existing components and tokens. Keep tenantPath()/withQuery(),
react-router-dom, /tenant/:tenantId routes, Figtree and the seeded Sense design system.
Do not add auth or write go_services. Modify one screen unless the user requests more.

Return JSON:
{"title": str, "notes": str,
 "edits": [{"path": str, "old": str, "new": str}], "files": []}
Prefer exact edits: old is an exact, unique block from the complete current file; new
replaces that block. Multiple edits to a file apply sequentially. Do not abbreviate code.
For a deliberate whole-file rewrite you may return files [{"path": str,"content": str}]
with FULL content. Do not mix edits and full contents for the same file.
Only edit paths supplied with complete content in current_files. If required source is
missing, return {"read_paths": [existing paths from tree]} to fetch it before editing.
Never guess unseen code. Never return unchanged files or "rest unchanged" placeholders.
In notes, state the implemented behavior and a concrete way to try it. Disclose any
unimplemented part. Do not claim tests ran. If a critical ambiguity prevents the change,
return no edits and ask one specific question in notes. Otherwise make the smallest
reasonable assumption and implement. The latest explicit instruction overrides history.
"""


class PrototypePathError(ValueError):
    pass


def sanitize_path(raw: str) -> str:
    text = (raw or "").replace("\\", "/").strip().lstrip("/")
    if not text:
        raise PrototypePathError("Path not allowed")
    parts = [p for p in text.split("/") if p not in ("", ".")]
    if ".." in parts or not parts:
        raise PrototypePathError("Path not allowed")
    text = "/".join(parts)
    lower = text.lower()
    if any(bit in lower for bit in SECRET_BITS):
        raise PrototypePathError("Path not allowed")
    for prefix in ("convin-activate/static/", "static/"):
        if text.startswith(prefix):
            text = text[len(prefix) :]
    if text in ROOT_FILES:
        return text
    if not any(text.startswith(root) for root in ALLOWED_ROOTS):
        text = "src/" + text
    if text in ROOT_FILES:
        return text
    if not any(text.startswith(root) for root in ALLOWED_ROOTS):
        raise PrototypePathError("Path not allowed")
    suffix = Path(text).suffix.lower()
    if suffix not in ALLOWED_EXT:
        raise PrototypePathError("Path not allowed")
    if len(text) > 240:
        raise PrototypePathError("Path not allowed")
    return text


def _proto_root(prototype_id: int) -> Path:
    root = (PROTO_DIR / str(int(prototype_id))).resolve()
    base = PROTO_DIR.resolve()
    if root != base and base not in root.parents:
        raise PrototypePathError("Path not allowed")
    return root


def _write_disk(prototype_id: int, files: list[PrototypeFile]) -> None:
    root = _proto_root(prototype_id)
    root.mkdir(parents=True, exist_ok=True)
    for row in files:
        path = sanitize_path(row.path)
        dest = (root / path).resolve()
        if root not in dest.parents and dest != root:
            raise PrototypePathError("Path not allowed")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(row.content or "", encoding="utf-8")


def _write_one(prototype_id: int, path: str, content: str) -> None:
    _write_disk(prototype_id, [PrototypeFile(prototype_id=prototype_id, path=path, content=content)])


def heuristic_files(prompt: str = "") -> list[dict]:
    del prompt
    return kit_files()


def _read_kit(rel: str, limit: int = 3500) -> str:
    path = KIT_ROOT / rel
    try:
        if not path.is_file():
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")[:limit]
    except OSError:
        return ""


def sense_kit_context(prompt: str = "") -> str:
    bits = [
        "This sandbox is production-shaped Sense UI (Vite SPA, react-router-dom, /tenant/:tenantId).",
        "Chrome: AppSidebar #f6f8fb, Main / AI / Human, TopBar + search portal, FilterBar chips.",
        "Page files: src/pages/Campaigns.jsx, AgentManagement.jsx, UnifiedLeads.jsx, Analytics.jsx, Tools.jsx, KnowledgeBase.jsx, AgentWorkspace.jsx, Settings.jsx.",
        "Visuals live in src/features/**. Routes are declared in src/App.jsx. Use src/lib/nav.ts tenantPath().",
        "Logo: overlapping #5B8DEF / #5CE1E6 circles in src/assets/sense-logo.svg before the Sense wordmark.",
    ]
    for rel in (
        "src/pages/Campaigns.jsx",
        "src/App.jsx",
        "src/lib/nav.ts",
        "src/components/layout/AppSidebar.tsx",
        "src/components/filters/FilterBar.tsx",
        "src/features/campaigns/CampaignsListPage.tsx",
        "src/styles.css",
    ):
        body = _read_kit(rel, 2200)
        if body:
            bits.append(f"{rel} excerpt:\n{body}")
    q = (prompt or "").lower()
    extras = []
    if "agent" in q:
        extras.append("src/pages/AgentManagement.jsx")
        extras.append("src/features/agents/AgentWizardPage.tsx")
    if "customer" in q or "lead" in q:
        extras.append("src/pages/UnifiedLeads.jsx")
        extras.append("src/features/customers/CustomersPage.tsx")
    if "analytic" in q:
        extras.append("src/pages/Analytics.jsx")
        extras.append("src/features/analytics/AnalyticsPage.tsx")
    if "setting" in q or "billing" in q or "phone" in q:
        extras.append("src/pages/Settings.jsx")
        extras.append("src/features/settings/components/PhoneNumbers.tsx")
    if "wizard" in q or "campaign" in q:
        extras.append("src/pages/Campaigns.jsx")
        extras.append("src/features/campaigns/CampaignWizardPage.tsx")
    if "tool" in q:
        extras.append("src/pages/Tools.jsx")
    if "knowledge" in q:
        extras.append("src/pages/KnowledgeBase.jsx")
    if "human" in q or "workspace" in q:
        extras.append("src/pages/AgentWorkspace.jsx")
    for rel in extras:
        body = _read_kit(rel, 1800)
        if body:
            bits.append(f"{rel} excerpt:\n{body}")
    return "\n\n".join(bits)[:16000]


def prototype_out(row: Prototype, db: Session, *, detail: bool = False) -> dict:
    data = {
        "id": row.id,
        "title": row.title,
        "status": row.status,
        "error": row.error or "",
        "llm_used": bool(row.llm_used),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
    if not detail:
        return data
    files = (
        db.query(PrototypeFile)
        .filter(PrototypeFile.prototype_id == row.id)
        .order_by(PrototypeFile.path)
        .all()
    )
    messages = (
        db.query(PrototypeMessage)
        .filter(PrototypeMessage.prototype_id == row.id)
        .order_by(PrototypeMessage.id)
        .all()
    )
    data["files"] = [{"path": f.path, "content": f.content} for f in files]
    data["messages"] = [
        {
            "id": m.id,
            "role": m.role,
            "body": m.body,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages
    ]
    return data


def _merge_files(db: Session, prototype_id: int, incoming: list[dict]) -> list[str]:
    kept: list[str] = []
    existing = {
        row.path: row
        for row in db.query(PrototypeFile).filter(PrototypeFile.prototype_id == prototype_id).all()
    }
    for item in incoming[:MAX_FILES]:
        if not isinstance(item, dict):
            continue
        try:
            path = sanitize_path(str(item.get("path") or ""))
        except PrototypePathError:
            continue
        content = str(item.get("content") or "")
        if len(content) > MAX_FILE_CHARS:
            content = content[:MAX_FILE_CHARS]
        row = existing.get(path)
        if row:
            row.content = content
            row.updated_at = datetime.utcnow()
        else:
            row = PrototypeFile(prototype_id=prototype_id, path=path, content=content)
            db.add(row)
            existing[path] = row
        kept.append(path)
    db.flush()
    files = db.query(PrototypeFile).filter(PrototypeFile.prototype_id == prototype_id).all()
    try:
        _write_disk(prototype_id, files)
    except OSError:
        log.exception("could not mirror prototype %s to disk", prototype_id)
    return kept


def seed_prototype(db: Session, title: str = "", prompt: str = "") -> Prototype:
    row = Prototype(
        title=(title or prompt or "Sense").strip()[:180] or "Sense",
        status="ready",
        error="",
        llm_used=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(row)
    db.flush()
    reset_working_tree(row.id)
    _merge_files(db, row.id, kit_files())
    db.commit()
    db.refresh(row)
    return row


def reset_working_tree(prototype_id: int) -> None:
    root = _proto_root(prototype_id)
    if root.exists():
        for child in root.iterdir():
            if child.name == "node_modules":
                continue
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child, ignore_errors=True)
            else:
                try:
                    child.unlink()
                except OSError:
                    pass
    copy_kit(root)
    link_node_modules(root)


def reset_to_kit(db: Session, prototype_id: int) -> Prototype:
    row = db.get(Prototype, prototype_id)
    if not row:
        raise LookupError("Prototype not found")
    db.query(PrototypeFile).filter(PrototypeFile.prototype_id == prototype_id).delete()
    db.flush()
    reset_working_tree(prototype_id)
    _merge_files(db, prototype_id, kit_files())
    row.updated_at = datetime.utcnow()
    row.status = "ready"
    row.error = ""
    db.commit()
    db.refresh(row)
    return row


def put_file(db: Session, prototype_id: int, path: str, content: str) -> dict:
    row = db.get(Prototype, prototype_id)
    if not row:
        raise LookupError("Prototype not found")
    clean = sanitize_path(path)
    body = (content or "")[:MAX_FILE_CHARS]
    existing = (
        db.query(PrototypeFile)
        .filter(PrototypeFile.prototype_id == prototype_id, PrototypeFile.path == clean)
        .one_or_none()
    )
    if existing:
        existing.content = body
        existing.updated_at = datetime.utcnow()
    else:
        count = db.query(PrototypeFile).filter(PrototypeFile.prototype_id == prototype_id).count()
        if count >= MAX_FILES:
            raise PrototypePathError("Too many files")
        db.add(PrototypeFile(prototype_id=prototype_id, path=clean, content=body))
    row.updated_at = datetime.utcnow()
    db.commit()
    try:
        _write_one(prototype_id, clean, body)
    except OSError:
        log.exception("could not write %s for prototype %s", clean, prototype_id)
    return prototype_out(row, db, detail=True)


def _history(db: Session, prototype_id: int) -> list[dict]:
    query = db.query(PrototypeMessage).filter(PrototypeMessage.prototype_id == prototype_id)
    recent = query.order_by(PrototypeMessage.id.desc()).limit(10).all()
    first = query.order_by(PrototypeMessage.id.asc()).first()
    rows = list(reversed(recent))
    if first and all(r.id != first.id for r in rows):
        rows.insert(0, first)
    return [{"role": r.role, "text": r.body[:8500]} for r in rows]


def _turn_files(db: Session, prototype_id: int, prompt: str) -> list[dict]:
    files = db.query(PrototypeFile).filter(PrototypeFile.prototype_id == prototype_id).all()
    by_path = {item.path: item for item in files}
    stop = {"the", "and", "with", "that", "this", "change", "make", "should", "please", "add", "have", "when", "from", "then", "only"}
    tokens = set(re.findall(r"[a-z]{3,}", prompt.lower())) - stop
    phrases = re.findall(r'["“]([^"”]+)["”]', prompt)
    def score(item):
        path, body = item.path.lower(), (item.content or '').lower()
        return (100 if item.path in prompt else 0) + sum(8 for t in tokens if t in path) + sum(2 for t in tokens if t in body) + sum(18 for phrase in phrases if phrase.lower() in body)
    ranked = sorted(files, key=lambda item: (-score(item), item.path))
    selected, seen, used = [], set(), 0
    def add(path):
        nonlocal used
        item = by_path.get(path)
        if not item or path in seen or used + len(item.content or '') > 110000:
            return False
        selected.append({"path": path, "content": item.content or ''})
        seen.add(path)
        used += len(item.content or '')
        return True
    # The named screen and control win over generic shell/campaign context.
    for item in ranked[:6]:
        if score(item):
            add(item.path)
    for path in ['src/App.jsx', 'src/lib/nav.ts', 'src/styles.css']:
        add(path)
    # Include local imports so a page wrapper leads to its actual component/state.
    for item in list(selected):
        for spec in re.findall(r'(?:from\s*|import\s*)[\'"]([^\'"]+)[\'"]', item['content']):
            base = 'src/' + spec[2:] if spec.startswith('@/') else posixpath.normpath(posixpath.join(posixpath.dirname(item['path']), spec)) if spec.startswith('.') else ''
            if base:
                for suffix in ['', '.tsx', '.ts', '.jsx', '.js', '/index.tsx', '/index.ts', '/index.jsx']:
                    if add(base + suffix):
                        break
    return [{"tree": "\n".join(sorted(by_path)), "content_policy": "Complete files only. Request read_paths for omitted files."}] + selected


def prototype_pack(db: Session, prototype_id: int, prompt: str = "") -> dict:
    row = db.get(Prototype, prototype_id)
    if not row:
        raise LookupError("Prototype not found")
    packed = _turn_files(db, prototype_id, prompt or row.title or "prototype")
    tree = next((str(item.get("tree") or "") for item in packed if item.get("tree")), "")
    files = [
        {"path": str(item.get("path") or ""), "content": str(item.get("content") or "")[:12000]}
        for item in packed
        if item.get("path")
    ]
    return {
        "id": row.id,
        "title": row.title,
        "status": row.status,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "tree": tree[:8000],
        "files": files[:14],
        "messages": _history(db, prototype_id)[-8:],
    }


def _generated_files(parsed: dict, current: list[dict]) -> list[dict]:
    """Validate the entire edit set before touching any file; an ambiguous edit is atomic."""
    originals = {f['path']: f['content'] for f in current if 'path' in f}
    changed, whole = {}, set()
    for item in parsed.get('files') or []:
        if not isinstance(item, dict):
            raise ValueError('Invalid generated file; no changes applied.')
        path = sanitize_path(str(item.get('path') or ''))
        content = item.get('content')
        if path not in originals or path in whole or not isinstance(content, str) or not content.strip() or len(content) > MAX_FILE_CHARS:
            raise ValueError('Generated file is missing complete context or has invalid content; no changes applied.')
        changed[path], whole = content, whole | {path}
    for edit in parsed.get('edits') or []:
        if not isinstance(edit, dict):
            raise ValueError('Invalid generated edit; no changes applied.')
        path = sanitize_path(str(edit.get('path') or ''))
        old, new = edit.get('old'), edit.get('new')
        source = changed.get(path, originals.get(path))
        if path in whole or source is None or not isinstance(old, str) or not old or not isinstance(new, str) or source.count(old) != 1:
            raise ValueError('An exact edit did not match a unique block in the current file; no changes applied. Try again with the target control named.')
        changed[path] = source.replace(old, new, 1)
        if not changed[path].strip() or len(changed[path]) > MAX_FILE_CHARS:
            raise ValueError('Invalid edit result; no changes applied.')
    return [{"path": path, "content": content} for path, content in changed.items() if content != originals[path]]


def run_turn(db: Session, prototype_id: int, prompt: str, *, target: str = "") -> dict:
    row = db.get(Prototype, prototype_id)
    if not row:
        raise LookupError("Prototype not found")
    text = (prompt or "").strip()
    if not text:
        raise ValueError("Describe the screen to generate.")
    history = _history(db, row.id)
    row.status = "generating"
    row.error = ""
    row.updated_at = datetime.utcnow()
    db.add(PrototypeMessage(prototype_id=row.id, role="user", body=((f"Target: {target}\n\n" if target else "") + text)[:8500]))
    db.commit()

    try:
        payload = {
            "prompt": text,
            "target": target,
            "kit": "Use the existing Sense components, Figtree, Tailwind tokens and tenant routes. current_files override all historical code.",
            "current_files": _turn_files(db, row.id, target + "\n" + text + "\n" + next((h["text"] for h in reversed(history) if h["role"] == "user"), "")[:800]),
            "history": history,
        }
        llm_used = False
        notes = ""
        title = row.title
        incoming: list[dict] = []
        try:
            data = chat_json(
                "prototype",
                SYSTEM_PROMPT,
                payload,
                max_chars=len(json.dumps(payload, default=str)) + 1000,
                timeout=120,
                max_retries=1,
            )
            parsed = parse_json_object(data)
            if parsed.get("read_paths"):
                known = {f.path: f.content for f in db.query(PrototypeFile).filter(PrototypeFile.prototype_id == row.id).all()}
                for path in parsed['read_paths'][:8]:
                    if path in known and not any(f.get('path') == path for f in payload['current_files']):
                        if sum(len(f.get('content', '')) for f in payload['current_files']) + len(known[path]) <= 220000:
                            payload['current_files'].append({'path': path, 'content': known[path]})
                data = chat_json('prototype', SYSTEM_PROMPT, payload,
                                 max_chars=len(json.dumps(payload, default=str)) + 1000, timeout=120, max_retries=1)
                parsed = parse_json_object(data)
            notes = str(parsed.get("notes") or "")[:2000]
            title = str(parsed.get("title") or title)[:180]
            llm_used = True
        except Exception as exc:
            log.info("prototype LLM fallback: %s", exc)
            notes = "LLM unavailable — the Lovable Sense app is unchanged. Try again after the model is up."
            llm_used = False

        if llm_used:
            incoming = _generated_files(parsed, payload['current_files'])
            originals = {f['path']: f['content'] for f in payload['current_files'] if 'path' in f}
            db.expire_all()
            latest = {f.path: f.content for f in db.query(PrototypeFile).filter(PrototypeFile.prototype_id == prototype_id).all()}
            if any(latest.get(f['path']) != originals[f['path']] for f in incoming):
                raise ValueError('This file was edited while generation ran. Your manual changes are preserved; retry the request.')
        kept: list[str] = []
        if incoming:
            kept = _merge_files(db, row.id, incoming)
        if incoming and not kept:
            notes = "Generated paths were rejected — left the Lovable Sense app unchanged."
            llm_used = False
        elif not incoming:
            notes = notes or "No files returned — left the Lovable Sense app unchanged."

        if kept:
            notes = (notes + "\n\nChanged: " + ", ".join(kept)).strip()
        row = db.get(Prototype, prototype_id)
        row.title = title or row.title
        row.status = "ready"
        row.llm_used = llm_used
        row.error = ""
        row.updated_at = datetime.utcnow()
        db.add(PrototypeMessage(prototype_id=row.id, role="assistant", body=notes or "Updated the prototype."))
        db.commit()
        db.refresh(row)
        return {"ok": True, "llm_used": llm_used, "title": row.title, "files": kept}
    except Exception as exc:
        log.exception("prototype turn failed")
        failed = db.get(Prototype, prototype_id)
        if failed:
            failed.status = "error"
            failed.error = str(exc)[:800]
            failed.updated_at = datetime.utcnow()
            db.commit()
        raise


def preview_target(db: Session, prototype_id: int) -> tuple[str, str]:
    row = db.get(Prototype, prototype_id)
    if not row:
        raise LookupError("Prototype not found")
    root = _proto_root(prototype_id)
    if not (root / "package.json").is_file():
        reset_working_tree(prototype_id)
        if not db.query(PrototypeFile).filter(PrototypeFile.prototype_id == prototype_id).count():
            _merge_files(db, prototype_id, kit_files())
            db.commit()
    return ensure_preview(root, prototype_id)


def preview_html(db: Session, prototype_id: int) -> str:
    url, error = preview_target(db, prototype_id)
    if not url:
        message = error or "Sense preview could not start."
        return (
            "<!doctype html><html><head><meta charset='utf-8'><title>Sense preview</title></head>"
            "<body style='font-family:Figtree,sans-serif;padding:48px;color:#374151'>"
            "<h1>Sense preview</h1>"
            f"<p>{html.escape(message)}</p>"
            "<p>The studio still holds the Lovable Sense source. Install Node.js and retry.</p>"
            "</body></html>"
        )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Sense</title>
  <style>html,body,iframe{{margin:0;height:100%;width:100%;border:0;background:#fff}}</style>
</head>
<body>
  <iframe src="{url}" title="Sense"></iframe>
</body>
</html>
"""


def export_zip(db: Session, prototype_id: int) -> bytes:
    row = db.get(Prototype, prototype_id)
    if not row:
        raise LookupError("Prototype not found")
    files = db.query(PrototypeFile).filter(PrototypeFile.prototype_id == prototype_id).all()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in files:
            try:
                path = sanitize_path(item.path)
            except PrototypePathError:
                continue
            zf.writestr(path, item.content or "")
        zf.writestr(
            "README.md",
            (
                f"# {row.title}\n\n"
                "This zip is the Sense prototype UI (Vite + react-router-dom, same visuals as Lovable).\n"
                "Routes and page filenames match production: /tenant/:tenantId/campaigns → src/pages/Campaigns.jsx.\n"
                "Copy into go_services using PORTING.md. Do not overwrite production App.jsx or Layout.jsx (auth).\n"
                "Run `npm install` then `npm run dev`. Nothing here is written to go_services.\n"
            ),
        )
    return buf.getvalue()

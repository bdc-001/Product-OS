"""UI prototype sandbox on the workspace's kit. Files stay in the platform; never write the product repo."""

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

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.clients.llm import chat_json
from app.config import ROOT, settings
from app.models import Prototype, PrototypeFile, PrototypeMessage
from app.services.prompts import parse_json_object
from app.services.prototype_lovable import copy_kit, kit_files, kit_name, kit_root, link_node_modules
from app.services.prototype_runtime import ensure_preview
from app.storage import WorkspaceDir

log = logging.getLogger(__name__)

PROTO_DIR = WorkspaceDir("prototypes")
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

SYSTEM_PROMPT = """Implement the user's requested change in the CURRENT prototype.
Treat the latest request as a precise change specification, not an invitation to redesign.
Resolve the named screen, control, states and interactions against current_files. Current
files are authoritative; history describes prior intent, and kit is style guidance only.
Preserve earlier working changes, routes, layout, labels, fixtures and unrelated behavior.
If a field or action is requested, wire its state, validation and visible result as well
as its appearance. Use existing components and tokens. __KIT_RULES__
Do not add auth or write the product repo. Modify one screen unless the user requests more.

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


KIT_GUIDES = {
    "starter": {
        "rules": "Keep the HashRouter routes in src/App.tsx, the Layout shell, fixtures in src/data/ and the Tailwind tokens in src/index.css.",
        "kit": "Use the starter kit's Layout, PageHeader, StatusPill, Tailwind tokens and fixtures. current_files override all historical code.",
    },
}


def kit_guide() -> dict:
    if kit_name() in KIT_GUIDES:
        return KIT_GUIDES[kit_name()]
    manifest = kit_manifest()
    starter = KIT_GUIDES["starter"]
    return {"rules": manifest.get("rules") or starter["rules"], "kit": manifest.get("kit") or starter["kit"]}


def system_prompt() -> str:
    return SYSTEM_PROMPT.replace("__KIT_RULES__", kit_guide()["rules"])


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
    ui = (settings.repo_ui_path or "").strip().strip("/")
    for prefix in (f"{ui}/" if ui else "", "static/"):
        if prefix and text.startswith(prefix):
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
    path = kit_root() / rel
    try:
        if not path.is_file():
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")[:limit]
    except OSError:
        return ""


def kit_manifest() -> dict:
    """The active kit's optional `kit.json`: rules, notes, context files, topic files and routes."""
    try:
        data = json.loads((kit_root() / "kit.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def kit_context(prompt: str = "") -> str:
    manifest = kit_manifest()
    if kit_name() == "starter" or not manifest:
        return starter_kit_context()
    bits = [str(note) for note in manifest.get("notes") or []]
    for rel in manifest.get("context_files") or []:
        body = _read_kit(rel, 2200)
        if body:
            bits.append(f"{rel} excerpt:\n{body}")
    q = (prompt or "").lower()
    extras: list[str] = []
    for topic, paths in (manifest.get("topics") or {}).items():
        if topic in q:
            extras.extend(path for path in paths if path not in extras)
    for rel in extras:
        body = _read_kit(rel, 1800)
        if body:
            bits.append(f"{rel} excerpt:\n{body}")
    return "\n\n".join(bits)[:16000]


def starter_kit_context() -> str:
    bits = ["This sandbox is the starter kit: a Vite SPA with react-router-dom HashRouter, Tailwind v4 tokens and fixtures."]
    for rel in ("src/App.tsx", "src/components/Layout.tsx", "src/pages/Items.tsx", "src/data/fixtures.ts", "src/index.css"):
        body = _read_kit(rel, 2200)
        if body:
            bits.append(f"{rel} excerpt:\n{body}")
    return "\n\n".join(bits)[:16000]


def prototype_out(row: Prototype, db: Session, *, detail: bool = False, include_files: bool = True) -> dict:
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
    messages = (
        db.query(PrototypeMessage)
        .filter(PrototypeMessage.prototype_id == row.id)
        .order_by(PrototypeMessage.id)
        .all()
    )
    if include_files:
        files = (
            db.query(PrototypeFile)
            .filter(PrototypeFile.prototype_id == row.id)
            .order_by(PrototypeFile.path)
            .all()
        )
        data["files"] = [{"path": f.path, "content": f.content} for f in files]
    else:
        data["files"] = []
        data["file_count"] = (
            db.query(func.count(PrototypeFile.id)).filter(PrototypeFile.prototype_id == row.id).scalar() or 0
        )
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
        title=(title or prompt or "Untitled prototype").strip()[:180] or "Untitled prototype",
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
    for path in ['src/App.jsx', 'src/utils/nav.ts', 'src/index.css']:
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
            "kit": kit_guide()["kit"],
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
                system_prompt(),
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
                data = chat_json('prototype', system_prompt(), payload,
                                 max_chars=len(json.dumps(payload, default=str)) + 1000, timeout=120, max_retries=1)
                parsed = parse_json_object(data)
            notes = str(parsed.get("notes") or "")[:2000]
            title = str(parsed.get("title") or title)[:180]
            llm_used = True
        except Exception as exc:
            log.info("prototype LLM fallback: %s", exc)
            notes = "LLM unavailable — the prototype is unchanged. Try again after the model is up."
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
            notes = "Generated paths were rejected — left the prototype unchanged."
            llm_used = False
        elif not incoming:
            notes = notes or "No files returned — left the prototype unchanged."

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
    row = db.get(Prototype, prototype_id)
    if not url:
        message = error or "The preview could not start."
        return (
            "<!doctype html><html><head><meta charset='utf-8'><title>Prototype preview</title></head>"
            "<body style='font-family:Inter,sans-serif;padding:48px;color:#374151'>"
            "<h1>Prototype preview</h1>"
            f"<p>{html.escape(message)}</p>"
            "<p>The studio still holds the prototype source. Install Node.js and retry.</p>"
            "</body></html>"
        )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(row.title or "Prototype")}</title>
  <style>html,body,iframe{{margin:0;height:100%;width:100%;border:0;background:#fff}}</style>
</head>
<body>
  <iframe src="{url}" title="{html.escape(row.title or "Prototype")}"></iframe>
</body>
</html>
"""


def export_zip(db: Session, prototype_id: int) -> bytes:
    from app.services.prototype_handoff import handoff_files
    row = db.get(Prototype, prototype_id)
    if not row:
        raise LookupError("Prototype not found")
    files = db.query(PrototypeFile).filter(PrototypeFile.prototype_id == prototype_id).all()
    buf = io.BytesIO()
    source = {}
    for item in files:
        try:
            source[sanitize_path(item.path)] = item.content or ""
        except PrototypePathError:
            continue
    generated = handoff_files(prototype_id, row.title, source)
    routes = (kit_manifest().get("routes") or "Routes live in src/App.tsx; each page is a file in src/pages/.") + "\n"
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path, content in {**source, **generated}.items():
            zf.writestr(path, content)
        zf.writestr(
            "README.md",
            (
                f"# {row.title}\n\n"
                "This zip contains the current prototype source and a production layout handoff.\n"
                f"{routes}"
                "Start with PORTING.md and handoff/manifest.json. Build the scoped CSS with node handoff/build-styles.mjs.\n"
                "Do not infer dimensions from production utility names. Do not overwrite production App or Layout files (auth).\n"
                "Run `npm install` then `npm run dev`. Nothing here is written to the product repo.\n"
            ),
        )
    return buf.getvalue()

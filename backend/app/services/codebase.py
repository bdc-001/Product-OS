"""Index the company clone in place. Never copy the repo into this project."""

from __future__ import annotations

import fcntl
import json
import re
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.clients.llm import LLMClient
from app.config import ROOT, settings
from app.models import CodebaseAsk, CodebaseModule, CodebaseSnapshot, GitStash
from app.services.profile import load_profile
from app.services.prompts import with_preamble
from app.services.time_window import format_ist, now_local, tz

SKIP_DIRS = {
    ".git",
    ".idea",
    ".vscode",
    ".venv",
    "venv",
    "node_modules",
    "vendor",
    "dist",
    "build",
    "coverage",
    "__pycache__",
    ".next",
    "target",
    "bin",
    "obj",
    "testdata",
    "fixtures",
}
SKIP_TOP = {"hack"}
SECRET_NAME = re.compile(r"(^|\.)(env|pem|key|p12|keystore)$|secret|credential|password|id_rsa", re.I)
REMOTE_BLOCKED = re.compile(
    r"whitelist your IP|could not read from remote|permission denied \(publickey\)|authentication failed|repository not found",
    re.I,
)
DOC_HINTS = ("readme", "architecture", "overview", "index", "product", "feature")
MAP_DIR = ROOT / "data" / "codebase"
GIT_LOCK_PATH = ROOT / "data" / "git.lock"
_git_thread_lock = threading.RLock()
_git_lock_depth = 0
_git_lock_fh = None
SUMMARIZE_PROMPT = with_preamble(
    """You are indexing Convin's go_services monorepo for a PM (Arsalaan).
For each module:
- summary: exactly 1-3 sentences.
- capabilities: 3-5 bullets, each under 20 words, starting with a verb.
Use only the provided tree, README, and docs.
If a module has no README or docs, set summary to "Not documented" rather than inferring from file or folder names.
Do not invent APIs or owners. Do not infer product behavior from directory names.

Return JSON:
{"modules": [{"name": "voicebot", "summary": "...", "capabilities": ["..."]}], "not_enough_evidence": ""}
"""
)


def codebase_root() -> Path:
    return Path(settings.codebase_path).expanduser()


GIT_LOCK_NAMES = (
    "index.lock",
    "HEAD.lock",
    "config.lock",
    "packed-refs.lock",
    "shallow.lock",
    "ORIG_HEAD.lock",
)


def clear_stale_git_locks(root: Path, max_age_s: float = 20) -> list[str]:
    """Remove leftover .git/*.lock files after a killed pull (uvicorn reload)."""
    git_dir = Path(root) / ".git"
    if not git_dir.is_dir():
        return []
    removed: list[str] = []
    candidates = [git_dir / name for name in GIT_LOCK_NAMES]
    refs = git_dir / "refs"
    if refs.is_dir():
        candidates.extend(refs.rglob("*.lock"))
    now = time.time()
    for path in candidates:
        if not path.is_file():
            continue
        try:
            age = now - path.stat().st_mtime
        except OSError:
            continue
        if age < max_age_s:
            continue
        try:
            path.unlink()
            removed.append(str(path.relative_to(git_dir)))
        except OSError:
            continue
    return removed


def _git(root: Path, *args: str, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    global _git_lock_depth, _git_lock_fh
    with _git_thread_lock:
        if _git_lock_depth == 0:
            GIT_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
            _git_lock_fh = open(GIT_LOCK_PATH, "a", encoding="utf-8")
            fcntl.flock(_git_lock_fh.fileno(), fcntl.LOCK_EX)
        _git_lock_depth += 1
        try:
            try:
                return subprocess.run(
                    ["git", "-C", str(root), *args],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired:
                clear_stale_git_locks(root, max_age_s=0)
                return subprocess.CompletedProcess(
                    args=["git", "-C", str(root), *args],
                    returncode=124,
                    stdout="",
                    stderr=f"git timed out after {timeout}s",
                )
        finally:
            _git_lock_depth -= 1
            if _git_lock_depth == 0 and _git_lock_fh is not None:
                fcntl.flock(_git_lock_fh.fileno(), fcntl.LOCK_UN)
                _git_lock_fh.close()
                _git_lock_fh = None


def _safe_read(path: Path, limit: int = 6000) -> str:
    if not path.is_file():
        return ""
    if SECRET_NAME.search(path.name):
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    if SECRET_NAME.search(text[:400]):
        return ""
    return text[:limit]


def git_status(root: Path | None = None) -> dict:
    root = root or codebase_root()
    exists = root.is_dir()
    is_git = exists and (root / ".git").exists()
    out = {
        "path": str(root),
        "exists": exists,
        "is_git": is_git,
        "configured": bool(settings.codebase_path),
        "pull_enabled": bool(settings.codebase_pull),
        "branch": "",
        "commit_sha": "",
        "commit_at": "",
        "commit_message": "",
        "ahead": 0,
        "behind": 0,
        "dirty": False,
        "error": "" if exists else f"Folder not found: {root}",
    }
    if not is_git:
        return out
    try:
        branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        sha = _git(root, "rev-parse", "HEAD").stdout.strip()
        subject = _git(root, "log", "-1", "--format=%s").stdout.strip()
        when = _git(root, "log", "-1", "--format=%ci").stdout.strip()
        porcelain = _git(root, "status", "--porcelain").stdout.strip()
        counts = _git(root, "rev-list", "--left-right", "--count", f"HEAD...origin/{branch}")
        ahead = behind = 0
        if counts.returncode == 0:
            parts = counts.stdout.strip().split()
            if len(parts) == 2:
                ahead, behind = int(parts[0]), int(parts[1])
        out.update(
            {
                "branch": branch,
                "commit_sha": sha[:12],
                "commit_at": when,
                "commit_message": subject[:240],
                "ahead": ahead,
                "behind": behind,
                "dirty": bool(porcelain),
            }
        )
    except Exception as exc:
        out["error"] = str(exc)
    return out


def _git_text(proc: subprocess.CompletedProcess[str]) -> str:
    return ((proc.stderr or "") + "\n" + (proc.stdout or "")).strip()


def remote_blocked(raw: str) -> bool:
    return bool(REMOTE_BLOCKED.search(raw or ""))


def explain_remote_error(raw: str) -> str:
    text = (raw or "").strip()
    if re.search(r"whitelist your IP", text, re.I):
        return (
            "Bitbucket blocked this IP — an admin has to whitelist it (or join VPN). "
            "Until then this app lists branches already on your Mac and indexes those. It cannot see new remotes."
        )
    if remote_blocked(text):
        return (
            "Cannot reach origin from this machine. Showing local branches only. "
            "Connect VPN or fix git access, then fetch again."
        )
    return text[:800]


def pull_current_branch(root: Path) -> dict:
    if not settings.codebase_pull:
        return {"ok": True, "pulled": False, "error": "CODEBASE_PULL is false; indexing local files only."}
    clear_stale_git_locks(root)
    stashed = stash_local_changes(root, "pull")
    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if not branch or branch == "HEAD":
        return _with_stash_note({"ok": True, "pulled": False, "error": "Detached HEAD; indexed the checkout without pull."}, stashed)
    fetch = _git(root, "fetch", "origin", branch, timeout=120)
    if fetch.returncode != 0:
        fetch = _git(root, "fetch", "origin", timeout=120)
    if fetch.returncode != 0:
        raw = _git_text(fetch) or "git fetch failed"
        return _with_stash_note(
            {"ok": True, "pulled": False, "error": explain_remote_error(raw), "remote_blocked": remote_blocked(raw)},
            stashed,
        )
    remote_ref = f"origin/{branch}"
    has_remote = _git(root, "show-ref", "--verify", "--quiet", f"refs/remotes/{remote_ref}")
    if has_remote.returncode == 0:
        pull = _git(root, "merge", "--ff-only", remote_ref, timeout=180)
    else:
        pull = _git(root, "pull", "--ff-only", "origin", branch, timeout=180)
    if pull.returncode != 0:
        raw = _git_text(pull) or "git pull --ff-only failed"
        if remote_blocked(raw):
            return _with_stash_note(
                {"ok": True, "pulled": False, "error": explain_remote_error(raw), "remote_blocked": True},
                stashed,
            )
        return _with_stash_note({"ok": False, "pulled": False, "error": raw[:800]}, stashed)
    log_text = (pull.stdout or "").strip()
    already = bool(re.search(r"already up.to.date", log_text, re.I)) or not log_text
    return _with_stash_note(
        {
            "ok": True,
            "pulled": True,
            "already_up_to_date": already,
            "error": "",
            "log": log_text[:400],
        },
        stashed,
    )


def _worktree_dirty(root: Path) -> bool:
    return bool(_git(root, "status", "--porcelain").stdout.strip())


def stash_local_changes(root: Path, reason: str = "index") -> dict:
    if not _worktree_dirty(root):
        return {"stashed": False, "message": ""}
    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() or "HEAD"
    stamp = now_local().strftime("%Y-%m-%d %H:%M")
    label = f"pm-platform: auto-stash before {reason} ({branch} {stamp})"
    proc = _git(root, "stash", "push", "--include-untracked", "-m", label, timeout=120)
    text = _git_text(proc)
    if re.search(r"No local changes to save", text, re.I):
        return {"stashed": False, "message": ""}
    if proc.returncode != 0:
        raise RuntimeError((text or "git stash failed").strip()[:800])
    leftover = _git(root, "status", "--porcelain").stdout.strip()
    if leftover:
        raise RuntimeError(
            "Could not stash all local changes before switching. "
            f"Still dirty: {leftover.splitlines()[0][:200]}"
        )
    return {
        "stashed": True,
        "branch": branch,
        "message": f"Stashed local changes from {branch}. Restore later with git stash pop in go_services.",
    }


def persist_stash(db: Session, stashed: dict | None, note: str = "") -> None:
    text = (note or (stashed or {}).get("message") or "").strip()
    if not text and not (stashed or {}).get("stashed"):
        return
    if not (stashed or {}).get("stashed") and "stashed" not in text.lower():
        return
    db.add(
        GitStash(
            branch=(stashed or {}).get("branch") or "",
            label=text[:512],
            message=text,
            created_at=now_local().replace(tzinfo=None),
        )
    )
    db.commit()


def open_stashes(db: Session) -> list[GitStash]:
    return db.query(GitStash).filter(GitStash.restored_at.is_(None)).order_by(GitStash.id.desc()).all()


def _with_stash_note(result: dict, stashed: dict | None) -> dict:
    note = (stashed or {}).get("message") or ""
    if note:
        result["stashed"] = True
        result["stashed_note"] = note
    return result


def split_pull_error(raw: str) -> tuple[str, str]:
    text = (raw or "").strip()
    match = re.search(
        r"(Stashed local changes from [^.]+)\.\s*(Restore later with git stash pop in go_services\.?)?",
        text,
        re.I,
    )
    if not match:
        return text, ""
    note = match.group(0).strip()
    rest = (text[: match.start()] + text[match.end() :]).strip()
    return rest, note


def recent_commits(root: Path, limit: int = 40) -> list[dict]:
    log = _git(root, "log", f"-{limit}", "--format=%h|%ad|%s", "--date=short")
    rows = []
    for line in log.stdout.splitlines():
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        rows.append({"sha": parts[0], "date": parts[1], "message": parts[2][:200]})
    return rows


def _tree(path: Path, depth: int = 2) -> str:
    lines: list[str] = []

    def walk(current: Path, prefix: str, remaining: int) -> None:
        if remaining < 0 or len(lines) > 40:
            return
        try:
            children = sorted([p for p in current.iterdir() if p.name not in SKIP_DIRS and not p.name.startswith(".")], key=lambda p: (not p.is_dir(), p.name.lower()))
        except OSError:
            return
        for child in children[:24]:
            lines.append(f"{prefix}{child.name}{'/' if child.is_dir() else ''}")
            if child.is_dir() and remaining > 0:
                walk(child, prefix + "  ", remaining - 1)

    walk(path, "", depth)
    return "\n".join(lines[:40])


def _doc_files(service: Path) -> list[Path]:
    found: list[Path] = []
    for name in ("README.md", "README", "readme.md"):
        candidate = service / name
        if candidate.is_file():
            found.append(candidate)
    docs = service / "docs"
    if docs.is_dir():
        ranked = []
        for path in docs.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".md", ".txt"}:
                continue
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            score = 0
            lower = path.name.lower()
            if any(hint in lower for hint in DOC_HINTS):
                score -= 10
            score += len(path.parts)
            ranked.append((score, path))
        ranked.sort(key=lambda item: item[0])
        found.extend(path for _, path in ranked[:8])
    return found[:10]


def _heuristic_summary(name: str, readme: str, tree: str) -> str:
    first = ""
    for line in (readme or "").splitlines():
        text = line.strip().lstrip("#").strip()
        if len(text) > 24:
            first = text[:280]
            break
    if first:
        return first
    if tree:
        return f"{name} service in go_services. Layout: " + ", ".join(tree.splitlines()[:8])
    return f"{name} package in go_services."


def scan_modules(root: Path) -> list[dict]:
    modules = []
    root_readme = _safe_read(root / "README.md", 4000)
    modules.append(
        {
            "name": "go_services",
            "kind": "monorepo",
            "summary": _heuristic_summary("go_services", root_readme, ""),
            "docs_excerpt": root_readme[:2500],
            "tree": _tree(root, 1),
            "doc_paths": ["README.md"],
            "capabilities": ["Shared Go/Python services for Sense / Activate / Post Call / Voicebot."],
        }
    )
    try:
        children = sorted([p for p in root.iterdir() if p.is_dir()], key=lambda p: p.name.lower())
    except OSError:
        return modules
    for folder in children:
        if folder.name.startswith(".") or folder.name in SKIP_DIRS or folder.name in SKIP_TOP:
            continue
        docs = _doc_files(folder)
        excerpts = []
        paths = []
        for doc in docs:
            rel = str(doc.relative_to(root))
            paths.append(rel)
            body = _safe_read(doc, 3500)
            if body:
                excerpts.append(f"## {rel}\n{body}")
        tree = _tree(folder, 2)
        blob = "\n\n".join(excerpts)[:8000]
        modules.append(
            {
                "name": folder.name,
                "kind": "service",
                "summary": _heuristic_summary(folder.name, blob, tree),
                "docs_excerpt": blob[:4000],
                "tree": tree,
                "doc_paths": paths,
                "capabilities": [],
            }
        )
    return modules


def _llm_summarize(modules: list[dict]) -> tuple[list[dict], bool]:
    llm = LLMClient()
    if not llm.configured:
        return modules, False
    payload = {
        "modules": [
            {
                "name": item["name"],
                "tree": item.get("tree") or "",
                "docs": (item.get("docs_excerpt") or "")[:700],
                "tree": (item.get("tree") or "")[:500],
            }
            for item in modules
        ]
    }
    try:
        generated = llm.complete_json(payload, system_prompt=SUMMARIZE_PROMPT, max_chars=28000, surface="codebase")
    except Exception:
        return modules, False
    by_name = {}
    for row in generated.get("modules") or []:
        if isinstance(row, dict) and row.get("name"):
            by_name[str(row["name"]).strip().lower()] = row
    for item in modules:
        row = by_name.get(item["name"].lower())
        if not row:
            continue
        if row.get("summary"):
            item["summary"] = str(row["summary"])[:600]
        caps = row.get("capabilities") or []
        if isinstance(caps, list):
            item["capabilities"] = [str(cap)[:160] for cap in caps[:6]]
    return modules, True


def write_product_map(snapshot: CodebaseSnapshot, modules: list[CodebaseModule]) -> Path:
    MAP_DIR.mkdir(parents=True, exist_ok=True)
    path = MAP_DIR / "PRODUCT_MAP.md"
    lines = [
        f"# Product map · go_services",
        "",
        f"- Path: `{snapshot.path}`",
        f"- Branch: `{snapshot.branch}`",
        f"- Commit: `{snapshot.commit_sha}` {snapshot.commit_message}",
        f"- Indexed: {format_ist(snapshot.created_at) if snapshot.created_at else ''}",
        f"- Modules: {snapshot.module_count}",
        "",
        "## What this branch ships",
        "",
        snapshot.live_summary or "Not summarized yet.",
        "",
        "## Recent commits",
        "",
    ]
    for commit in (snapshot.recent_commits or [])[:25]:
        lines.append(f"- {commit.get('date')} `{commit.get('sha')}` {commit.get('message')}")
    lines += ["", "## Services", ""]
    for module in modules:
        lines.append(f"### {module.name}")
        if module.summary:
            lines.append(module.summary)
        for cap in module.capabilities or []:
            lines.append(f"- {cap}")
        if module.doc_paths:
            lines.append("Docs: " + ", ".join(module.doc_paths[:8]))
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def latest_snapshot(db: Session) -> CodebaseSnapshot | None:
    return db.query(CodebaseSnapshot).order_by(CodebaseSnapshot.id.desc()).first()


def snapshot_out(db: Session, snapshot: CodebaseSnapshot | None = None) -> dict:
    live = git_status()
    snapshot = snapshot or latest_snapshot(db)
    modules = []
    if snapshot:
        modules = [
            {
                "name": row.name,
                "kind": row.kind,
                "summary": row.summary,
                "capabilities": row.capabilities or [],
                "doc_paths": row.doc_paths or [],
            }
            for row in db.query(CodebaseModule).filter(CodebaseModule.snapshot_id == snapshot.id).order_by(CodebaseModule.name.asc()).all()
        ]
    pull_error, stashed_note = split_pull_error(snapshot.pull_error if snapshot else "")
    stash_rows = open_stashes(db)
    if stash_rows and not stashed_note:
        stashed_note = stash_rows[0].message or stash_rows[0].label
    behind_main = 0
    try:
        root = codebase_root()
        base = detect_base_branch(root)
        if snapshot and snapshot.commit_sha and base:
            counts = _git(root, "rev-list", "--count", f"{snapshot.commit_sha}..{base}")
            if counts.returncode == 0:
                behind_main = int((counts.stdout or "0").strip() or 0)
    except Exception:
        behind_main = int(live.get("behind") or 0)
    return {
        **live,
        "indexed": bool(snapshot),
        "indexed_at": snapshot.created_at.isoformat() if snapshot and snapshot.created_at else None,
        "indexed_at_label": format_ist(snapshot.created_at) if snapshot and snapshot.created_at else "",
        "indexed_branch": snapshot.branch if snapshot else "",
        "indexed_sha": snapshot.commit_sha if snapshot else "",
        "indexed_message": snapshot.commit_message if snapshot else "",
        "module_count": snapshot.module_count if snapshot else 0,
        "pulled": snapshot.pulled if snapshot else False,
        "pull_error": pull_error,
        "stashed_note": stashed_note,
        "stashed": bool(stashed_note),
        "llm_used": snapshot.llm_used if snapshot else False,
        "recent_commits": (snapshot.recent_commits or [])[:15] if snapshot else [],
        "live_base": getattr(snapshot, "live_base", "") if snapshot else "",
        "live_summary": getattr(snapshot, "live_summary", "") if snapshot else "",
        "live_commits": (getattr(snapshot, "live_commits", None) or [])[:25] if snapshot else [],
        "live_files": (getattr(snapshot, "live_files", None) or [])[:40] if snapshot else [],
        "in_sync": bool(snapshot and snapshot.branch and snapshot.branch == (live.get("branch") or "")),
        "behind_main": behind_main,
        "index_age_days": (
            max(0, (now_local().replace(tzinfo=None) - snapshot.created_at).days)
            if snapshot and snapshot.created_at
            else None
        ),
        "stashes": [
            {
                "id": row.id,
                "branch": row.branch,
                "message": row.message or row.label,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in stash_rows[:5]
        ],
        "modules": modules,
        "map_path": str(MAP_DIR / "PRODUCT_MAP.md"),
        "now_label": format_ist(now_local()),
        "data_branch": load_profile().get("data_branch") or "",
    }


def update_index(db: Session, pull: bool = True, branch: str | None = None) -> dict:
    root = codebase_root()
    if not root.is_dir():
        raise FileNotFoundError(f"CODEBASE_PATH does not exist: {root}")
    pull_result = {"ok": True, "pulled": False, "error": ""}
    if branch:
        pull_result = checkout_named_branch(root, branch)
        pull = False
    if pull:
        try:
            pull_result = pull_current_branch(root)
        except Exception as exc:
            pull_result = {"ok": False, "pulled": False, "error": str(exc)}
    status = git_status(root)
    modules = scan_modules(root)
    modules, llm_used = _llm_summarize(modules)
    commits = recent_commits(root) if status.get("is_git") else []
    live = describe_live_changes(root, status.get("branch") or "", status.get("commit_sha") or "")
    pull_error, stashed_note = split_pull_error(pull_result.get("error") or "")
    stashed_note = (pull_result.get("stashed_note") or stashed_note or "").strip()
    persist_stash(db, pull_result, stashed_note)
    snapshot = CodebaseSnapshot(
        path=str(root),
        branch=status.get("branch") or "",
        commit_sha=status.get("commit_sha") or "",
        commit_at=status.get("commit_at") or "",
        commit_message=status.get("commit_message") or "",
        ahead=status.get("ahead") or 0,
        behind=status.get("behind") or 0,
        module_count=len(modules),
        pulled=bool(pull_result.get("pulled")),
        pull_error=" ".join(part for part in (stashed_note, pull_error or status.get("error") or "") if part).strip(),
        llm_used=llm_used or bool(live.get("llm_used")),
        recent_commits=commits,
        live_base=live.get("base") or "",
        live_summary=live.get("summary") or "",
        live_commits=live.get("commits") or [],
        live_files=live.get("files") or [],
        created_at=now_local().replace(tzinfo=None),
    )
    db.add(snapshot)
    db.flush()
    rows = []
    for item in modules:
        row = CodebaseModule(
            snapshot_id=snapshot.id,
            name=item["name"],
            kind=item.get("kind") or "service",
            summary=item.get("summary") or "",
            docs_excerpt=item.get("docs_excerpt") or "",
            tree=item.get("tree") or "",
            doc_paths=item.get("doc_paths") or [],
            capabilities=item.get("capabilities") or [],
        )
        db.add(row)
        rows.append(row)
    db.commit()
    db.refresh(snapshot)
    write_product_map(snapshot, rows)
    out = snapshot_out(db, snapshot)
    if stashed_note:
        out["stashed_note"] = stashed_note
        out["stashed"] = True
    alerts = []
    if status.get("dirty"):
        alerts.append("go_services is dirty after indexing.")
    wanted = (branch or status.get("branch") or "").strip()
    if wanted and (status.get("branch") or "") != wanted:
        alerts.append(f"Clone is on {status.get('branch') or 'unknown'} after indexing {wanted}.")
    base = detect_base_branch(root)
    short_base = (base or "").replace("origin/", "")
    if short_base and (status.get("branch") or "") == short_base and status.get("dirty"):
        alerts.append(f"Clone is on {short_base} but not clean.")
    if alerts:
        out["clone_alert"] = " ".join(alerts)
    out["pulled"] = bool(pull_result.get("pulled"))
    out["already_up_to_date"] = bool(pull_result.get("already_up_to_date"))
    out["remote_blocked"] = bool(pull_result.get("remote_blocked"))
    if pull_result.get("ok") is False and pull_error:
        out["ok"] = False
        out["error"] = pull_error
    return out


def retrieve_modules(db: Session, query: str, service: str = "", limit: int = 8) -> list[CodebaseModule]:
    snapshot = latest_snapshot(db)
    if not snapshot:
        return []
    rows = db.query(CodebaseModule).filter(CodebaseModule.snapshot_id == snapshot.id).all()
    tokens = [token.lower() for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", query or "") if token.lower() not in {"the", "and", "for", "with"}]
    wanted = (service or "").strip().lower()

    def score(row: CodebaseModule) -> int:
        blob = " ".join(
            [
                row.name,
                row.summary or "",
                " ".join(row.capabilities or []),
                " ".join(row.doc_paths or []),
                (row.docs_excerpt or "")[:1200],
            ]
        ).lower()
        total = 0
        if wanted and row.name.lower() == wanted:
            total += 50
        for token in tokens:
            if token == row.name.lower():
                total += 4
            elif token in row.name.lower():
                total += 2
            elif token in blob:
                total += 1
        return total

    ranked = sorted(rows, key=score, reverse=True)
    if wanted:
        exact = [row for row in ranked if row.name.lower() == wanted]
        related = [row for row in ranked if row.name.lower() != wanted and score(row) > 0]
        return (exact + related)[:limit]
    scored = [row for row in ranked if score(row) > 0]
    return scored[:limit] or ranked[:limit]


def grep_codebase(query: str, limit: int = 18) -> list[dict]:
    root = codebase_root()
    if not root.is_dir():
        return []
    tokens = [token for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{3,}", query or "") if token.lower() not in {"this", "that", "with", "from", "have"}]
    if not tokens:
        return []
    pattern = "|".join(re.escape(token) for token in tokens[:6])
    globs = [
        "--glob", "!**/.git/**",
        "--glob", "!**/node_modules/**",
        "--glob", "!**/vendor/**",
        "--glob", "!**/*.min.js",
        "--glob", "!**/*.lock",
        "--glob", "!**/*.{png,jpg,jpeg,gif,webp,mp4,pdf,xlsx,csv,bin,exe}",
    ]
    try:
        proc = subprocess.run(
            ["rg", "-i", "-n", "--max-count", "2", "-S", pattern, str(root), *globs],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    hits = []
    for line in proc.stdout.splitlines():
        if len(hits) >= limit:
            break
        if SECRET_NAME.search(line):
            continue
        parts = line.split(":", 3)
        if len(parts) < 3:
            continue
        file_path, lineno, text = parts[0], parts[1], parts[-1]
        try:
            rel = str(Path(file_path).relative_to(root))
        except ValueError:
            rel = file_path
        hits.append({"path": rel, "line": lineno, "text": text.strip()[:240]})
    return hits


QUERY_DIR = MAP_DIR / "query"
SKIP_QUERY_PATH = re.compile(r"(^|/)(vendor|node_modules|hack|\.git)(/|$)", re.I)


def _query_key(branch: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", (branch or "").strip()).strip("-") or "branch"


def resolve_branch_ref(root: Path, name: str) -> tuple[str, str, str]:
    wanted = _canonical_branch(name)[0] or (name or "").strip()
    if not wanted:
        raise RuntimeError("Pick a branch to ask.")
    for candidate in (wanted, f"origin/{wanted}", f"refs/heads/{wanted}", f"refs/remotes/origin/{wanted}"):
        probe = _git(root, "rev-parse", "--verify", candidate)
        if probe.returncode != 0:
            continue
        sha = (probe.stdout or "").strip()
        short = _git(root, "rev-parse", "--short", sha).stdout.strip() or sha[:12]
        return wanted, candidate, short
    raise RuntimeError(f"{wanted} is not in this clone. Fetch it first, then prepare a local query index.")


def git_show_ref(root: Path, ref: str, path: str, limit: int = 2500) -> str:
    if not path or SECRET_NAME.search(path):
        return ""
    proc = _git(root, "show", f"{ref}:{path}", timeout=15)
    if proc.returncode != 0:
        return ""
    text = proc.stdout or ""
    if SECRET_NAME.search(text[:400]):
        return ""
    return text[:limit]


def grep_on_ref(root: Path, ref: str, query: str, limit: int = 18) -> list[dict]:
    tokens = [token for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{3,}", query or "") if token.lower() not in {"this", "that", "with", "from", "have"}]
    if not tokens:
        return []
    pattern = "|".join(re.escape(token) for token in tokens[:6])
    try:
        proc = _git(root, "grep", "-i", "-n", "-I", "-E", "--max-count", "2", "-e", pattern, ref, timeout=25)
    except subprocess.TimeoutExpired:
        return []
    hits = []
    for line in proc.stdout.splitlines():
        if len(hits) >= limit:
            break
        raw = line[len(ref) + 1 :] if line.startswith(f"{ref}:") else line
        parts = raw.split(":", 2)
        if len(parts) < 3:
            continue
        path, lineno, text = parts[0], parts[1], parts[2]
        if SKIP_QUERY_PATH.search(path) or SECRET_NAME.search(path):
            continue
        hits.append({"path": path, "line": lineno, "text": text.strip()[:240]})
    return hits


def query_index_path(branch: str) -> Path:
    return QUERY_DIR / f"{_query_key(branch)}.json"


def query_index_out(payload: dict | None, *, branch: str = "") -> dict:
    data = payload or {}
    return {
        "ready": bool(data.get("sha") and data.get("modules") is not None),
        "branch": data.get("branch") or branch,
        "ref": data.get("ref") or "",
        "sha": data.get("sha") or "",
        "module_count": len(data.get("modules") or []),
        "message": data.get("message") or "",
        "error": "",
        "local": True,
    }


def load_query_index(branch: str) -> dict | None:
    path = query_index_path(branch)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def get_query_index(branch: str) -> dict:
    name = (_canonical_branch(branch)[0] or (branch or "").strip())
    if not name:
        return query_index_out(None)
    cached = load_query_index(name)
    out = query_index_out(cached, branch=name)
    try:
        root = codebase_root()
        if not root.is_dir():
            return out
        _, _, sha = resolve_branch_ref(root, name)
        if cached and cached.get("sha") == sha:
            out["ready"] = True
            out["sha"] = sha
        else:
            out["ready"] = False
            if cached:
                out["stale"] = True
    except RuntimeError as exc:
        out["error"] = str(exc)
        out["ready"] = False
    return out


def build_query_index(branch: str) -> dict:
    root = codebase_root()
    if not root.is_dir():
        raise FileNotFoundError(f"CODEBASE_PATH does not exist: {root}")
    name, ref, sha = resolve_branch_ref(root, branch)
    cached = load_query_index(name)
    if cached and cached.get("sha") == sha:
        return query_index_out(cached, branch=name)
    subject = _git(root, "log", "-1", "--format=%s", ref).stdout.strip()[:240]
    folders = _git(root, "ls-tree", "-d", "--name-only", ref).stdout.splitlines()
    modules = [
        {
            "name": "go_services",
            "kind": "monorepo",
            "summary": _heuristic_summary("go_services", git_show_ref(root, ref, "README.md", 2000), ""),
            "docs_excerpt": git_show_ref(root, ref, "README.md", 2500),
            "tree": "\n".join(folders[:40]),
            "doc_paths": ["README.md"] if git_show_ref(root, ref, "README.md", 40) else [],
            "capabilities": ["Local git query index — no checkout."],
        }
    ]
    for folder in folders:
        if not folder or folder.startswith(".") or folder in SKIP_DIRS or folder in SKIP_TOP:
            continue
        readme = ""
        doc_paths = []
        for candidate in (f"{folder}/README.md", f"{folder}/readme.md", f"{folder}/docs/README.md"):
            body = git_show_ref(root, ref, candidate, 2800)
            if body:
                readme = body
                doc_paths.append(candidate)
                break
        tree_proc = _git(root, "ls-tree", "--name-only", f"{ref}:{folder}")
        tree = "\n".join((tree_proc.stdout.splitlines() if tree_proc.returncode == 0 else [])[:40])
        modules.append(
            {
                "name": folder,
                "kind": "service",
                "summary": _heuristic_summary(folder, readme, tree),
                "docs_excerpt": readme[:4000],
                "tree": tree,
                "doc_paths": doc_paths,
                "capabilities": [],
            }
        )
    payload = {
        "branch": name,
        "ref": ref,
        "sha": sha,
        "message": subject,
        "modules": modules,
    }
    QUERY_DIR.mkdir(parents=True, exist_ok=True)
    query_index_path(name).write_text(json.dumps(payload), encoding="utf-8")
    return query_index_out(payload, branch=name)


def _modules_from_query(payload: dict, query: str, limit: int = 8) -> list[dict]:
    rows = payload.get("modules") or []
    tokens = [token.lower() for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", query or "") if token.lower() not in {"the", "and", "for", "with"}]

    def score(row: dict) -> int:
        blob = " ".join(
            [
                row.get("name") or "",
                row.get("summary") or "",
                " ".join(row.get("doc_paths") or []),
                (row.get("docs_excerpt") or "")[:1200],
                row.get("tree") or "",
            ]
        ).lower()
        total = 0
        for token in tokens:
            name = (row.get("name") or "").lower()
            if token == name:
                total += 4
            elif token in name:
                total += 2
            elif token in blob:
                total += 1
        return total

    ranked = sorted(rows, key=score, reverse=True)
    scored = [row for row in ranked if score(row) > 0]
    return (scored or ranked)[:limit]


ASK_PROMPT = with_preamble(
    """You are Arsalaan's PM answering a question about Convin's go_services codebase.
Use only the module excerpts and code hits from the named git branch.
Every factual claim in "answer" must trace to a citation in "citations".
If excerpts only partially answer the question, say what is missing before giving the partial answer.
Never name a file or function that does not appear in the payload.
If this local query index does not contain the answer, say so.

Return JSON:
{"answer": "plain language for a PM, 1-3 short paragraphs", "citations": [{"path": "file or module", "note": "why it matters"}], "not_enough_evidence": ""}
"""
)

LIVE_PROMPT = with_preamble(
    """You are Arsalaan's PM explaining what a git branch ships versus the live/default branch.
This text feeds release notes that get emailed. Write for an internal product audience.
Order by customer-visible impact, largest first. Name specific features/tables/screens only if paths or commit messages support them.
If the diff is only chores/config, say so in one sentence instead of padding.
Group by product change, not by commit hash. No file dumps.
Do not invent features that are not supported by the commit messages and file paths.

Return JSON:
{"summary": "3-8 sentence narrative of what went live / what this branch ships", "not_enough_evidence": ""}
"""
)


def detect_base_branch(root: Path) -> str:
    for candidate in ("origin/main", "origin/master", "origin/production", "main", "master"):
        probe = _git(root, "rev-parse", "--verify", candidate)
        if probe.returncode == 0:
            return candidate
    return ""


def _parse_git_dt(raw: str) -> datetime | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _ist_day(raw: str) -> str:
    dt = _parse_git_dt(raw)
    if dt is None:
        match = re.match(r"(\d{4}-\d{2}-\d{2})", raw or "")
        return match.group(1) if match else ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz())
    return dt.astimezone(tz()).strftime("%Y-%m-%d")


def _ist_stamp(raw: str) -> str:
    dt = _parse_git_dt(raw)
    if dt is None:
        return (raw or "")[:16].replace("T", " ")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz())
    return dt.astimezone(tz()).strftime("%Y-%m-%d %H:%M")


def _sort_key(raw: str) -> str:
    dt = _parse_git_dt(raw)
    if dt is None:
        return raw or ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz())
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def merge_dates_on_base(root: Path, base: str) -> dict[str, str]:
    if not base:
        return {}
    log = _git(root, "log", base, "--first-parent", "--merges", "--format=%cI\t%s", "-250", timeout=30)
    found: dict[str, str] = {}
    for line in log.stdout.splitlines():
        when, sep, subject = line.partition("\t")
        if not sep:
            continue
        match = re.search(r"Merged in ([^\s(]+)", subject)
        if not match:
            continue
        name = _canonical_branch(match.group(1))[0]
        if name and name not in found:
            found[name] = when.strip()
    return found


def _canonical_branch(ref: str) -> tuple[str, bool]:
    name = (ref or "").strip()
    if not name or name.endswith("/HEAD") or name == "HEAD":
        return "", False
    if name.startswith("origin/"):
        return name[7:], True
    return name, False


def list_recent_branches(fetch: bool = False, limit: int = 80) -> dict:
    root = codebase_root()
    status = git_status(root)
    out = {
        "ok": status.get("is_git"),
        "error": status.get("error") or "",
        "fetched": False,
        "remote_blocked": False,
        "current": status.get("branch") or "",
        "base": detect_base_branch(root) if status.get("is_git") else "",
        "branches": [],
    }
    if not status.get("is_git"):
        out["error"] = out["error"] or "Not a git clone."
        return out
    if fetch:
        proc = _git(root, "fetch", "origin", "--prune", timeout=120)
        if proc.returncode != 0:
            raw = _git_text(proc) or "git fetch failed"
            out["error"] = explain_remote_error(raw)
            out["remote_blocked"] = remote_blocked(raw)
        else:
            out["fetched"] = True
            out["error"] = ""
            out["remote_blocked"] = False
    listing = _git(
        root,
        "for-each-ref",
        "--sort=-committerdate",
        "--format=%(refname:short)\t%(objectname:short)\t%(committerdate:iso-strict)\t%(contents:subject)\t%(HEAD)",
        "refs/heads",
        "refs/remotes/origin",
        timeout=30,
    )
    if listing.returncode != 0:
        out["error"] = out["error"] or (listing.stderr or "Could not list branches.").strip()[:800]
        return out
    seen: dict[str, dict] = {}
    order: list[str] = []
    for line in listing.stdout.splitlines():
        parts = line.split("\t", 4)
        if len(parts) < 4:
            continue
        ref, sha, when, subject = parts[0], parts[1], parts[2], parts[3]
        head_mark = parts[4] if len(parts) > 4 else ""
        name, remote = _canonical_branch(ref)
        if not name or name in {"origin", "HEAD"}:
            continue
        if name == (out.get("base") or "").replace("origin/", ""):
            continue
        row = seen.get(name)
        if not row:
            row = {
                "name": name,
                "sha": sha[:12],
                "date": when,
                "tip_date": when,
                "message": (subject or "")[:180],
                "remote": remote,
                "current": head_mark.strip() == "*",
                "merged": False,
            }
            seen[name] = row
            order.append(name)
        else:
            if not remote:
                row["remote"] = False
            if head_mark.strip() == "*":
                row["current"] = True
            if not row.get("sha"):
                row["sha"] = sha[:12]
    merges = merge_dates_on_base(root, out["base"])
    rows = []
    for name in order:
        row = seen[name]
        merged_at = merges.get(name) or ""
        sort_raw = merged_at or row.get("tip_date") or row.get("date") or ""
        row["merged"] = bool(merged_at)
        row["date"] = _ist_stamp(sort_raw)
        row["day"] = _ist_day(sort_raw)
        row["sort_at"] = sort_raw
        rows.append(row)
    rows.sort(key=lambda item: _sort_key(item.get("sort_at") or ""), reverse=True)
    out["branches"] = rows[:limit]
    return out


def checkout_named_branch(root: Path, name: str) -> dict:
    wanted = _canonical_branch(name)[0] or (name or "").strip()
    if not wanted:
        raise RuntimeError("Pick a branch to index.")
    clear_stale_git_locks(root)
    status = git_status(root)
    current = status.get("branch") or ""
    stashed = stash_local_changes(root, f"switch to {wanted}") if status.get("dirty") else {"stashed": False, "message": ""}
    if current == wanted:
        if settings.codebase_pull:
            return _with_stash_note(pull_current_branch(root), stashed)
        return _with_stash_note({"ok": True, "pulled": False, "error": ""}, stashed)
    local = _git(root, "show-ref", "--verify", "--quiet", f"refs/heads/{wanted}")
    remote = _git(root, "show-ref", "--verify", "--quiet", f"refs/remotes/origin/{wanted}")
    if local.returncode != 0 and remote.returncode != 0:
        fetch = _git(root, "fetch", "origin", "--prune", timeout=120)
        if fetch.returncode != 0:
            raise RuntimeError(explain_remote_error(_git_text(fetch) or "git fetch failed"))
        local = _git(root, "show-ref", "--verify", "--quiet", f"refs/heads/{wanted}")
        remote = _git(root, "show-ref", "--verify", "--quiet", f"refs/remotes/origin/{wanted}")
    if local.returncode == 0:
        switched = _git(root, "switch", wanted, timeout=60)
        if switched.returncode != 0:
            switched = _git(root, "checkout", wanted, timeout=60)
    elif remote.returncode == 0:
        switched = _git(root, "switch", "-C", wanted, "--track", f"origin/{wanted}", timeout=60)
        if switched.returncode != 0:
            switched = _git(root, "checkout", "-B", wanted, f"origin/{wanted}", timeout=60)
    else:
        raise RuntimeError(f"Branch not found on this Mac: {wanted}. Fetch from origin after VPN / IP whitelist.")
    if switched.returncode != 0:
        raise RuntimeError((switched.stderr or switched.stdout or f"Could not switch to {wanted}").strip()[:800])
    if settings.codebase_pull:
        return _with_stash_note(pull_current_branch(root), stashed)
    return _with_stash_note({"ok": True, "pulled": False, "error": ""}, stashed)


def _live_range(root: Path, branch: str) -> tuple[str, str]:
    base = detect_base_branch(root)
    short_base = base.replace("origin/", "") if base else ""
    if not base:
        return "--since=14 days ago", "last 14 days"
    if branch and short_base and branch == short_base:
        return "--since=14 days ago", f"{short_base} · last 14 days"
    merge = _git(root, "merge-base", base, "HEAD")
    if merge.returncode != 0 or not merge.stdout.strip():
        return f"{base}..HEAD", f"vs {short_base or base}"
    return f"{merge.stdout.strip()}..HEAD", f"vs {short_base or base}"


def collect_live_changes(root: Path, branch: str = "") -> dict:
    spec, label = _live_range(root, branch)
    commits: list[dict] = []
    files: list[dict] = []
    if spec.startswith("--since"):
        log = _git(root, "log", spec, "--format=%h\t%ad\t%s", "--date=short", "-40")
        names = _git(root, "log", spec, "--name-status", "--pretty=format:", "-40")
    else:
        log = _git(root, "log", spec, "--format=%h\t%ad\t%s", "--date=short", "-40")
        names = _git(root, "diff", "--name-status", spec.replace("..", "...", 1))
    for line in log.stdout.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        commits.append({"sha": parts[0], "date": parts[1], "message": parts[2][:200]})
    for line in names.stdout.splitlines():
        text = line.strip()
        if not text:
            continue
        if "\t" in text:
            kind, path = text.split("\t", 1)
        else:
            parts = text.split(None, 1)
            if len(parts) != 2:
                continue
            kind, path = parts
        if SECRET_NAME.search(path):
            continue
        files.append({"change": kind[:8], "path": path[:220]})
        if len(files) >= 80:
            break
    unique_files = []
    seen = set()
    for row in files:
        if row["path"] in seen:
            continue
        seen.add(row["path"])
        unique_files.append(row)
    return {"base": label, "commits": commits, "files": unique_files[:40]}


def _heuristic_live_summary(branch: str, live: dict) -> str:
    commits = live.get("commits") or []
    files = live.get("files") or []
    services: list[str] = []
    for row in files:
        top = (row.get("path") or "").split("/", 1)[0]
        if top and top not in services and top not in SKIP_DIRS:
            services.append(top)
    lines = [
        f"{branch or 'This branch'} {live.get('base') or ''}".strip() + ".",
        f"{len(commits)} commit{'s' if len(commits) != 1 else ''} and {len(files)} file{'s' if len(files) != 1 else ''} in the window.",
    ]
    if services:
        lines.append("Touched: " + ", ".join(services[:12]) + ".")
    for commit in commits[:8]:
        lines.append(f"- {commit.get('message')}")
    if not commits:
        lines.append("No unique commits versus the live branch yet.")
    return "\n".join(lines)


def describe_live_changes(root: Path, branch: str, sha: str) -> dict:
    live = collect_live_changes(root, branch)
    summary = _heuristic_live_summary(branch, live)
    llm_used = False
    llm = LLMClient()
    if llm.configured and (live.get("commits") or live.get("files")):
        payload = {
            "branch": branch,
            "commit": sha,
            "compared_to": live.get("base"),
            "commits": live.get("commits")[:25],
            "files": live.get("files")[:40],
        }
        try:
            generated = llm.complete_json(payload, system_prompt=LIVE_PROMPT, max_chars=16000, surface="codebase_live")
            text = str(generated.get("summary") or "").strip()
            if text:
                summary = text[:4000]
                llm_used = True
        except Exception:
            llm_used = False
    return {**live, "summary": summary, "llm_used": llm_used}


def refresh_live_summary(db: Session) -> dict:
    snapshot = latest_snapshot(db)
    if not snapshot:
        raise RuntimeError("Index a branch in Codebase first.")
    root = codebase_root()
    live = describe_live_changes(root, snapshot.branch, snapshot.commit_sha)
    snapshot.live_base = live.get("base") or ""
    snapshot.live_summary = live.get("summary") or ""
    snapshot.live_commits = live.get("commits") or []
    snapshot.live_files = live.get("files") or []
    if live.get("llm_used"):
        snapshot.llm_used = True
    db.commit()
    db.refresh(snapshot)
    return snapshot_out(db, snapshot)


def _heuristic_ask(question: str, modules: list, hits: list, branch: str = "") -> tuple[str, list]:
    label = f"`{branch}`" if branch else "the indexed go_services map"
    lines = [f"From {label}, for: {question.strip() or 'this question'}"]
    citations = []
    for module in modules[:5]:
        lines.append(f"{module['name']}: {module.get('summary') or 'No summary yet.'}")
        citations.append({"path": module["name"], "note": "indexed module"})
    for hit in hits[:8]:
        lines.append(f"`{hit['path']}:{hit['line']}` {hit['text']}")
        citations.append({"path": f"{hit['path']}:{hit['line']}", "note": hit["text"][:120]})
    if len(lines) == 1:
        lines.append("Nothing in this branch’s local query index matched. Try another phrasing, or prepare the branch again.")
    return "\n".join(lines), citations[:12]


def ask_out(row: CodebaseAsk) -> dict:
    return {
        "id": row.id,
        "question": row.question,
        "answer": row.answer,
        "citations": row.citations or [],
        "snapshot_id": row.snapshot_id,
        "branch": row.branch,
        "commit_sha": row.commit_sha,
        "llm_used": row.llm_used,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def list_asks(db: Session, limit: int = 40) -> list[dict]:
    rows = db.query(CodebaseAsk).order_by(CodebaseAsk.id.desc()).limit(limit).all()
    return [ask_out(row) for row in rows]


def ask_codebase(db: Session, question: str, branch: str = "") -> dict:
    query = (question or "").strip()
    if not query:
        raise RuntimeError("Ask a question about the selected branch.")
    root = codebase_root()
    wanted = (_canonical_branch(branch)[0] or (branch or "").strip())
    snapshot = latest_snapshot(db)
    if not wanted:
        if not snapshot:
            raise RuntimeError("Select a branch on the left, then ask it.")
        wanted = snapshot.branch
    index = load_query_index(wanted)
    name, ref, sha = resolve_branch_ref(root, wanted)
    if not index or index.get("sha") != sha:
        build_query_index(name)
        index = load_query_index(name) or {}
    modules = _modules_from_query(index, query)
    module_payload = [
        {
            "name": row.get("name"),
            "summary": row.get("summary"),
            "capabilities": row.get("capabilities") or [],
            "doc_paths": row.get("doc_paths") or [],
            "docs_excerpt": (row.get("docs_excerpt") or "")[:1800],
        }
        for row in modules
    ]
    from app.services.source_index import search
    source = search(name, query)
    hits = source["hits"]
    sha = source["sha"]
    answer, citations = _heuristic_ask(query, module_payload, hits, name)
    llm_used = False
    llm = LLMClient()
    if llm.configured:
        payload = {
            "question": query,
            "branch": name,
            "sha": sha,
            "query_index": True,
            "modules": module_payload,
            "code_hits": hits,
        }
        try:
            generated = llm.complete_json(payload, system_prompt=ASK_PROMPT, max_chars=18000, surface="codebase_ask")
            text = str(generated.get("answer") or "").strip()
            if text:
                answer = text[:5000]
                llm_used = True
            raw_cites = generated.get("citations") or []
            if isinstance(raw_cites, list) and raw_cites:
                citations = [
                    {"path": str(item.get("path") or "")[:180], "note": str(item.get("note") or "")[:240]}
                    for item in raw_cites
                    if isinstance(item, dict)
                ][:12]
        except Exception:
            llm_used = False
    row = CodebaseAsk(
        question=query[:1000],
        answer=answer,
        citations=citations,
        snapshot_id=snapshot.id if snapshot and snapshot.branch == name else 0,
        branch=name,
        commit_sha=sha,
        llm_used=llm_used,
        created_at=now_local().replace(tzinfo=None),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return ask_out(row)

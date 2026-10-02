"""Repositories: a bare mirror per repo on the volume, one product worktree, and per-run worktrees.

Managed repositories never switch branches in somebody's working copy. The mirror holds every
remote branch under `refs/remotes/origin/*`; read-only work (logs, diffs, `git show`, the source
index) runs against those refs. The product worktree is a disposable checkout of the product
branch that module scans, grep and release screenshots read from disk. Anything else that
needs files for a different ref gets a temporary worktree that is removed afterwards.

`local` repositories point at an existing clone (laptop development) and keep the old flow.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import stat
import subprocess
import tempfile
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator
from urllib.parse import quote, urlparse

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Connection, Repository
from app.storage import workspace_path

log = logging.getLogger(__name__)

GIT_PROVIDERS = ("bitbucket", "github", "gitlab", "other")
MERGE_FORMATS = ("any", "bitbucket", "github", "gitlab")
TOKEN_USERNAMES = {"bitbucket": "x-token-auth", "github": "x-access-token", "gitlab": "oauth2", "other": "git"}
AUTH_FAILED = re.compile(
    r"authentication failed|invalid username or password|permission denied \(publickey\)|could not read username|"
    r"access denied|http basic: access denied|403|401",
    re.I,
)
REMOTE_BLOCKED = re.compile(r"whitelist your IP|ip address .* not allowed|not on the allowlist|ip allowlist", re.I)
UNREACHABLE = re.compile(r"could not resolve host|connection timed out|network is unreachable|connection refused|timed out", re.I)
NOT_FOUND = re.compile(r"repository not found|does not exist|not found", re.I)

# Merge-commit subjects that name the merged branch, per host.
MERGE_SUBJECTS = {
    "bitbucket": (re.compile(r"Merged in ([^\s(]+)"),),
    "github": (re.compile(r"Merge pull request #\d+ from (?:[^\s/]+)/(\S+)"), re.compile(r"Merge branch '([^']+)'")),
    "gitlab": (re.compile(r"Merge branch '([^']+)' into"), re.compile(r"Merge branch '([^']+)'")),
}

_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()
_EGRESS: dict[str, tuple[float, str]] = {}


# Paths


def repo_dir(repo: Repository) -> Path:
    return workspace_path("repos", str(repo.id))


def mirror_path(repo: Repository) -> Path:
    return repo_dir(repo) / "mirror.git"


def product_checkout_path(repo: Repository) -> Path | None:
    if repo.mode == "local":
        return Path(repo.local_path).expanduser() if repo.local_path else None
    return repo_dir(repo) / "worktrees" / "product"


def index_path(repo_id: int | None = None) -> Path:
    rid = repo_id or int(settings.repository_id or 0)
    if rid:
        return workspace_path("repos", str(rid), "source.sqlite3")
    return workspace_path("codebase", "source.sqlite3")


def lock_path(repo_id: int | None = None) -> Path:
    rid = repo_id or int(settings.repository_id or 0)
    if rid:
        return workspace_path("repos", str(rid), "git.lock")
    return workspace_path("git.lock")


def repo_lock(repo: Repository) -> threading.RLock:
    key = str(lock_path(repo.id))
    with _LOCKS_GUARD:
        if key not in _LOCKS:
            _LOCKS[key] = threading.RLock()
        return _LOCKS[key]


# Patterns


def release_regex(pattern: str | None = None) -> re.Pattern[str]:
    """`release/YYYY-MM-DD` → `^release/\\d{4}-\\d{2}-\\d{2}$`. `*` matches one path-safe segment."""
    raw = (pattern or settings.repo_release_pattern or "release/YYYY-MM-DD").strip() or "release/YYYY-MM-DD"
    body = re.escape(raw)
    for token, repl in (("YYYY", r"\d{4}"), ("MM", r"\d{2}"), ("DD", r"\d{2}"), (r"\*", r"[\w.-]+")):
        body = body.replace(token, repl)
    return re.compile(f"^{body}$")


def release_fragment(pattern: str | None = None) -> str:
    return release_regex(pattern).pattern[1:-1]


def merged_branch(subject: str, fmt: str | None = None) -> str:
    """The branch a merge commit brought in, read from its subject for the given host format."""
    text = subject or ""
    chosen = (fmt or settings.repo_merge_format or "any").strip().lower()
    groups = [MERGE_SUBJECTS[chosen]] if chosen in MERGE_SUBJECTS else list(MERGE_SUBJECTS.values())
    for patterns in groups:
        for pattern in patterns:
            match = pattern.search(text)
            if match:
                name = match.group(1).strip().strip("'\"")
                return name[7:] if name.startswith("origin/") else name
    return ""


def path_scopes() -> list[str]:
    raw = settings.repo_path_scopes
    items = raw if isinstance(raw, list) else str(raw or "").split(",")
    out = []
    for item in items:
        text = str(item or "").strip().strip("/")
        if text:
            out.append(text + "/")
    return out


def primary_scope() -> str:
    scopes = path_scopes()
    return scopes[0] if scopes else ""


def scope_root() -> str:
    """First path scope without the trailing slash, or "" for the whole repository."""
    return primary_scope().rstrip("/")


def default_base_ref() -> str:
    branch = (settings.repo_default_branch or "").strip()
    return f"origin/{branch}" if branch else ""


# Credentials


def _https_url(url: str) -> str:
    text = (url or "").strip()
    match = re.match(r"^(?:ssh://)?git@([^:/]+)[:/](.+)$", text)
    if match:
        return f"https://{match.group(1)}/{match.group(2)}"
    return text


def _ssh_url(url: str) -> str:
    text = (url or "").strip()
    if text.startswith(("http://", "https://")):
        parsed = urlparse(text)
        path = parsed.path.lstrip("/")
        return f"git@{parsed.hostname}:{path}"
    return text


def remote_for(repo: Repository, auth_type: str) -> str:
    if auth_type == "ssh_key":
        return _ssh_url(repo.remote_url)
    if auth_type == "token":
        return _https_url(repo.remote_url)
    return repo.remote_url


def display_url(url: str) -> str:
    parsed = urlparse(url or "")
    if parsed.scheme in {"http", "https"} and (parsed.username or parsed.password):
        host = parsed.hostname or ""
        return f"{parsed.scheme}://{host}{parsed.path}"
    return url or ""


def connection_for(db: Session, repo: Repository) -> Connection | None:
    if repo.connection_id:
        row = db.get(Connection, repo.connection_id)
        if row is not None:
            return row
    provider = repo.provider if repo.provider in {"bitbucket", "github", "gitlab"} else ""
    if not provider:
        return None
    return db.query(Connection).filter(Connection.provider == provider).order_by(Connection.id).first()


@contextmanager
def git_auth(db: Session | None, repo: Repository) -> Iterator[tuple[dict, str]]:
    """Environment and remote URL for git commands that talk to the remote. Key files are temporary."""
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "", "SSH_ASKPASS": ""}
    if repo.mode == "local" or db is None:
        yield env, repo.remote_url
        return
    from app.connections.store import connection_values

    row = connection_for(db, repo)
    values = connection_values(db, row) if row is not None else {}
    auth_type = str(values.get("auth_type") or ("ssh_key" if values.get("ssh_private_key") else "token" if values.get("access_token") else "none"))
    tmp = Path(tempfile.mkdtemp(prefix="git-auth-"))
    try:
        known_hosts = repo_dir(repo) / "known_hosts"
        known_hosts.parent.mkdir(parents=True, exist_ok=True)
        if auth_type == "ssh_key" and values.get("ssh_private_key"):
            key = tmp / "id"
            key.write_text(str(values["ssh_private_key"]).strip() + "\n", encoding="utf-8")
            key.chmod(stat.S_IRUSR | stat.S_IWUSR)
            env["GIT_SSH_COMMAND"] = (
                f"ssh -i {key} -o IdentitiesOnly=yes -o BatchMode=yes "
                f"-o StrictHostKeyChecking=accept-new -o UserKnownHostsFile={known_hosts}"
            )
            yield env, remote_for(repo, "ssh_key")
            return
        token = str(values.get("access_token") or "")
        if token:
            username = str(values.get("username") or "").strip() or TOKEN_USERNAMES.get(repo.provider, "git")
            askpass = tmp / "askpass.sh"
            askpass.write_text(
                '#!/bin/sh\ncase "$1" in\n  Username*) printf "%s" "$GIT_AUTH_USER" ;;\n  *) printf "%s" "$GIT_AUTH_TOKEN" ;;\nesac\n',
                encoding="utf-8",
            )
            askpass.chmod(stat.S_IRWXU)
            env.update({"GIT_ASKPASS": str(askpass), "GIT_AUTH_USER": username, "GIT_AUTH_TOKEN": token})
            url = remote_for(repo, "token")
            parsed = urlparse(url)
            if parsed.scheme in {"http", "https"} and not parsed.username:
                url = url.replace(f"{parsed.scheme}://", f"{parsed.scheme}://{quote(username, safe='')}@", 1)
            yield env, url
            return
        yield env, repo.remote_url
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# Git plumbing


def run_git(cwd: Path, *args: str, env: dict | None = None, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(["git", *args], 124, "", f"git timed out after {timeout}s")


def _text(proc: subprocess.CompletedProcess[str]) -> str:
    return ((proc.stderr or "") + "\n" + (proc.stdout or "")).strip()


def _scrub(text: str) -> str:
    return re.sub(r"(https?://)[^/@\s]+@", r"\1", text or "")


def classify_fetch_error(raw: str) -> str:
    text = raw or ""
    if REMOTE_BLOCKED.search(text):
        return "remote_blocked"
    if AUTH_FAILED.search(text):
        return "auth_failed"
    if UNREACHABLE.search(text):
        return "unreachable"
    if NOT_FOUND.search(text):
        return "not_found"
    return "error"


FETCH_MESSAGES = {
    "remote_blocked": "The git host refused this server's IP. Add the outgoing IP shown here to the repository allowlist.",
    "auth_failed": "The git host rejected the credentials. Check the connection's token or deploy key.",
    "unreachable": "Could not reach the git host from this server.",
    "not_found": "The repository was not found, or the credentials cannot see it.",
}


def explain_fetch_error(status: str, raw: str) -> str:
    base = FETCH_MESSAGES.get(status, "")
    detail = _scrub(raw).strip().splitlines()[-1:] if raw else []
    return (base + (" " if base and detail else "") + (detail[0][:300] if detail else "")).strip()


def ensure_mirror(db: Session | None, repo: Repository) -> Path:
    mirror = mirror_path(repo)
    if (mirror / "HEAD").is_file():
        return mirror
    mirror.parent.mkdir(parents=True, exist_ok=True)
    proc = run_git(mirror.parent, "init", "--bare", mirror.name)
    if proc.returncode != 0:
        raise RuntimeError(_text(proc)[:400] or "git init failed")
    run_git(mirror, "config", "gc.auto", "256")
    run_git(mirror, "remote", "add", "origin", display_url(repo.remote_url))
    run_git(mirror, "config", "remote.origin.fetch", "+refs/heads/*:refs/remotes/origin/*")
    return mirror


def _record_fetch(db: Session | None, repo: Repository, status: str, error: str) -> None:
    repo.last_fetch_at = datetime.utcnow()
    repo.last_fetch_status = status
    repo.last_fetch_error = error[:1200]
    repo.updated_at = datetime.utcnow()
    if db is not None:
        db.add(repo)
        db.commit()


def fetch(db: Session | None, repo: Repository, *, timeout: int = 600) -> dict:
    """`git remote update --prune` into the mirror, then refresh the product worktree."""
    if repo.mode == "local":
        return _fetch_local(db, repo, timeout=timeout)
    with repo_lock(repo):
        mirror = ensure_mirror(db, repo)
        with git_auth(db, repo) as (env, url):
            run_git(mirror, "remote", "set-url", "origin", url)
            try:
                proc = run_git(mirror, "remote", "update", "--prune", env=env, timeout=timeout)
            finally:
                run_git(mirror, "remote", "set-url", "origin", display_url(repo.remote_url))
        if proc.returncode != 0:
            raw = _text(proc)
            status = classify_fetch_error(raw)
            message = explain_fetch_error(status, raw)
            _record_fetch(db, repo, status, message)
            return {"ok": False, "status": status, "error": message, "remote_blocked": status == "remote_blocked"}
        default = detect_default_branch(repo)
        if default and not repo.default_branch:
            repo.default_branch = default
        _record_fetch(db, repo, "ok", "")
        checkout = sync_product_worktree(repo)
        return {"ok": True, "status": "ok", "error": "", "checkout": checkout}


def _fetch_local(db: Session | None, repo: Repository, *, timeout: int) -> dict:
    root = product_checkout_path(repo)
    if not root or not root.is_dir():
        message = f"Folder not found: {root}"
        _record_fetch(db, repo, "error", message)
        return {"ok": False, "status": "error", "error": message}
    with repo_lock(repo):
        proc = run_git(root, "fetch", "origin", "--prune", timeout=timeout)
    if proc.returncode != 0:
        raw = _text(proc)
        status = classify_fetch_error(raw)
        message = explain_fetch_error(status, raw)
        _record_fetch(db, repo, status, message)
        return {"ok": False, "status": status, "error": message, "remote_blocked": status == "remote_blocked"}
    _record_fetch(db, repo, "ok", "")
    return {"ok": True, "status": "ok", "error": ""}


def git_dir(repo: Repository) -> Path | None:
    """Where read-only git commands should run: the mirror, or the local clone."""
    if repo.mode == "local":
        return product_checkout_path(repo)
    mirror = mirror_path(repo)
    return mirror if (mirror / "HEAD").is_file() else None


def detect_default_branch(repo: Repository) -> str:
    cwd = git_dir(repo)
    if cwd is None:
        return ""
    if repo.default_branch:
        probe = run_git(cwd, "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{repo.default_branch}", timeout=10)
        if probe.returncode == 0:
            return repo.default_branch
    for candidate in ("main", "master", "production", "develop", "trunk"):
        probe = run_git(cwd, "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{candidate}", timeout=10)
        if probe.returncode == 0:
            return candidate
    return ""


def product_branch(repo: Repository) -> str:
    return (repo.product_branch or repo.default_branch or detect_default_branch(repo) or "main").strip()


def sync_product_worktree(repo: Repository, branch: str | None = None) -> dict:
    """Point the product worktree at origin/<branch>. Local edits are discarded: it is a cache."""
    if repo.mode == "local":
        return {"ok": True, "path": str(product_checkout_path(repo) or "")}
    wanted = (branch or product_branch(repo)).strip()
    mirror = mirror_path(repo)
    path = product_checkout_path(repo)
    assert path is not None
    with repo_lock(repo):
        if not (mirror / "HEAD").is_file():
            return {"ok": False, "path": str(path), "error": "Fetch the repository first."}
        ref = f"refs/remotes/origin/{wanted}"
        if run_git(mirror, "rev-parse", "--verify", "--quiet", ref, timeout=10).returncode != 0:
            return {"ok": False, "path": str(path), "error": f"Branch {wanted} is not on the remote."}
        run_git(mirror, "worktree", "prune")
        if not (path / ".git").exists():
            if path.exists():
                shutil.rmtree(path, ignore_errors=True)
            path.parent.mkdir(parents=True, exist_ok=True)
            proc = run_git(mirror, "worktree", "add", "--force", "-B", wanted, str(path), f"origin/{wanted}", timeout=600)
        else:
            proc = run_git(path, "checkout", "--force", "-B", wanted, f"origin/{wanted}", timeout=600)
            if proc.returncode == 0:
                run_git(path, "clean", "-fd", timeout=300)
        if proc.returncode != 0:
            return {"ok": False, "path": str(path), "error": _scrub(_text(proc))[:600]}
        run_git(path, "branch", f"--set-upstream-to=origin/{wanted}", wanted, timeout=10)
        sha = run_git(path, "rev-parse", "HEAD", timeout=10).stdout.strip()
    _invalidate_status(path)
    return {"ok": True, "path": str(path), "branch": wanted, "sha": sha[:12]}


def _invalidate_status(path: Path) -> None:
    try:
        from app.services.codebase import invalidate_git_status

        invalidate_git_status(path)
    except Exception:
        pass


@contextmanager
def temporary_worktree(repo: Repository, ref: str, *, share: tuple[str, ...] = ()) -> Iterator[Path]:
    """A throwaway checkout of `ref` for one run. `share` symlinks heavy folders (node_modules) from the product worktree."""
    if repo.mode == "local":
        root = product_checkout_path(repo)
        if root is None:
            raise RuntimeError("Repository has no local path.")
        tmp_root = Path(tempfile.mkdtemp(prefix="wt-"))
        path = tmp_root / "checkout"
        cwd = root
    else:
        cwd = mirror_path(repo)
        path = repo_dir(repo) / "worktrees" / f"run-{uuid.uuid4().hex[:10]}"
        tmp_root = None
    with repo_lock(repo):
        path.parent.mkdir(parents=True, exist_ok=True)
        proc = run_git(cwd, "worktree", "add", "--detach", "--force", str(path), ref, timeout=600)
    if proc.returncode != 0:
        if tmp_root:
            shutil.rmtree(tmp_root, ignore_errors=True)
        raise RuntimeError(_scrub(_text(proc))[:600] or f"Could not check out {ref}")
    product = product_checkout_path(repo)
    for rel in share:
        source = (product / rel) if product else None
        target = path / rel
        if source is not None and source.exists() and not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                target.symlink_to(source, target_is_directory=source.is_dir())
            except OSError:
                log.warning("could not share %s into worktree", rel)
    try:
        yield path
    finally:
        remove_worktree(cwd, path)
        if tmp_root:
            shutil.rmtree(tmp_root, ignore_errors=True)


def remove_worktree(cwd: Path, path: Path) -> None:
    proc = run_git(cwd, "worktree", "remove", "--force", str(path), timeout=120)
    if proc.returncode != 0 and path.exists():
        shutil.rmtree(path, ignore_errors=True)
    run_git(cwd, "worktree", "prune", timeout=60)


def prune_stale_worktrees(repo: Repository, max_age_s: int = 6 * 3600) -> int:
    """Remove run worktrees left behind by a crashed worker."""
    if repo.mode == "local":
        return 0
    base = repo_dir(repo) / "worktrees"
    if not base.is_dir():
        return 0
    removed = 0
    now = time.time()
    for child in base.iterdir():
        if not child.name.startswith("run-"):
            continue
        try:
            age = now - child.stat().st_mtime
        except OSError:
            continue
        if age >= max_age_s:
            remove_worktree(mirror_path(repo), child)
            removed += 1
    return removed


# Branch listing (reads the mirror, never checks out)


def merge_dates(repo: Repository, base: str, *, limit: int = 400) -> dict[str, str]:
    cwd = git_dir(repo)
    if cwd is None or not base:
        return {}
    proc = run_git(cwd, "log", base, "--first-parent", "--merges", "--format=%cI\t%s", f"-{limit}", timeout=30)
    found: dict[str, str] = {}
    for line in proc.stdout.splitlines():
        when, sep, subject = line.partition("\t")
        if not sep:
            continue
        name = merged_branch(subject, repo.merge_format)
        if name and name not in found:
            found[name] = when.strip()
    return found


def list_branches(repo: Repository, *, limit: int = 120) -> list[dict]:
    cwd = git_dir(repo)
    if cwd is None:
        return []
    proc = run_git(
        cwd,
        "for-each-ref",
        "--sort=-committerdate",
        "--format=%(refname:short)\t%(objectname:short)\t%(committerdate:iso-strict)\t%(contents:subject)",
        "refs/remotes/origin",
        timeout=30,
    )
    default = (repo.default_branch or "").strip()
    base = f"origin/{default}" if default else ""
    merges = merge_dates(repo, base)
    pattern = release_regex(repo.release_pattern)
    indexed = set(repo.indexed_branches or [])
    current_product = product_branch(repo)
    rows = []
    for line in proc.stdout.splitlines():
        parts = line.split("\t", 3)
        if len(parts) < 4:
            continue
        ref, sha, when, subject = parts
        name = ref[7:] if ref.startswith("origin/") else ref
        if not name or name in {"HEAD", "origin"} or name.endswith("/HEAD"):
            continue
        merged_at = merges.get(name) or ""
        rows.append(
            {
                "name": name,
                "sha": sha[:12],
                "committed_at": when,
                "message": (subject or "")[:180],
                "merged": bool(merged_at),
                "merged_at": merged_at,
                "is_default": name == default,
                "is_product": name == current_product,
                "is_release": bool(pattern.match(name)),
                "indexed": name in indexed,
            }
        )
        if len(rows) >= limit:
            break
    return rows


def refresh_branch_cache(db: Session, repo: Repository) -> list[dict]:
    rows = list_branches(repo)
    repo.branches_cache = rows
    repo.updated_at = datetime.utcnow()
    db.add(repo)
    db.commit()
    return rows


# Egress IP (to allowlist on the git host)


def egress_ip(force: bool = False) -> str:
    url = (settings.egress_ip_url or "").strip()
    if not url:
        return ""
    cached = _EGRESS.get(url)
    if cached and not force and time.time() - cached[0] < 3600:
        return cached[1]
    try:
        from app.clients.http import get

        response = get(url, timeout=6)
        ip = response.text.strip() if response.status_code == 200 else ""
    except Exception:
        ip = ""
    if ip and len(ip) <= 64:
        _EGRESS[url] = (time.time(), ip)
        return ip
    return cached[1] if cached else ""


# Rows


def primary(db: Session) -> Repository | None:
    return db.query(Repository).order_by(Repository.is_primary.desc(), Repository.id).first()


def current(db: Session) -> Repository | None:
    rid = int(settings.repository_id or 0)
    if rid:
        row = db.get(Repository, rid)
        if row is not None:
            return row
    return primary(db)


def repository_out(repo: Repository, *, branches: bool = False) -> dict:
    path = product_checkout_path(repo)
    out = {
        "id": repo.id,
        "name": repo.name,
        "provider": repo.provider,
        "remote_url": display_url(repo.remote_url),
        "connection_id": repo.connection_id,
        "mode": repo.mode,
        "local_path": repo.local_path or "",
        "default_branch": repo.default_branch or "",
        "product_branch": product_branch(repo) if (repo.product_branch or repo.default_branch) else "",
        "release_pattern": repo.release_pattern or "release/YYYY-MM-DD",
        "merge_format": repo.merge_format or "any",
        "path_scopes": list(repo.path_scopes or []),
        "ui_path": repo.ui_path or "",
        "is_primary": bool(repo.is_primary),
        "checkout_path": str(path) if path else "",
        "checkout_ready": bool(path and (path / ".git").exists()),
        "mirror_ready": repo.mode == "local" or (mirror_path(repo) / "HEAD").is_file(),
        "last_fetch_at": repo.last_fetch_at.isoformat() if repo.last_fetch_at else None,
        "last_fetch_status": repo.last_fetch_status or "never",
        "last_fetch_error": repo.last_fetch_error or "",
        "indexed_branches": list(repo.indexed_branches or []),
        "branch_count": len(repo.branches_cache or []),
        "created_at": repo.created_at.isoformat() if repo.created_at else None,
    }
    if branches:
        out["branches"] = list(repo.branches_cache or [])
    return out


def repository_values(repo: Repository) -> dict:
    """Settings the codebase and release services read inside the workspace."""
    values: dict = {
        "repository_id": repo.id,
        "repo_mode": repo.mode or "managed",
        "repo_default_branch": repo.default_branch or "",
        "repo_release_pattern": repo.release_pattern or "release/YYYY-MM-DD",
        "repo_merge_format": repo.merge_format or "any",
        "repo_path_scopes": ",".join(repo.path_scopes or []),
        "repo_ui_path": repo.ui_path or "",
    }
    path = product_checkout_path(repo)
    if path:
        values["codebase_path"] = str(path)
        if repo.ui_path:
            values["release_shots_ui_path"] = str(path / repo.ui_path)
    return values


def save_repository(db: Session, data: dict, repo: Repository | None = None) -> Repository:
    row = repo or Repository(name="", provider="bitbucket")
    for key in ("name", "provider", "remote_url", "mode", "local_path", "default_branch", "product_branch", "release_pattern", "merge_format", "ui_path"):
        if key in data and data[key] is not None:
            setattr(row, key, str(data[key]).strip())
    if "connection_id" in data:
        row.connection_id = int(data["connection_id"]) if data.get("connection_id") else None
    if "path_scopes" in data:
        raw = data.get("path_scopes")
        items = raw if isinstance(raw, list) else str(raw or "").split(",")
        row.path_scopes = [str(item).strip().strip("/") + "/" for item in items if str(item).strip().strip("/")]
    if row.provider not in GIT_PROVIDERS:
        row.provider = "other"
    if row.merge_format not in MERGE_FORMATS:
        row.merge_format = "any"
    if row.mode not in {"managed", "local"}:
        row.mode = "managed"
    if not row.name:
        row.name = _name_from_url(row.remote_url) or Path(row.local_path or "repo").name
    if row.mode == "managed" and not row.remote_url:
        raise ValueError("A remote URL is required.")
    if row.mode == "local" and not row.local_path:
        raise ValueError("A local path is required for a local repository.")
    if data.get("is_primary") or not db.query(Repository.id).filter(Repository.is_primary.is_(True)).first():
        for other in db.query(Repository).filter(Repository.is_primary.is_(True)).all():
            if other is not row:
                other.is_primary = False
        row.is_primary = True
    row.updated_at = datetime.utcnow()
    db.add(row)
    db.flush()
    from app.connections.store import audit, bump_version

    bump_version(db)
    audit(db, "repository.saved", row.name, {"fields": sorted(data)})
    db.commit()
    db.refresh(row)
    return row


def delete_repository(db: Session, repo: Repository) -> None:
    folder = repo_dir(repo) if repo.mode == "managed" else None
    name = repo.name
    db.delete(repo)
    from app.connections.store import audit, bump_version

    bump_version(db)
    audit(db, "repository.removed", name, {})
    db.commit()
    if folder and folder.is_dir():
        shutil.rmtree(folder, ignore_errors=True)


def _name_from_url(url: str) -> str:
    text = (url or "").rstrip("/")
    if not text:
        return ""
    tail = re.split(r"[/:]", text)[-1]
    return tail[:-4] if tail.endswith(".git") else tail


def mark_indexed(db: Session, repo: Repository, branch: str, keep: int | None = None) -> list[str]:
    """Record an indexed branch, newest first, keeping the last N. Returns the evicted names."""
    limit = max(1, int(keep or settings.source_index_keep or 3))
    names = [branch] + [name for name in (repo.indexed_branches or []) if name != branch]
    protected = {product_branch(repo)}
    kept: list[str] = []
    evicted: list[str] = []
    for name in names:
        if len(kept) < limit or name in protected:
            kept.append(name)
        else:
            evicted.append(name)
    repo.indexed_branches = kept
    db.add(repo)
    db.commit()
    return evicted

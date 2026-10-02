"""Repositories: mirrors, product branch, release pattern, scopes, branch list and fetch status."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import Principal, current_principal, require_admin
from app.config import settings
from app.database import get_db
from app.models import Connection, Repository
from app.services import repos
from app.services.jobs import active_run, enqueue, job_out

router = APIRouter()


class RepositoryBody(BaseModel):
    name: str | None = None
    provider: str | None = None
    remote_url: str | None = None
    connection_id: int | None = None
    mode: str | None = None
    local_path: str | None = None
    default_branch: str | None = None
    product_branch: str | None = None
    release_pattern: str | None = None
    merge_format: str | None = None
    path_scopes: list[str] | str | None = None
    ui_path: str | None = None
    is_primary: bool | None = None


def local_repos_allowed() -> bool:
    return not settings.is_production


def _repo(db: Session, repo_id: int) -> Repository:
    row = db.get(Repository, repo_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return row


def _sync_kind(repo_id: int) -> str:
    return f"repo-sync-{repo_id}"


def _out(db: Session, repo: Repository, *, branches: bool = False) -> dict:
    run = active_run(db, _sync_kind(repo.id))
    return {**repos.repository_out(repo, branches=branches), "sync_run": job_out(run)}


@router.get("/repositories")
def list_repositories(principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    rows = db.query(Repository).order_by(Repository.is_primary.desc(), Repository.id).all()
    credentials = [
        {"id": c.id, "provider": c.provider, "name": c.name, "status": c.status}
        for c in db.query(Connection).filter(Connection.provider.in_(("bitbucket", "github", "gitlab"))).order_by(Connection.id).all()
    ]
    return {
        "repositories": [_out(db, row) for row in rows],
        "credentials": credentials,
        "egress_ip": repos.egress_ip(),
        "providers": list(repos.GIT_PROVIDERS),
        "merge_formats": list(repos.MERGE_FORMATS),
        "local_allowed": local_repos_allowed(),
        "can_edit": principal.at_least("admin"),
    }


def _save(db: Session, body: RepositoryBody, repo: Repository | None, principal: Principal) -> Repository:
    data = body.model_dump(exclude_none=True)
    if data.get("mode") == "local" and not local_repos_allowed():
        raise HTTPException(status_code=400, detail="Local folders are only available on a self-hosted install. Connect a remote instead.")
    if data.get("connection_id"):
        conn = db.get(Connection, int(data["connection_id"]))
        if conn is None:
            raise HTTPException(status_code=422, detail="Unknown credential")
        data.setdefault("provider", conn.provider)
    try:
        return repos.save_repository(db, data, repo)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _start_sync(db: Session, repo: Repository, principal: Principal):
    return enqueue(db, _sync_kind(repo.id), task="repo-sync", params={"repository_id": repo.id}, pipeline_id="codebase", started_by=principal.email)


@router.post("/repositories")
def add_repository(body: RepositoryBody, principal: Principal = Depends(require_admin), db: Session = Depends(get_db)):
    repo = _save(db, body, None, principal)
    run = _start_sync(db, repo, principal)
    return JSONResponse(status_code=201, content={**_out(db, repo), "sync_run": job_out(run)})


@router.get("/repositories/{repo_id}")
def repository_detail(repo_id: int, _: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    return _out(db, _repo(db, repo_id), branches=True)


@router.patch("/repositories/{repo_id}")
def edit_repository(repo_id: int, body: RepositoryBody, principal: Principal = Depends(require_admin), db: Session = Depends(get_db)):
    repo = _repo(db, repo_id)
    before = (repo.remote_url, repo.product_branch, repo.connection_id)
    repo = _save(db, body, repo, principal)
    if (repo.remote_url, repo.product_branch, repo.connection_id) != before:
        _start_sync(db, repo, principal)
    return _out(db, repo, branches=True)


@router.delete("/repositories/{repo_id}")
def remove_repository(repo_id: int, _: Principal = Depends(require_admin), db: Session = Depends(get_db)):
    repos.delete_repository(db, _repo(db, repo_id))
    return {"ok": True}


@router.post("/repositories/{repo_id}/sync")
def sync_repository(repo_id: int, principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    run = _start_sync(db, _repo(db, repo_id), principal)
    return JSONResponse(status_code=202, content=job_out(run))


@router.get("/repositories/{repo_id}/branches")
def repository_branches(repo_id: int, refresh: bool = False, q: str = "", _: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    repo = _repo(db, repo_id)
    rows = repos.refresh_branch_cache(db, repo) if refresh and repos.git_dir(repo) else list(repo.branches_cache or [])
    if q:
        needle = q.lower()
        rows = [row for row in rows if needle in str(row.get("name", "")).lower()]
    return {
        "branches": rows,
        "product_branch": repos.product_branch(repo) if repos.git_dir(repo) else (repo.product_branch or repo.default_branch or ""),
        "release_pattern": repo.release_pattern,
        "last_fetch_at": repo.last_fetch_at.isoformat() if repo.last_fetch_at else None,
        "last_fetch_status": repo.last_fetch_status or "never",
        "last_fetch_error": repo.last_fetch_error or "",
    }


@router.post("/repositories/{repo_id}/test")
def test_repository(repo_id: int, _: Principal = Depends(require_admin), db: Session = Depends(get_db)):
    """`git ls-remote` with the repository's credential: proves access without fetching."""
    repo = _repo(db, repo_id)
    if repo.mode == "local":
        path = repos.product_checkout_path(repo)
        ok = bool(path and (path / ".git").exists())
        return {"ok": ok, "status": "ok" if ok else "error", "message": "Local clone found." if ok else f"No git clone at {path}", "egress_ip": ""}
    import tempfile
    from pathlib import Path

    with repos.git_auth(db, repo) as (env, url):
        proc = repos.run_git(Path(tempfile.gettempdir()), "ls-remote", "--heads", url, env=env, timeout=60)
    if proc.returncode == 0:
        heads = len([line for line in (proc.stdout or "").splitlines() if line.strip()])
        return {"ok": True, "status": "ok", "message": f"Access confirmed: {heads} branches visible.", "egress_ip": repos.egress_ip()}
    raw = (proc.stderr or proc.stdout or "")
    status = repos.classify_fetch_error(raw)
    return {"ok": False, "status": status, "message": repos.explain_fetch_error(status, raw), "egress_ip": repos.egress_ip()}

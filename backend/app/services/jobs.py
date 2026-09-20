"""Background jobs so long Refresh / index calls return 202 + poll."""

from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.database import SessionLocal
from app.models import BackgroundJob, PipelineRun
from app.services.time_window import now_local

log = logging.getLogger(__name__)

ORPHAN_ERROR = "Refresh was interrupted because the server restarted. Retrying is safe."
HANG_MINUTES = 20


def job_out(row: BackgroundJob | None) -> dict | None:
    if not row:
        return None
    return {
        "id": row.id,
        "kind": row.kind,
        "status": row.status,
        "steps": row.steps or {},
        "result": row.result or {},
        "error": row.error or "",
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
    }


def worker_pid() -> int:
    return os.getpid()


def _is_live_worker(pid: int | None) -> bool:
    return bool(pid) and int(pid) == worker_pid()


def _fail_row(row: BackgroundJob, error: str) -> None:
    row.status = "failed"
    row.error = (error or ORPHAN_ERROR)[:800]
    row.finished_at = datetime.utcnow()


def reap_orphaned_jobs(db: Session, kind: str | None = None) -> int:
    """Fail jobs whose worker process is gone (uvicorn --reload, crash)."""
    query = db.query(BackgroundJob).filter(BackgroundJob.status.in_(("queued", "running")))
    if kind:
        query = query.filter(BackgroundJob.kind == kind)
    n = 0
    hang_cutoff = datetime.utcnow() - timedelta(minutes=HANG_MINUTES)
    for row in query.all():
        started = (row.created_at or hang_cutoff).replace(tzinfo=None)
        orphan = not _is_live_worker(row.worker_pid)
        # A batch of marketing films may take hours; each subprocess has its own timeout.
        cutoff = datetime.utcnow() - timedelta(hours=12) if row.kind == "marketing" else hang_cutoff
        hung = started < cutoff
        if orphan or hung:
            _fail_row(row, ORPHAN_ERROR if orphan else "stale job")
            n += 1
    if n:
        db.commit()
        log.warning("reaped %s orphaned/hung background job(s)", n)
    return n


def fail_stale_pipeline_runs(db: Session | None = None) -> int:
    own = db is None
    session = db or SessionLocal()
    try:
        n = 0
        running = session.query(PipelineRun).filter(PipelineRun.status == "running").all()
        for run in running:
            run.status = "failed"
            run.error = run.error or ORPHAN_ERROR
            run.finished_at = datetime.utcnow()
            n += 1
        if n:
            session.commit()
            log.warning("reaped %s in-flight pipeline run(s) after restart", n)
        return n
    finally:
        if own:
            session.close()


def recover_after_restart() -> None:
    session = SessionLocal()
    try:
        reap_orphaned_jobs(session)
        fail_stale_pipeline_runs(session)
    except Exception:
        session.rollback()
        log.exception("could not reap interrupted refresh jobs")
    finally:
        session.close()
    try:
        from app.services.codebase import clear_stale_git_locks, codebase_root

        clear_stale_git_locks(codebase_root(), max_age_s=5)
    except Exception:
        log.exception("could not clear leftover git locks")
    try:
        from app.services.marketing_manager import start_recovery_worker
        start_recovery_worker()
    except Exception:
        log.exception("could not resume marketing queue")
    try:
        from app.services.release_worker import catchup_stuck_jobs

        catchup_stuck_jobs()
    except Exception:
        log.exception("could not resume interrupted release jobs")


def get_job(db: Session, job_id: int) -> BackgroundJob | None:
    reap_orphaned_jobs(db)
    return db.query(BackgroundJob).filter(BackgroundJob.id == job_id).one_or_none()


def enqueue(db: Session, kind: str, work) -> BackgroundJob:
    reap_orphaned_jobs(db, kind)
    existing = (
        db.query(BackgroundJob)
        .filter(BackgroundJob.kind == kind, BackgroundJob.status.in_(("queued", "running")))
        .order_by(BackgroundJob.id.desc())
        .first()
    )
    if existing and _is_live_worker(existing.worker_pid):
        return existing
    if existing:
        _fail_row(existing, ORPHAN_ERROR)
        db.commit()
    row = BackgroundJob(
        kind=kind,
        status="queued",
        steps={},
        result={},
        error="",
        worker_pid=worker_pid(),
        created_at=now_local().replace(tzinfo=None),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    job_id = row.id

    def run() -> None:
        session = SessionLocal()
        try:
            job = session.query(BackgroundJob).filter(BackgroundJob.id == job_id).one()
            job.status = "running"
            job.worker_pid = worker_pid()
            session.commit()

            def set_step(name: str, payload: dict) -> None:
                current = dict(job.steps or {})
                current[name] = payload
                job.steps = current
                flag_modified(job, "steps")
                session.add(job)
                session.commit()

            result = work(session, set_step) or {}
            job = session.query(BackgroundJob).filter(BackgroundJob.id == job_id).one()
            job.result = result if isinstance(result, dict) else {"ok": True}
            job.status = "completed" if (job.result or {}).get("ok", True) else "failed"
            job.error = (job.result or {}).get("error") or ""
            job.finished_at = datetime.utcnow()
            session.commit()
        except Exception as exc:
            log.exception("background job %s failed", job_id)
            try:
                job = session.query(BackgroundJob).filter(BackgroundJob.id == job_id).one_or_none()
                if job:
                    job.status = "failed"
                    job.error = str(exc)[:800]
                    job.finished_at = datetime.utcnow()
                    session.commit()
            except Exception:
                session.rollback()
        finally:
            session.close()

    threading.Thread(target=run, daemon=True, name=f"job-{kind}-{job_id}").start()
    return row

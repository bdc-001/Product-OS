"""Runs: leased, heartbeated executions of pipeline tasks.

Two ways to start work:

* `enqueue(db, "refresh")` with a registered task name (see `app.pipelines.tasks`). The run is
  queued in the database and any worker process claims it, so it survives deploys and scales out.
* `enqueue(db, "artifact", work)` with a closure. It runs in this process (the closure cannot be
  serialized) but still holds a lease, so a crash or deploy marks it failed instead of leaving it
  "running" forever.

A run's lease is extended by a heartbeat while it executes. When a lease expires the run is
retried (named tasks with attempts left) or failed with `ORPHAN_ERROR`.
"""

from __future__ import annotations

import logging
import os
import socket
import threading
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any, Callable

from sqlalchemy import select, update
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app import context
from app.database import SessionLocal, engine
from app.models import PipelineRun, Run

log = logging.getLogger(__name__)

ORPHAN_ERROR = "This run stopped because its worker went away (restart or deploy). Retrying is safe."
CANCELLED = "Cancelled"
ACTIVE = ("queued", "running")
LEASE_SECONDS = 120
HEARTBEAT_SECONDS = 30
STALE_QUEUED = timedelta(hours=6)
WORKER_ID = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:6]}"
MAX_LOG_LINES = 400

StepFn = Callable[[str, dict], None]


class RunCancelled(Exception):
    pass


def worker_pid() -> int:
    return os.getpid()


def _now() -> datetime:
    return datetime.utcnow()


def job_out(row: Run | None) -> dict | None:
    if not row:
        return None
    duration = None
    if row.started_at:
        duration = int(((row.finished_at or _now()) - row.started_at).total_seconds())
    return {
        "id": row.id,
        "kind": row.kind,
        "pipeline_id": row.pipeline_id or "",
        "task": row.task or "",
        "status": row.status,
        "trigger": row.trigger or "manual",
        "started_by": row.started_by or "",
        "params": row.params or {},
        "steps": row.steps or {},
        "result": row.result or {},
        "error": row.error or "",
        "attempts": row.attempts or 0,
        "cancel_requested": bool(row.cancel_requested),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        "duration_s": duration,
    }


def run_detail(row: Run) -> dict:
    return {**job_out(row), "logs": list(row.logs or [])[-MAX_LOG_LINES:], "cost": row.cost or {}}


# Per-run log capture: records emitted while a run's context is active land in `runs.logs`.

_LOG_BUFFERS: dict[int, deque] = defaultdict(lambda: deque(maxlen=MAX_LOG_LINES))
_LOG_GUARD = threading.Lock()


class RunLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        ctx = context.current()
        if ctx is None or not ctx.run_id:
            return
        try:
            line = {"at": datetime.utcfromtimestamp(record.created).isoformat(timespec="seconds"), "level": record.levelname.lower(), "message": record.getMessage()[:1000]}
        except Exception:
            return
        with _LOG_GUARD:
            _LOG_BUFFERS[ctx.run_id].append(line)


_handler = RunLogHandler(level=logging.INFO)
if not any(isinstance(h, RunLogHandler) for h in logging.getLogger().handlers):
    logging.getLogger().addHandler(_handler)
    if logging.getLogger().level > logging.INFO or logging.getLogger().level == logging.NOTSET:
        logging.getLogger().setLevel(logging.INFO)


def _drain_logs(run_id: int) -> list[dict]:
    with _LOG_GUARD:
        buffer = _LOG_BUFFERS.pop(run_id, None)
    return list(buffer or [])


def _flush_logs(job: Run) -> None:
    fresh = _drain_logs(job.id)
    if fresh:
        job.logs = (list(job.logs or []) + fresh)[-MAX_LOG_LINES:]
        flag_modified(job, "logs")


# Lease bookkeeping


def _take_lease(row: Run) -> None:
    now = _now()
    row.lease_owner = WORKER_ID
    row.lease_expires_at = now + timedelta(seconds=LEASE_SECONDS)
    row.heartbeat_at = now
    row.worker_pid = os.getpid()


def _fail(row: Run, error: str) -> None:
    row.status = "failed"
    row.error = (error or ORPHAN_ERROR)[:800]
    row.finished_at = _now()
    row.lease_owner = ""
    row.lease_expires_at = None


def _requeue(row: Run, delay_seconds: int = 0) -> None:
    row.status = "queued"
    row.lease_owner = ""
    row.lease_expires_at = _now() + timedelta(seconds=delay_seconds) if delay_seconds else None


def _is_orphan(row: Run, now: datetime) -> bool:
    if row.status == "running":
        if row.lease_expires_at is None:
            # Rows from before leases: owned by a process id.
            return int(row.worker_pid or 0) != os.getpid()
        return row.lease_expires_at < now
    if row.status == "queued":
        if row.lease_owner:
            return bool(row.lease_expires_at and row.lease_expires_at < now)
        return bool(row.created_at and row.created_at < now - STALE_QUEUED)
    return False


def reap_orphaned_jobs(db: Session, kind: str | None = None) -> int:
    """Retry or fail runs whose lease expired (crash, deploy, `--reload`)."""
    from app.pipelines.tasks import TASKS

    query = db.query(Run).filter(Run.status.in_(ACTIVE))
    if kind:
        query = query.filter(Run.kind == kind)
    now = _now()
    n = 0
    for row in query.all():
        if not _is_orphan(row, now):
            continue
        if row.status == "running" and row.task in TASKS and (row.attempts or 0) < (row.max_attempts or 1):
            _requeue(row, delay_seconds=30 * (row.attempts or 1))
        else:
            _fail(row, ORPHAN_ERROR)
        n += 1
    if n:
        db.commit()
        log.warning("reaped %s orphaned run(s)", n)
    return n


def fail_stale_pipeline_runs(db: Session) -> int:
    n = 0
    for run in db.query(PipelineRun).filter(PipelineRun.status == "running").all():
        started = run.started_at or _now()
        if started.replace(tzinfo=None) < _now() - timedelta(minutes=30):
            run.status = "failed"
            run.error = run.error or ORPHAN_ERROR
            run.finished_at = _now()
            n += 1
    if n:
        db.commit()
    return n


def get_job(db: Session, job_id: int) -> Run | None:
    row = db.query(Run).filter(Run.id == job_id).one_or_none()
    if row is not None and row.status in ACTIVE and _is_orphan(row, _now()):
        reap_orphaned_jobs(db, row.kind)
        db.refresh(row)
    return row


def active_run(db: Session, kind: str) -> Run | None:
    return db.query(Run).filter(Run.kind == kind, Run.status.in_(ACTIVE)).order_by(Run.id.desc()).first()


def enqueue(
    db: Session,
    kind: str,
    work: Callable[[Session, StepFn], Any] | None = None,
    *,
    task: str = "",
    params: dict | None = None,
    pipeline_id: str = "",
    trigger: str = "manual",
    started_by: str = "",
    max_attempts: int = 1,
    parent_run_id: int | None = None,
) -> Run:
    from app.pipelines.registry import TASK_PIPELINE
    from app.pipelines.tasks import TASKS

    task = task or ("" if work is not None else kind)
    if work is None and task not in TASKS:
        raise KeyError(f"Unknown task: {task}")
    reap_orphaned_jobs(db, kind)
    existing = active_run(db, kind)
    if existing is not None:
        return existing
    ctx = context.current()
    row = Run(
        kind=kind,
        task=task,
        pipeline_id=pipeline_id or TASK_PIPELINE.get(task or kind, ""),
        params=dict(params or {}),
        trigger=trigger,
        started_by=started_by or (ctx.user_email if ctx else ""),
        parent_run_id=parent_run_id,
        status="queued",
        steps={},
        logs=[],
        result={},
        cost={},
        error="",
        attempts=0,
        max_attempts=max(1, max_attempts),
        created_at=_now(),
    )
    if work is not None:
        _take_lease(row)
        row.status = "running"
        row.started_at = _now()
        row.attempts = 1
    db.add(row)
    db.commit()
    db.refresh(row)
    if work is None:
        from app.pipelines import worker

        worker.notify()
        return row
    run_id = row.id
    context.spawn(execute, run_id, work, name=f"run-{kind}-{run_id}")
    return row


def request_cancel(db: Session, row: Run) -> Run:
    if row.status == "queued":
        row.status = "cancelled"
        row.error = CANCELLED
        row.finished_at = _now()
        row.lease_owner = ""
        row.lease_expires_at = None
    elif row.status == "running":
        row.cancel_requested = True
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def retry_run(db: Session, row: Run) -> Run:
    from app.pipelines.tasks import TASKS

    if row.task not in TASKS:
        raise ValueError("This run was started from a page; start it again there.")
    return enqueue(db, row.kind, task=row.task, params=row.params or {}, pipeline_id=row.pipeline_id, trigger="retry", max_attempts=row.max_attempts or 1, parent_run_id=row.id)


def _heartbeat(run_id: int, stop: threading.Event, cancel: threading.Event) -> None:
    table = Run.__table__
    while not stop.wait(HEARTBEAT_SECONDS):
        try:
            now = _now()
            with engine.begin() as conn:
                conn.execute(
                    update(table)
                    .where(table.c.id == run_id, table.c.lease_owner == WORKER_ID)
                    .values(lease_expires_at=now + timedelta(seconds=LEASE_SECONDS), heartbeat_at=now)
                )
                flag = conn.execute(select(table.c.cancel_requested).where(table.c.id == run_id)).scalar()
            if flag:
                cancel.set()
        except Exception:
            log.debug("heartbeat for run %s failed", run_id, exc_info=True)


def execute(run_id: int, work: Callable[[Session, StepFn], Any]) -> None:
    """Run `work` for an already-leased run inside the current workspace context."""
    ctx = context.require()
    with context.use(ctx.child(run_id=run_id)):
        session = SessionLocal()
        stop, cancel = threading.Event(), threading.Event()
        beat = context.spawn(_heartbeat, run_id, stop, cancel, name=f"run-{run_id}-heartbeat")
        try:
            job = session.query(Run).filter(Run.id == run_id).one()
            job.status = "running"
            job.started_at = job.started_at or _now()
            session.commit()

            def set_step(name: str, payload: dict) -> None:
                if cancel.is_set():
                    raise RunCancelled()
                current = dict(job.steps or {})
                current[name] = payload
                job.steps = current
                flag_modified(job, "steps")
                _flush_logs(job)
                session.add(job)
                session.commit()

            result = work(session, set_step) or {}
            session.expire_all()
            job = session.query(Run).filter(Run.id == run_id).one()
            job.result = result if isinstance(result, dict) else {"ok": True}
            job.status = "completed" if (job.result or {}).get("ok", True) else "failed"
            job.error = str((job.result or {}).get("error") or "")[:2000]
            job.finished_at = _now()
            job.lease_owner = ""
            job.lease_expires_at = None
            _flush_logs(job)
            session.commit()
        except Exception as exc:
            session.rollback()
            cancelled = isinstance(exc, RunCancelled)
            if not cancelled:
                log.exception("run %s failed", run_id)
            try:
                job = session.query(Run).filter(Run.id == run_id).one_or_none()
                if job is not None:
                    from app.pipelines.tasks import TASKS

                    if not cancelled and job.task in TASKS and (job.attempts or 0) < (job.max_attempts or 1):
                        _requeue(job, delay_seconds=20 * (job.attempts or 1))
                        job.error = str(exc)[:800]
                    else:
                        job.status = "cancelled" if cancelled else "failed"
                        job.error = CANCELLED if cancelled else str(exc)[:800]
                        job.finished_at = _now()
                        job.lease_owner = ""
                        job.lease_expires_at = None
                    _flush_logs(job)
                    session.commit()
            except Exception:
                session.rollback()
        finally:
            stop.set()
            session.close()
            beat.join(timeout=1)
            _drain_logs(run_id)


def run_named(run_id: int) -> None:
    """Execute a claimed run of a registered task (called by the worker inside its workspace)."""
    from app.pipelines.tasks import TASKS

    db = SessionLocal()
    try:
        row = db.query(Run).filter(Run.id == run_id).one()
        task, params = row.task, dict(row.params or {})
        params.setdefault("trigger", row.trigger or "manual")
    finally:
        db.close()
    fn = TASKS[task]
    execute(run_id, lambda session, set_step: fn(session, set_step, params))


def recover_after_restart() -> None:
    """Kept for callers from before the worker; the worker reaps expired leases itself."""
    from app.pipelines import worker

    worker.recover()

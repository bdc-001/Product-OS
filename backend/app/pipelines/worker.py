"""Claims queued runs from the database and executes them in their workspace.

Started inline by the API (`RUN_WORKER=inline`, laptop and single-container hosting) or as its own
process (`python -m app.pipelines.worker`). Any number of workers can run: a claim is a single
atomic UPDATE (`FOR UPDATE SKIP LOCKED` on Postgres), and leases expire if a worker dies.
"""

from __future__ import annotations

import logging
import signal
import threading
from datetime import datetime, timedelta

from sqlalchemy import bindparam, text

from app import context
from app.config import settings
from app.database import SessionLocal, engine, is_postgres

log = logging.getLogger(__name__)

POLL_SECONDS = 3
PER_WORKSPACE = 2

_wake = threading.Event()
_stop = threading.Event()
_thread: threading.Thread | None = None
_slots: threading.Semaphore | None = None
_running: set[int] = set()
_running_guard = threading.Lock()


def notify() -> None:
    _wake.set()


def _claim_sql() -> str:
    lock = "FOR UPDATE SKIP LOCKED" if is_postgres() else ""
    return f"""
        UPDATE runs SET status = 'running', lease_owner = :owner, lease_expires_at = :expires,
               heartbeat_at = :now, started_at = COALESCE(started_at, :now),
               attempts = attempts + 1, worker_pid = :pid
        WHERE id = (
            SELECT id FROM runs
            WHERE status = 'queued' AND lease_owner = '' AND task IN :tasks
              AND (lease_expires_at IS NULL OR lease_expires_at <= :now)
              AND workspace_id NOT IN (
                  SELECT workspace_id FROM runs WHERE status = 'running'
                  GROUP BY workspace_id HAVING COUNT(*) >= :per_workspace
              )
            ORDER BY id
            LIMIT 1
            {lock}
        ) AND status = 'queued'
        RETURNING id, workspace_id
    """


def claim() -> tuple[int, int] | None:
    import os

    from app.pipelines.tasks import TASKS
    from app.services.jobs import LEASE_SECONDS, WORKER_ID

    now = datetime.utcnow()
    statement = text(_claim_sql()).bindparams(bindparam("tasks", expanding=True))
    with engine.begin() as conn:
        row = conn.execute(
            statement,
            {
                "owner": WORKER_ID,
                "expires": now + timedelta(seconds=LEASE_SECONDS),
                "now": now,
                "pid": os.getpid(),
                "tasks": sorted(TASKS),
                "per_workspace": PER_WORKSPACE,
            },
        ).first()
    return (int(row[0]), int(row[1])) if row else None


def reap_expired() -> int:
    from app.services.jobs import reap_orphaned_jobs

    with context.system():
        db = SessionLocal()
        try:
            return reap_orphaned_jobs(db)
        finally:
            db.close()


def _execute(run_id: int, workspace_id: int) -> None:
    from app.services.jobs import run_named
    from app.workspaces import context_for

    try:
        db = SessionLocal()
        try:
            ctx = context_for(db, workspace_id)
        finally:
            db.close()
        with context.use(ctx):
            run_named(run_id)
    except Exception:
        log.exception("worker could not execute run %s", run_id)
    finally:
        with _running_guard:
            _running.discard(run_id)
        if _slots is not None:
            _slots.release()
        _wake.set()


def tick() -> int:
    """Reap, then claim as many runs as there are free slots. Returns how many started."""
    started = 0
    try:
        reap_expired()
    except Exception:
        log.exception("reaping expired runs failed")
    while _slots is not None and _slots.acquire(blocking=False):
        try:
            claimed = claim()
        except Exception:
            _slots.release()
            log.exception("claiming a run failed")
            break
        if claimed is None:
            _slots.release()
            break
        run_id, workspace_id = claimed
        with _running_guard:
            _running.add(run_id)
        threading.Thread(target=_execute, args=(run_id, workspace_id), name=f"worker-run-{run_id}", daemon=True).start()
        started += 1
    return started


def _loop() -> None:
    log.info("run worker started (%s slots)", settings.env_value("worker_concurrency"))
    while not _stop.is_set():
        tick()
        _wake.wait(POLL_SECONDS)
        _wake.clear()
    log.info("run worker stopped")


def recover() -> None:
    """After a restart: reap expired leases and resume work that lived outside the run table."""
    reap_expired()
    from app.models import ReleaseJob, Workspace
    from app.workspaces import in_workspace

    with context.system():
        db = SessionLocal()
        try:
            workspace_ids = [row.id for row in db.query(Workspace.id).all()]
        finally:
            db.close()
    for workspace_id in workspace_ids:
        db = SessionLocal()
        try:
            with in_workspace(db, workspace_id):
                from app.services.jobs import fail_stale_pipeline_runs
                from app.services.marketing_manager import schedule_pending
                from app.services.release_worker import catchup_stuck_jobs

                fail_stale_pipeline_runs(db)
                if db.query(ReleaseJob.id).first():
                    catchup_stuck_jobs()
                schedule_pending(db)
        except Exception:
            log.exception("recovery failed for workspace %s", workspace_id)
        finally:
            db.close()


def start(concurrency: int | None = None) -> None:
    global _thread, _slots
    if _thread is not None and _thread.is_alive():
        return
    _stop.clear()
    _slots = threading.Semaphore(max(1, int(concurrency or settings.env_value("worker_concurrency") or 4)))
    try:
        recover()
    except Exception:
        log.exception("worker recovery failed")
    _thread = threading.Thread(target=_loop, name="run-worker", daemon=True)
    _thread.start()


def stop() -> None:
    _stop.set()
    _wake.set()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    from app.bootstrap import bootstrap

    bootstrap()
    start()
    if settings.env_value("run_scheduler"):
        from app.pipelines import scheduler

        scheduler.start()
    done = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: done.set())
    done.wait()
    stop()


if __name__ == "__main__":
    main()

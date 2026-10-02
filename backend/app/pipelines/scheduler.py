"""Fires scheduled pipelines for every workspace. Replaces APScheduler jobs and the launchd sync.

Exactly one process is the leader (a Postgres advisory lock; SQLite installs are single-process).
Every tick it compares each enabled schedule (cron, in the workspace timezone) with the config's
`last_fired_at` and enqueues a run when a fire time has passed. Missed fires collapse into one run.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import text

from app import context
from app.database import SessionLocal, engine, is_postgres

log = logging.getLogger(__name__)

TICK_SECONDS = 30
LOCK_KEY = 72_900_001
MAINTENANCE_EVERY = timedelta(minutes=10)

_stop = threading.Event()
_thread: threading.Thread | None = None
_leader_conn = None
_last_maintenance: datetime | None = None


def _tz(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name or "Asia/Kolkata")
    except Exception:
        return ZoneInfo("Asia/Kolkata")


def next_fire(schedule: str, tz_name: str, after: datetime) -> datetime | None:
    """Next fire time (naive UTC) strictly after `after` (naive UTC)."""
    tz = _tz(tz_name)
    trigger = CronTrigger.from_crontab(schedule, timezone=tz)
    anchor = after.replace(tzinfo=dt_timezone.utc).astimezone(tz)
    fire = trigger.get_next_fire_time(None, anchor + timedelta(seconds=1))
    return fire.astimezone(dt_timezone.utc).replace(tzinfo=None) if fire else None


def valid_schedule(schedule: str) -> bool:
    try:
        CronTrigger.from_crontab(schedule)
        return True
    except (ValueError, TypeError):
        return False


def is_leader() -> bool:
    global _leader_conn
    if not is_postgres():
        return True
    if _leader_conn is not None:
        return True
    conn = engine.connect()
    got = conn.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_KEY}).scalar()
    if got:
        _leader_conn = conn
        log.info("scheduler leadership acquired")
        return True
    conn.close()
    return False


def due_configs(now: datetime) -> list[tuple[int, int, str]]:
    """(workspace_id, config_id, pipeline_id) for every schedule whose next fire time has passed."""
    from app.models import PipelineConfig, Workspace

    due = []
    with context.system():
        db = SessionLocal()
        try:
            rows = (
                db.query(PipelineConfig, Workspace.timezone)
                .join(Workspace, Workspace.id == PipelineConfig.workspace_id)
                .filter(PipelineConfig.schedule_enabled.is_(True), PipelineConfig.enabled.is_(True), PipelineConfig.schedule != "")
                .all()
            )
            for config, tz_name in rows:
                anchor = config.last_fired_at or config.updated_at or now
                try:
                    fire = next_fire(config.schedule, tz_name, anchor)
                except (ValueError, TypeError):
                    continue
                if fire is not None and fire <= now:
                    due.append((config.workspace_id, config.id, config.pipeline_id))
        finally:
            db.close()
    return due


def fire(workspace_id: int, config_id: int, pipeline_id: str, now: datetime) -> int | None:
    from app.models import PipelineConfig
    from app.pipelines.registry import PipelineNotReady, start_pipeline
    from app.workspaces import in_workspace

    db = SessionLocal()
    try:
        with in_workspace(db, workspace_id):
            config = db.get(PipelineConfig, config_id)
            if config is None:
                return None
            config.last_fired_at = now
            db.commit()
            try:
                run = start_pipeline(db, pipeline_id, trigger="schedule", started_by="schedule")
            except PipelineNotReady as exc:
                log.info("skipped scheduled %s in workspace %s: %s", pipeline_id, workspace_id, exc)
                return None
            return run.id
    except Exception:
        log.exception("scheduled %s failed to start in workspace %s", pipeline_id, workspace_id)
        return None
    finally:
        db.close()


def maintenance(now: datetime) -> None:
    """Pick up queued marketing campaigns and evict old source indexes, per workspace."""
    from app.models import MarketingCampaign, Workspace
    from app.services.jobs import active_run, enqueue
    from app.services.marketing_manager import PENDING
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
                if db.query(MarketingCampaign.id).filter(MarketingCampaign.status.in_(PENDING)).first() and not active_run(db, "marketing"):
                    enqueue(db, "marketing", trigger="recovery", started_by="system")
                if not active_run(db, "source-index-evict"):
                    enqueue(db, "source-index-evict", trigger="maintenance", started_by="system")
        except Exception:
            log.exception("maintenance failed for workspace %s", workspace_id)
        finally:
            db.close()


def tick(now: datetime | None = None) -> list[int]:
    global _last_maintenance
    now = now or datetime.utcnow()
    if not is_leader():
        return []
    started = []
    for workspace_id, config_id, pipeline_id in due_configs(now):
        run_id = fire(workspace_id, config_id, pipeline_id, now)
        if run_id:
            started.append(run_id)
    if _last_maintenance is None or now - _last_maintenance >= MAINTENANCE_EVERY:
        _last_maintenance = now
        try:
            maintenance(now)
        except Exception:
            log.exception("scheduler maintenance failed")
    return started


def _loop() -> None:
    while not _stop.is_set():
        try:
            tick()
        except Exception:
            log.exception("scheduler tick failed")
        _stop.wait(TICK_SECONDS)


def start() -> None:
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="scheduler", daemon=True)
    _thread.start()


def stop() -> None:
    global _leader_conn
    _stop.set()
    if _leader_conn is not None:
        try:
            _leader_conn.close()
        except Exception:
            pass
        _leader_conn = None

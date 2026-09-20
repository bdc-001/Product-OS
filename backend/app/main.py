from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import logging
import time

from app.api.routers import router
from app import models as _models  # noqa: F401
from app.config import settings, validate_startup
from app.database import Base, SessionLocal, engine, migrate_schema
from app.models import PipelineRun
from app.services.jobs import recover_after_restart
from app.services.pipeline import deliver_standup, email_standup, run_pipeline

log = logging.getLogger(__name__)

Base.metadata.create_all(bind=engine)
migrate_schema()

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api")


def _mark_dead_letter(error: str) -> None:
    db = SessionLocal()
    try:
        run = PipelineRun(
            status="dead_letter",
            trigger="schedule",
            error=(error or "scheduled standup failed after retries")[:800],
            dead_letter=True,
            attempt=3,
        )
        db.add(run)
        db.commit()
    except Exception:
        db.rollback()
        log.exception("could not record dead-letter standup")
    finally:
        db.close()


def _scheduled_standup() -> None:
    delays = (0, 20, 60)
    last_error = ""
    for attempt, delay in enumerate(delays, start=1):
        if delay:
            time.sleep(delay)
        db = SessionLocal()
        try:
            run = run_pipeline(db, trigger="schedule")
            if run.status == "completed":
                deliver_standup(db)
                return
            last_error = run.error or f"status {run.status}"
            run.attempt = attempt
            if attempt >= len(delays):
                run.dead_letter = True
                run.status = "dead_letter"
            db.commit()
        except Exception as exc:
            last_error = str(exc)
            log.exception("scheduled standup attempt %s failed", attempt)
        finally:
            db.close()
    _mark_dead_letter(last_error)


def _scheduled_standup_nudge() -> None:
    db = SessionLocal()
    try:
        email_standup(db, nudge=True)
    except Exception:
        log.exception("standup nudge email failed")
    finally:
        db.close()


def _scheduled_release_notes() -> None:
    db = SessionLocal()
    try:
        from app.services.release_worker import detect_and_enqueue

        detect_and_enqueue(db, triggered_by="schedule")
    except Exception:
        log.exception("scheduled release detect failed")
    finally:
        db.close()


scheduler = BackgroundScheduler(timezone=settings.timezone)
scheduler.add_job(
    _scheduled_standup,
    CronTrigger(day_of_week="mon-fri", hour=settings.standup_hour, minute=0, timezone=settings.timezone),
    id="daily_standup",
    replace_existing=True,
    max_instances=1,
    coalesce=True,
)
scheduler.add_job(
    _scheduled_standup_nudge,
    CronTrigger(day_of_week="mon-fri", hour=settings.standup_hour - 1 if settings.standup_hour else 8, minute=settings.standup_nudge_minute, timezone=settings.timezone),
    id="standup_nudge",
    replace_existing=True,
    max_instances=1,
    coalesce=True,
)
if settings.release_notes_enable_scheduler:
    scheduler.add_job(
        _scheduled_release_notes,
        CronTrigger(hour=settings.release_notes_hour, minute=0, timezone=settings.timezone),
        id="daily_release_notes",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )


@app.on_event("startup")
def startup() -> None:
    validate_startup()
    recover_after_restart()
    if not scheduler.running:
        scheduler.start()


@app.on_event("shutdown")
def shutdown() -> None:
    if scheduler.running:
        scheduler.shutdown(wait=False)


@app.get("/")
def root():
    return {"name": settings.app_name, "docs": "/docs"}

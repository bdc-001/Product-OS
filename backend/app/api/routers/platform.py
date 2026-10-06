from datetime import datetime
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import context
from app.api.common import standup_out
from app.clients.cliq import CliqClient
from app.clients.jira import JiraClient
from app.clients.llm import LLMClient
from app.config import settings
from app.database import get_db
from app.models import Evaluation, HiddenCard, JiraIssue, PipelineRun, Standup
from app.pipelines.registry import connection_states
from app.pipelines.tasks import SECTIONS
from app.services.hidden import hidden_keys
from app.services.jobs import enqueue, get_job, job_out
from app.services.pipeline import run_pipeline
from app.services.profile import load_profile
from app.services.time_window import format_ist, now_local, period_for

router = APIRouter()
_HEALTH_CACHE: dict[int, tuple[float, dict]] = {}
_HEALTH_TTL = 15.0


def _boards() -> list[str]:
    raw = settings.jira_projects or settings.jira_allowed_projects or ""
    return [key.strip().upper() for key in raw.split(",") if key.strip()]


@router.get("/health")
def health(db: Session = Depends(get_db)):
    ws = context.require()
    now = time.monotonic()
    cached = _HEALTH_CACHE.get(ws.id)
    if cached and now - cached[0] < _HEALTH_TTL:
        return dict(cached[1])
    last = (
        db.query(PipelineRun)
        .filter(PipelineRun.status == "completed")
        .order_by(PipelineRun.finished_at.desc(), PipelineRun.id.desc())
        .first()
    )
    dead = db.query(PipelineRun).filter(PipelineRun.dead_letter.is_(True)).order_by(PipelineRun.id.desc()).first()
    last_at = last.finished_at or last.started_at if last else None
    age_seconds = int((datetime.utcnow() - last_at.replace(tzinfo=None)).total_seconds()) if last_at else None
    profile = load_profile()
    payload = {
        "ok": True,
        "workspace": ws.slug,
        "jira": JiraClient().configured,
        "cliq": CliqClient().configured,
        "llm": LLMClient().configured,
        "timezone": settings.timezone,
        "now": now_local().isoformat(),
        "now_label": format_ist(now_local()),
        "period": period_for(),
        "headline": "This week's actionables",
        "cliq_user_id": profile.get("pm_cliq_user_id") or "",
        "pm_name": profile.get("pm_display_name") or "",
        "last_run_at": last_at.isoformat() if last_at else None,
        "last_run_age_seconds": age_seconds,
        "last_run_stale": bool(age_seconds is not None and age_seconds > 3 * 3600),
        "last_run_id": last.id if last else None,
        "dead_letter": bool(dead),
        "dead_letter_error": (dead.error if dead else "") or "",
    }
    _HEALTH_CACHE[ws.id] = (now, payload)
    return payload


@router.get("/platform")
def platform(db: Session = Depends(get_db)):
    profile = load_profile()
    boards = {}
    for prefix in _boards():
        boards[prefix] = (
            db.query(func.count(JiraIssue.id))
            .filter(JiraIssue.archived_at.is_(None), JiraIssue.issue_key.ilike(f"{prefix}-%"))
            .scalar()
            or 0
        )
    states = connection_states(db)
    return {
        "app_name": settings.app_name,
        "workspace": context.require().name,
        "product_name": profile.get("product_name") or "",
        "pm_display_name": profile.get("pm_display_name"),
        "pm_cliq_user_id": profile.get("pm_cliq_user_id"),
        "pm_cliq_mentions": profile.get("pm_cliq_mentions"),
        "timezone": settings.timezone,
        "data_branch": profile.get("data_branch") or "",
        "boards": boards,
        "hidden_count": db.query(func.count(HiddenCard.id)).scalar() or 0,
        "connections": {"jira": "jira" in states, "cliq": "cliq" in states, "llm": "llm" in states, **{k: True for k in states}},
        "jira_base_url": settings.jira_base_url,
    }


@router.get("/settings")
def get_settings(db: Session = Depends(get_db)):
    """Read-only summary for older screens; edit through /connections and /workspace."""
    profile = load_profile()
    return {
        "profile": {k: v for k, v in profile.items() if k != "people"},
        "timezone": settings.timezone,
        "connections": connection_states(db),
    }


@router.post("/pipeline/run")
def pipeline_run(ingest: bool = True, db: Session = Depends(get_db)):
    try:
        run = run_pipeline(db, trigger="manual", ingest=ingest)
    except Exception as exc:
        run = db.query(PipelineRun).order_by(PipelineRun.id.desc()).first()
        if run is None:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    standup = db.query(Standup).filter(Standup.run_id == run.id).one_or_none() if run else None
    evaluation = db.query(Evaluation).filter(Evaluation.standup_id == standup.id).one_or_none() if standup else None
    return {
        "run": {
            "id": run.id,
            "status": run.status,
            "window_start": run.window_start.isoformat() if run.window_start else None,
            "window_end": run.window_end.isoformat() if run.window_end else None,
            "jira_count": run.jira_count,
            "cliq_count": run.cliq_count,
            "relevant_cliq_count": run.relevant_cliq_count,
            "change_count": run.change_count,
            "insight_count": run.insight_count,
            "error": run.error,
        },
        "standup": standup_out(standup, evaluation, hidden_keys(db), db) if standup else None,
    }


@router.post("/refresh")
def platform_refresh(db: Session = Depends(get_db)):
    return JSONResponse(status_code=202, content=job_out(enqueue(db, "refresh")))


@router.get("/jobs/{job_id}")
def job_status(job_id: int, db: Session = Depends(get_db)):
    row = get_job(db, job_id)
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return job_out(row)


@router.post("/refresh/{section}")
def refresh_section(section: str, db: Session = Depends(get_db)):
    if section not in SECTIONS:
        raise HTTPException(400, "Unknown refresh section")
    return JSONResponse(status_code=202, content=job_out(enqueue(db, f"refresh-{section}")))


@router.get("/workspace/summary")
def workspace_summary(db: Session = Depends(get_db)):
    # Cheap shell data: no ticket hydration, code indexing, or external requests.
    profile = load_profile()
    return {**health(db), "pm_display_name": profile.get("pm_display_name"), "data_branch": profile.get("data_branch") or ""}

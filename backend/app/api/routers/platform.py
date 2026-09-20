from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.common import ProfileBody, standup_out
from app.clients.cliq import CliqClient
from app.clients.jira import JiraClient
from app.clients.llm import LLMClient
from app.config import settings
from app.database import get_db
from app.models import Evaluation, HiddenCard, JiraIssue, PipelineRun, Standup
from app.services.hidden import hidden_keys
from app.services.jobs import enqueue, get_job, job_out
from app.services.pipeline import run_pipeline
from app.services.profile import load_profile, save_profile
from app.services.workspace import PROFILE_KEYS, capture_runtime, public_settings, save_workspace
from app.services.refresh import refresh_platform
from app.services.time_window import format_ist, now_local, period_for

router = APIRouter()


@router.get("/health")
def health(db: Session = Depends(get_db)):
    jira = JiraClient()
    cliq = CliqClient()
    llm = LLMClient()
    last = (
        db.query(PipelineRun)
        .filter(PipelineRun.status == "completed")
        .order_by(PipelineRun.finished_at.desc(), PipelineRun.id.desc())
        .first()
    )
    dead = (
        db.query(PipelineRun)
        .filter(PipelineRun.dead_letter.is_(True))
        .order_by(PipelineRun.id.desc())
        .first()
    )
    last_at = last.finished_at or last.started_at if last else None
    age_seconds = None
    if last_at:
        age_seconds = int((datetime.utcnow() - last_at.replace(tzinfo=None)).total_seconds())
    stale = bool(age_seconds is not None and age_seconds > 3 * 3600)
    return {
        "ok": True,
        "jira": jira.configured,
        "cliq": cliq.configured,
        "llm": llm.configured,
        "timezone": settings.timezone,
        "now": now_local().isoformat(),
        "now_label": format_ist(now_local()),
        "period": period_for(),
        "headline": "This week's actionables",
        "cliq_user_id": load_profile().get("pm_cliq_user_id") or settings.pm_cliq_user_id,
        "pm_name": load_profile().get("pm_display_name") or settings.pm_display_name,
        "last_run_at": last_at.isoformat() if last_at else None,
        "last_run_age_seconds": age_seconds,
        "last_run_stale": stale,
        "last_run_id": last.id if last else None,
        "dead_letter": bool(dead),
        "dead_letter_error": (dead.error if dead else "") or "",
    }


@router.get("/platform")
def platform(db: Session = Depends(get_db)):
    profile = load_profile()
    def board_count(prefix: str) -> int:
        return (
            db.query(func.count(JiraIssue.id))
            .filter(JiraIssue.archived_at.is_(None), JiraIssue.issue_key.ilike(f"{prefix}-%"))
            .scalar()
            or 0
        )
    ac = board_count("AC")
    ps = board_count("PS")
    hidden = db.query(func.count(HiddenCard.id)).scalar() or 0
    jira = JiraClient()
    cliq = CliqClient()
    llm = LLMClient()
    return {
        "app_name": "PM Platform",
        "pm_display_name": profile.get("pm_display_name"),
        "pm_cliq_user_id": profile.get("pm_cliq_user_id"),
        "pm_cliq_mentions": profile.get("pm_cliq_mentions"),
        "timezone": profile.get("timezone"),
        "data_branch": profile.get("data_branch") or "",
        "boards": {"AC": ac, "PS": ps},
        "hidden_count": hidden,
        "connections": {"jira": jira.configured, "cliq": cliq.configured, "llm": llm.configured},
        "jira_email": settings.jira_email,
        "jira_base_url": settings.jira_base_url,
    }


@router.get("/settings")
def get_settings():
    return public_settings()


@router.patch("/settings")
def patch_settings(body: ProfileBody):
    data = body.model_dump(exclude_none=True)
    identity = {key: data.pop(key) for key in list(data) if key in PROFILE_KEYS}
    if identity:
        save_profile(identity)
    if data:
        return save_workspace(data)
    return public_settings()


@router.post("/settings/capture")
def capture_settings():
    return capture_runtime()


@router.post("/pipeline/run")
def pipeline_run(ingest: bool = True, db: Session = Depends(get_db)):
    try:
        run = run_pipeline(db, trigger="manual", ingest=ingest)
    except Exception as exc:
        run = db.query(PipelineRun).order_by(PipelineRun.id.desc()).first()
        if run is None:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    standup = db.query(Standup).filter(Standup.run_id == run.id).one_or_none() if run else None
    evaluation = (
        db.query(Evaluation).filter(Evaluation.standup_id == standup.id).one_or_none() if standup else None
    )
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
    def work(session, set_step):
        return refresh_platform(session, set_step=set_step)

    job = enqueue(db, "refresh", work)
    return JSONResponse(status_code=202, content=job_out(job))


@router.get("/jobs/{job_id}")
def job_status(job_id: int, db: Session = Depends(get_db)):
    row = get_job(db, job_id)
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return job_out(row)

@router.post("/refresh/{section}")
def refresh_section(section: str, db: Session = Depends(get_db)):
    allowed = {"jira", "cliq", "roadmap", "codebase", "overview"}
    if section not in allowed: raise HTTPException(400, "Unknown refresh section")
    def work(session, set_step):
        from app.services.time_window import briefing_window
        from app.services.ingest import ingest_jira, ingest_cliq
        set_step(section, {"status": "running"})
        start, end = briefing_window().as_naive()
        result = {"ok": True}
        if section == "jira":
            result["jira_count"] = ingest_jira(session, start)
            session.commit()
        elif section == "cliq":
            count, relevant, error = ingest_cliq(session, start, end)
            session.commit()
            result.update(ok=not bool(error), cliq_count=count, error=error)
        elif section == "roadmap":
            from app.services.roadmap import sync_roadmap_statuses
            sync_roadmap_statuses(session, fetch_missing=True)
        elif section == "codebase":
            from app.services.codebase import latest_snapshot, git_status
            from app.services.source_index import build
            snapshot = latest_snapshot(session)
            branch = load_profile().get("data_branch") or (snapshot.branch if snapshot else "") or git_status().get("branch")
            result.update(build(branch))
        else:
            run = run_pipeline(session, trigger="overview", ingest=False)
            result.update(ok=run.status == "completed", error=run.error)
        set_step(section, {**result, "status": "done"})
        return {"ok": result["ok"], "error": result.get("error", ""), "steps": {section: result}}
    return JSONResponse(status_code=202, content=job_out(enqueue(db, f"refresh-{section}", work)))

@router.get("/workspace/summary")
def workspace_summary(db: Session = Depends(get_db)):
    # Cheap shell data: no ticket hydration, code indexing, or external requests.
    profile = load_profile()
    return {**health(db), "pm_display_name": profile.get("pm_display_name"), "data_branch": profile.get("data_branch") or ""}

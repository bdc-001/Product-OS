"""Pipelines catalog, per-workspace pipeline settings and schedules, and run history."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import Principal, current_principal, require_admin
from app.connections import store
from app.database import get_db
from app.models import Run
from app.pipelines.registry import (
    BY_ID,
    CATEGORY_LABELS,
    PipelineNotReady,
    catalog,
    config_for,
    get_pipeline,
    start_pipeline,
    touch_config,
)
from app.pipelines.scheduler import next_fire, valid_schedule
from app.services.jobs import get_job, job_out, request_cancel, retry_run, run_detail

router = APIRouter()


class PipelinePatch(BaseModel):
    enabled: bool | None = None
    schedule: str | None = None
    schedule_enabled: bool | None = None
    settings: dict | None = None


class RunBody(BaseModel):
    params: dict = {}


def _with_next(item: dict, tz: str) -> dict:
    nxt = None
    if item.get("schedule_enabled") and item.get("schedule"):
        try:
            from datetime import datetime

            fire = next_fire(item["schedule"], tz, datetime.utcnow())
            nxt = fire.isoformat() + "Z" if fire else None
        except (ValueError, TypeError):
            nxt = None
    return {**item, "next_run_at": nxt}


@router.get("/pipelines")
def list_pipelines(principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    tz = store.workspace_row(db).timezone
    items = [_with_next(item, tz) for item in catalog(db)]
    return {"pipelines": items, "categories": CATEGORY_LABELS, "can_edit": principal.at_least("admin"), "timezone": tz}


def _one(db: Session, pipeline_id: str) -> dict:
    if pipeline_id not in BY_ID:
        raise HTTPException(status_code=404, detail="Unknown pipeline")
    tz = store.workspace_row(db).timezone
    item = next(p for p in catalog(db) if p["id"] == pipeline_id)
    return _with_next(item, tz)


@router.get("/pipelines/{pipeline_id}")
def pipeline_detail(pipeline_id: str, _: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    item = _one(db, pipeline_id)
    runs = db.query(Run).filter(Run.pipeline_id == pipeline_id).order_by(Run.id.desc()).limit(25).all()
    return {**item, "runs": [job_out(r) for r in runs]}


@router.patch("/pipelines/{pipeline_id}")
def update_pipeline(pipeline_id: str, body: PipelinePatch, principal: Principal = Depends(require_admin), db: Session = Depends(get_db)):
    try:
        pipeline = get_pipeline(pipeline_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown pipeline") from exc
    row = config_for(db, pipeline)
    if body.schedule is not None:
        schedule = body.schedule.strip()
        if schedule and not valid_schedule(schedule):
            raise HTTPException(status_code=422, detail="Use a 5-field cron schedule, e.g. `0 9 * * 1-5`.")
        row.schedule = schedule
    if body.schedule_enabled is not None:
        if body.schedule_enabled and not pipeline.task:
            raise HTTPException(status_code=400, detail="This pipeline runs from its page and cannot be scheduled.")
        row.schedule_enabled = body.schedule_enabled
        if body.schedule_enabled:
            row.last_fired_at = None
    if body.enabled is not None:
        row.enabled = body.enabled
    if body.settings is not None:
        allowed = {f.key: f for f in pipeline.settings}
        merged = dict(row.settings or {})
        for key, value in body.settings.items():
            spec = allowed.get(key)
            if spec is None:
                continue
            if spec.kind == "bool":
                value = bool(value)
            elif spec.kind == "number":
                try:
                    value = int(value)
                except (TypeError, ValueError):
                    continue
            merged[key] = value
        row.settings = merged
    touch_config(row)
    db.add(row)
    store.audit(db, "pipeline.updated", pipeline_id, body.model_dump(exclude_none=True), principal.email)
    db.commit()
    return _one(db, pipeline_id)


@router.post("/pipelines/{pipeline_id}/run")
def run_pipeline_now(pipeline_id: str, body: RunBody | None = None, principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    if pipeline_id not in BY_ID:
        raise HTTPException(status_code=404, detail="Unknown pipeline")
    try:
        run = start_pipeline(db, pipeline_id, params=(body.params if body else {}), started_by=principal.email)
    except PipelineNotReady as exc:
        raise HTTPException(status_code=409, detail={"message": str(exc), "readiness": exc.readiness}) from exc
    return JSONResponse(status_code=202, content=job_out(run))


@router.get("/runs")
def list_runs(
    pipeline: str = "",
    status: str = "",
    limit: int = Query(50, ge=1, le=200),
    before: int = 0,
    _: Principal = Depends(current_principal),
    db: Session = Depends(get_db),
):
    query = db.query(Run)
    if pipeline:
        query = query.filter(Run.pipeline_id == pipeline)
    if status:
        query = query.filter(Run.status.in_(status.split(",")))
    if before:
        query = query.filter(Run.id < before)
    rows = query.order_by(Run.id.desc()).limit(limit).all()
    names = {p.id: p.name for p in BY_ID.values()}
    return {
        "runs": [{**job_out(r), "pipeline_name": names.get(r.pipeline_id, r.kind)} for r in rows],
        "next_before": rows[-1].id if len(rows) == limit else None,
    }


def _run_or_404(db: Session, run_id: int) -> Run:
    row = get_job(db, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return row


@router.get("/runs/{run_id}")
def run_info(run_id: int, _: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    row = _run_or_404(db, run_id)
    names = {p.id: p.name for p in BY_ID.values()}
    children = db.query(Run).filter(Run.parent_run_id == row.id).order_by(Run.id).all()
    return {**run_detail(row), "pipeline_name": names.get(row.pipeline_id, row.kind), "children": [job_out(c) for c in children]}


@router.post("/runs/{run_id}/cancel")
def cancel_run(run_id: int, _: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    return job_out(request_cancel(db, _run_or_404(db, run_id)))


@router.post("/runs/{run_id}/retry")
def retry(run_id: int, principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    try:
        return JSONResponse(status_code=202, content=job_out(retry_run(db, _run_or_404(db, run_id))))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

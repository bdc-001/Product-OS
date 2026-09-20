"""Product Marketing sheet and asynchronous campaign API."""
from datetime import datetime
from typing import Literal
from threading import RLock
from functools import wraps

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import BackgroundJob, MarketingCampaign, MarketingFeature
from app.services.jobs import enqueue, job_out, reap_orphaned_jobs
from app.services.marketing_manager import FORMATS, FormatName, PENDING, queue_feature, drain_queue, sync_released_features, schedule_pending
from app.services.marketing import (
    CAMPAIGN_DIR, campaign_out, discover_features, drive_destination, feature_out,
    identity, produce_campaign, seed_mastersheet, SHEET_STATUSES, TAGS, two_liner,
)

router = APIRouter(prefix="/marketing", tags=["marketing"])
_queue_lock = RLock()


def serialized_start(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        with _queue_lock:
            return fn(*args, **kwargs)
    return wrapped


class FeatureBody(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    description: str = Field(default="", max_length=4000)
    summary: str = Field(default="", max_length=280)
    audience: str = Field(default="", max_length=500)
    benefit: str = Field(default="", max_length=2000)
    notes: str = Field(default="", max_length=4000)
    status: Literal["draft", "candidate", "ready", "dismissed"] = "draft"
    module: str = Field(default="", max_length=120)
    priority: str = Field(default="", max_length=16)
    hook: str = Field(default="", max_length=2000)
    start_date: str = Field(default="", max_length=32)
    end_date: str = Field(default="", max_length=32)
    sheet_status: str = Field(default="Not started", max_length=64)
    script: str = Field(default="", max_length=4000)
    video: str = Field(default="", max_length=4000)
    tag: str = Field(default="New", max_length=64)
    revision: int | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        value = value.strip()
        if not identity(value):
            raise ValueError("Enter a feature name.")
        return value

    @field_validator("sheet_status")
    @classmethod
    def clean_sheet_status(cls, value):
        value = (value or "Not started").strip()
        return value if value in SHEET_STATUSES else "Not started"

    @field_validator("tag")
    @classmethod
    def clean_tag(cls, value):
        value = (value or "New").strip()
        return value if value in TAGS else "New"

    @field_validator("priority")
    @classmethod
    def clean_priority(cls, value):
        value = (value or "").strip().upper()
        if value and value not in {"P1", "P2", "P3"}:
            return value[:16]
        return value


class GenerateBody(BaseModel):
    feature_ids: list[int] = Field(min_length=1, max_length=50)
    formats: list[FormatName] | None = Field(default=None, min_length=1, max_length=9)


@router.get("")
def workspace(db: Session = Depends(get_db)):
    from app.services.marketing_video import video_status
    from app.clients.llm import LLMClient, model_for
    from app.services.gsheets import sheet_status
    seed_mastersheet(db)
    reap_orphaned_jobs(db, "marketing")
    active = db.query(BackgroundJob).filter(BackgroundJob.kind.in_(("marketing", "marketing-discovery")),
        BackgroundJob.status.in_(("running", "queued"))).order_by(BackgroundJob.id.desc()).first()
    from app.services.marketing_status import content_inventory
    campaigns = db.query(MarketingCampaign).order_by(MarketingCampaign.id.desc()).all()
    sync = db.query(BackgroundJob).filter(BackgroundJob.kind.in_(("marketing-discovery", "refresh"))).order_by(BackgroundJob.id.desc()).first()
    return {"features": [{**feature_out(row), "content_status": content_inventory(row, campaigns)} for row in db.query(MarketingFeature).order_by(MarketingFeature.id).all()],
        "campaigns": [campaign_out(row, full=False) for row in campaigns[:100]], "last_sync": job_out(sync),
        "drive": drive_destination(), "sheet": sheet_status(), "video": video_status(),
        "model_configured": LLMClient(model=model_for("marketing_manager")).configured,
        "manager_model": model_for("marketing_manager"), "formats": FORMATS, "active_job": job_out(active),
        "sheet_statuses": list(SHEET_STATUSES), "tags": list(TAGS)}


@router.post("/features", status_code=201)
def add_feature(body: FeatureBody, db: Session = Depends(get_db)):
    data = body.model_dump(exclude={"revision"})
    # Keep PMM brief fields aligned with mastersheet columns.
    if not data["description"] and data["hook"]:
        data["description"] = data["hook"]
    if not data["summary"]:
        data["summary"] = two_liner(data.get("hook"), data.get("description"))
    if not data["benefit"] and data["hook"]:
        data["benefit"] = data["hook"]
    data["tag"] = data.get("tag") or "New"
    data["sheet_status"] = data.get("sheet_status") or "Not started"
    row = MarketingFeature(**data, identity=identity(body.name), source="manual")
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "This feature already exists, possibly as a dismissed row.")
    from app.services.gsheets import best_effort_push
    best_effort_push(db)
    return feature_out(row)


@router.put("/features/{feature_id}")
def update_feature(feature_id: int, body: FeatureBody, db: Session = Depends(get_db)):
    row = db.get(MarketingFeature, feature_id)
    if not row:
        raise HTTPException(404, "Feature not found.")
    if body.revision is None:
        raise HTTPException(409, "Reload the sheet before saving.")
    data = body.model_dump(exclude={"revision"})
    if not data["description"] and data["hook"]:
        data["description"] = data["hook"]
    if not data["summary"]:
        data["summary"] = two_liner(data.get("hook"), data.get("description"))
    if not data["benefit"] and data["hook"]:
        data["benefit"] = data["hook"]
    values = data | {"identity": identity(body.name),
        "revision": body.revision + 1, "updated_at": datetime.utcnow(), "decision": {}}
    try:
        changed = db.query(MarketingFeature).filter_by(id=feature_id, revision=body.revision).update(values)
        if not changed:
            db.rollback()
            raise HTTPException(409, "This row changed in another tab. Reload the sheet before saving.")
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A feature with that name already exists.")
    db.refresh(row)
    from app.services.gsheets import best_effort_push
    best_effort_push(db)
    return feature_out(row)


@router.post("/discover")
def discover(db: Session = Depends(get_db)):
    return JSONResponse(status_code=202, content=job_out(enqueue(db, "marketing-discovery", sync_released_features)))


@router.get("/campaigns/{campaign_id}")
def get_campaign(campaign_id: int, db: Session = Depends(get_db)):
    row = db.get(MarketingCampaign, campaign_id)
    if not row:
        raise HTTPException(404, "Campaign not found.")
    return campaign_out(row)


def busy(db):
    reap_orphaned_jobs(db, "marketing")
    if db.query(BackgroundJob).filter(BackgroundJob.kind == "marketing", BackgroundJob.status.in_(("queued", "running"))).first():
        raise HTTPException(409, "A marketing run is already in progress. Follow its progress on this page.")


@router.post("/generate")
@serialized_start
def generate(body: GenerateBody, db: Session = Depends(get_db)):
    busy(db)
    ids = list(dict.fromkeys(body.feature_ids))
    features = [db.get(MarketingFeature, id) for id in ids]
    if any(row is None for row in features):
        raise HTTPException(404, "One of the selected features no longer exists.")
    if any(row.status == "dismissed" or (row.decision or {}).get("verdict") in {"skip", "defer"} or len(row.description.strip()) < 20 for row in features):
        raise HTTPException(400, "Add a useful use case and keep selected features active. Edit and save skipped/deferred briefs with new evidence before starting.")
    formats = list(dict.fromkeys(body.formats)) if body.formats else [None]
    campaigns = [queue_feature(db, row, requested_format=key) for row in features for key in formats]
    if all(row.status in {"completed", "skipped", "deferred", "cancelled"} for row in campaigns):
        db.rollback()
        raise HTTPException(409, "The selected content is already complete or assessed for this feature version. Open its results, choose another type, or update the brief with new evidence.")
    for campaign in campaigns:
        if campaign.status in {"partial", "failed"}:
            campaign.status = "queued"
    db.commit()
    return JSONResponse(status_code=202, content=job_out(enqueue(db, "marketing", drain_queue)))


@router.post("/campaigns/{campaign_id}/retry")
@serialized_start
def retry(campaign_id: int, db: Session = Depends(get_db)):
    busy(db)
    campaign = db.get(MarketingCampaign, campaign_id)
    if not campaign:
        raise HTTPException(404, "Campaign not found.")
    if campaign.status in {"completed", "skipped", "deferred", "cancelled"}:
        raise HTTPException(409, "This assessment is complete. Update the feature brief to request a new PMM decision.")
    campaign.status = "queued"
    feature = db.get(MarketingFeature, campaign.feature_id)
    if feature:
        feature.tag = "In pipeline"
        feature.sheet_status = "In Progress"
        feature.updated_at = datetime.utcnow()
    db.commit()
    return JSONResponse(status_code=202, content=job_out(enqueue(db, "marketing", drain_queue)))


@router.get("/campaigns/{campaign_id}/files/{filename}")
def file(campaign_id: int, filename: str, db: Session = Depends(get_db)):
    row = db.get(MarketingCampaign, campaign_id)
    asset = next((a for a in (row.assets or []) if a["filename"] == filename), None) if row else None
    folder = (CAMPAIGN_DIR / str(campaign_id)).resolve()
    path = (folder / filename).resolve()
    if not asset or path.parent != folder or not path.is_file():
        raise HTTPException(404, "Campaign file not found.")
    return FileResponse(path, media_type=asset["mime"], filename=filename,
        headers={"Content-Security-Policy": "sandbox", "X-Content-Type-Options": "nosniff"})


@router.get("/features.csv")
def export_sheet(db: Session = Depends(get_db)):
    import csv
    import io
    seed_mastersheet(db)
    out = io.StringIO()
    writer = csv.writer(out)
    fields = ["Module", "Feature", "Description", "Use Case", "Industry", "Priority", "Hook", "Start Date", "End Date", "Status", "Script", "Video", "Tag"]
    writer.writerow(fields)
    for row in db.query(MarketingFeature).order_by(MarketingFeature.id):
        values = [
            row.module, row.name, (row.summary or "").strip() or two_liner(row.hook, row.description), row.description, row.audience,
            row.priority, row.hook, row.start_date, row.end_date, row.sheet_status, row.script, row.video, row.tag,
        ]
        # Prevent formulas when the export is opened in Excel or Google Sheets.
        writer.writerow([("'" + str(v)) if str(v).lstrip().startswith(("=", "+", "-", "@")) else v for v in values])
    return Response(out.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="product-marketing-mastersheet.csv"'})

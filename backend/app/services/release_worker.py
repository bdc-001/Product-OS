"""Background worker: index → extract → draft → PDF → pending_review. Drive only on Approve."""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import ROOT
from app.database import SessionLocal
from app.models import ReleaseJob, ReleasePack
from app.services.codebase import latest_snapshot, update_index
from app.services.comms import generate_pack
from app.services.feature_extract import default_checked, extract_features, features_to_features_in_short
from app.services.gdocs import generate_doc_json, publish_doc, export_pdf
from app.services.gdrive import drive_configured, drive_status, upload_pdf
from app.services.pdf_notes import pdf_filename, write_release_pdf
from app.services.time_window import now_local, tz

log = logging.getLogger(__name__)

IN_FLIGHT = {
    "detected",
    "indexing",
    "extracting",
    "generated",
    "pdf_done",
    "doc_draft",
    "publishing",
}


def job_out(row: ReleaseJob | None) -> dict | None:
    if not row:
        return None
    extraction = row.extraction if isinstance(row.extraction, dict) else {}
    return {
        "id": row.id,
        "branch": row.branch,
        "sha": row.sha,
        "base_sha": row.base_sha,
        "merged_at": row.merged_at,
        "merged_at_label": _merged_label(row.merged_at),
        "snapshot_id": row.snapshot_id,
        "pack_id": row.pack_id,
        "pdf_path": row.pdf_path,
        "drive_file_id": row.drive_file_id,
        "drive_link": row.drive_link,
        "extraction": extraction,
        "doc": extraction.get("doc") or {},
        "features": extraction.get("features") or [],
        "internal": extraction.get("internal") or [],
        "status": row.status,
        "error_detail": row.error_detail or "",
        "triggered_by": row.triggered_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "dry_run": row.drive_file_id == "dryrun",
        "doc_ready": bool((row.drive_link or "").strip()) and (row.status or "") in {"pending_review", "uploaded", "error:publishing"},
        "artifacts": extraction.get("artifacts") or [],
        "create_artifacts": bool(extraction.get("create_artifacts")),
    }


def _merged_label(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        local = dt.astimezone(tz())
        return local.strftime("%d %b, %I:%M %p").replace(" 0", " ") + " IST"
    except ValueError:
        return text[:40]


def _touch(job: ReleaseJob, db: Session, status: str, **fields) -> None:
    job.status = status
    job.updated_at = now_local().replace(tzinfo=None)
    for key, value in fields.items():
        setattr(job, key, value)
    db.add(job)
    db.commit()
    db.refresh(job)


def _fail(job: ReleaseJob, db: Session, stage: str, exc: Exception) -> None:
    stage = (stage or job.status or "detected").split(":")[-1]
    _touch(job, db, f"error:{stage}", error_detail=str(exc)[:500])
    log.exception("release job %s failed at %s", job.id, stage)


def schedule_worker(job_id: int) -> None:
    threading.Thread(target=run_job, args=(job_id,), daemon=True, name=f"release-{job_id}").start()


def run_job(job_id: int, *, from_stage: str | None = None) -> None:
    db = SessionLocal()
    try:
        job = db.query(ReleaseJob).filter(ReleaseJob.id == job_id).one_or_none()
        if not job:
            return
        stage = from_stage or job.status or "detected"
        if stage.startswith("error:"):
            stage = stage.split(":", 1)[1] or "detected"
        if stage in {"pending_review", "uploaded", "publishing"}:
            return
        if stage in {"detected", "indexing"}:
            _stage_index(db, job)
            stage = "extracting"
        if stage == "extracting":
            _stage_extract(db, job)
            stage = "generated"
        if stage in {"generated", "pdf_done", "doc_draft"}:
            if stage in {"generated", "pdf_done"}:
                _stage_pdf(db, job)
            _stage_doc(db, job)
    except Exception as exc:
        job = db.query(ReleaseJob).filter(ReleaseJob.id == job_id).one_or_none()
        if job:
            _fail(job, db, job.status or "detected", exc)
    finally:
        db.close()


def _stage_index(db: Session, job: ReleaseJob) -> None:
    _touch(job, db, "indexing", error_detail="")
    status = update_index(db, pull=True, branch=job.branch)
    snap = latest_snapshot(db)
    if not snap:
        raise RuntimeError(status.get("error") or "Index produced no snapshot")
    _touch(job, db, "extracting", snapshot_id=snap.id)


def _stage_extract(db: Session, job: ReleaseJob) -> None:
    _touch(job, db, "extracting")
    extra = {}
    snap = latest_snapshot(db)
    if snap and job.snapshot_id and snap.id == job.snapshot_id:
        extra = {"live_summary": snap.live_summary or "", "commits": (snap.live_commits or [])[:20]}
    extraction = extract_features(job.base_sha, job.sha, extra=extra)
    checked = [
        str(item.get("name") or "").strip()
        for item in extraction.get("features") or []
        if isinstance(item, dict) and default_checked(str(item.get("confidence") or ""))
    ]
    angle = features_to_features_in_short(extraction, checked)
    if not angle:
        angle = f"Product release {(job.branch or '').split('/')[-1]}. Cover what shipped versus main."
    pack = generate_pack(
        db,
        title=f"Product release {(job.branch or '').split('/')[-1]}",
        angle=angle,
        kind="release_notes",
        snapshot_id=job.snapshot_id or None,
    )
    doc = generate_doc_json(
        title=pack.get("title") or "",
        features_in_short=angle,
        branch=job.branch,
        notes=pack.get("release_notes") or "",
    )
    extraction = {**(extraction if isinstance(extraction, dict) else {}), "doc": doc}
    _touch(job, db, "generated", extraction=extraction, pack_id=pack.get("id") or 0)


def _stage_pdf(db: Session, job: ReleaseJob) -> None:
    _touch(job, db, "pdf_done")
    pack_row = db.query(ReleasePack).filter(ReleasePack.id == job.pack_id).one_or_none() if job.pack_id else None
    title = (pack_row.title if pack_row else "") or f"Product release {(job.branch or '').split('/')[-1]}"
    notes = (pack_row.release_notes if pack_row else "") or ""
    day = (job.branch or "").split("/")[-1]
    dest = ROOT / "data" / "release_notes" / pdf_filename(job.branch, title)
    try:
        date_str = datetime.strptime(day, "%Y-%m-%d").strftime("%d %b %Y")
    except ValueError:
        date_str = now_local().strftime("%d %b %Y")
    path = write_release_pdf(
        title=title,
        branch=job.branch,
        sha=(job.sha or "")[:12],
        body=notes,
        dest=dest,
        date_str=date_str,
        audience="Clients",
        version=day,
    )
    _touch(job, db, "pdf_done", pdf_path=str(path), error_detail="")


def _stage_doc(db: Session, job: ReleaseJob) -> None:
    _touch(job, db, "doc_draft")
    extraction = job.extraction if isinstance(job.extraction, dict) else {}
    doc = extraction.get("doc") if isinstance(extraction.get("doc"), dict) else {}
    if not (doc.get("title") or doc.get("highlights")):
        pack_row = db.query(ReleasePack).filter(ReleasePack.id == job.pack_id).one_or_none() if job.pack_id else None
        doc = generate_doc_json(
            title=(pack_row.title if pack_row else "") or f"Product release {(job.branch or '').split('/')[-1]}",
            features_in_short=(pack_row.angle if pack_row else "") or "",
            branch=job.branch,
            notes=(pack_row.release_notes if pack_row else "") or "",
        )
        extraction = {**extraction, "doc": doc}
        job.extraction = extraction
        db.commit()
    if drive_configured():
        doc_id, url = publish_doc(job, doc)
        artifacts = list(extraction.get("artifacts") or [])
        if extraction.get("create_artifacts") and not artifacts:
            from app.services.feature_artifacts import publish_feature_artifacts

            pack_row = db.query(ReleasePack).filter(ReleasePack.id == job.pack_id).one_or_none() if job.pack_id else None
            artifacts = publish_feature_artifacts(
                features_in_short=(pack_row.angle if pack_row else "") or "",
                branch=job.branch,
                notes=(pack_row.release_notes if pack_row else "") or "",
                doc=doc,
            )
        extraction = {**extraction, "artifacts": artifacts}
        _touch(job, db, "pending_review", drive_file_id=doc_id, drive_link=url, extraction=extraction, error_detail="")
        return
    _touch(job, db, "pending_review", error_detail="")


def regenerate(db: Session, job: ReleaseJob, checked: list[str] | None = None, features_in_short: str = "", create_artifacts: bool = False) -> dict:
    extraction = job.extraction if isinstance(job.extraction, dict) else {}
    if checked is not None:
        angle = features_to_features_in_short(extraction, checked)
    elif (features_in_short or "").strip():
        angle = features_in_short.strip()
    else:
        names = [
            str(item.get("name") or "").strip()
            for item in extraction.get("features") or []
            if isinstance(item, dict) and default_checked(str(item.get("confidence") or ""))
        ]
        angle = features_to_features_in_short(extraction, names)
    if not angle:
        raise RuntimeError("Select at least one feature to regenerate.")
    if job.status.startswith("error:"):
        job.status = "generated"
    pack = generate_pack(
        db,
        title=f"Product release {(job.branch or '').split('/')[-1]}",
        angle=angle,
        kind="release_notes",
        snapshot_id=job.snapshot_id or None,
        create_artifacts=create_artifacts,
    )
    doc = generate_doc_json(
        title=pack.get("title") or "",
        features_in_short=angle,
        branch=job.branch,
        notes=pack.get("release_notes") or "",
    )
    job.pack_id = pack.get("id") or 0
    job.extraction = {**extraction, "doc": doc, "create_artifacts": create_artifacts, "artifacts": pack.get("artifacts") or []}
    db.commit()
    db.refresh(job)
    _stage_pdf(db, job)
    _stage_doc(db, job)
    return job_out(job) or {}


def approve_and_publish(db: Session, job: ReleaseJob) -> dict:
    if job.status not in {"pending_review", "error:publishing"}:
        raise RuntimeError(f"Job is {job.status}, not pending_review")
    _touch(job, db, "publishing", error_detail="")
    pack_row = db.query(ReleasePack).filter(ReleasePack.id == job.pack_id).one_or_none() if job.pack_id else None
    title = (pack_row.title if pack_row else "") or "Release notes"
    filename = pdf_filename(job.branch, title)
    dest = ROOT / "data" / "release_notes" / filename
    doc_id = (job.drive_file_id or "").strip()
    doc_link = (job.drive_link or "").strip()
    try:
        if doc_id and doc_id != "dryrun" and drive_configured():
            export_pdf(doc_id, dest)
            upload_pdf(dest, job.branch, filename=filename)
            _touch(job, db, "uploaded", pdf_path=str(dest), drive_file_id=doc_id, drive_link=doc_link, error_detail="")
            return job_out(job) or {}
        if not (job.pdf_path or "").strip() or not Path(job.pdf_path).is_file():
            raise RuntimeError("No Google Doc or local PDF to publish. Regenerate the draft first.")
        result = upload_pdf(Path(job.pdf_path), job.branch, filename=filename)
        _touch(
            job,
            db,
            "uploaded",
            drive_file_id=result.get("file_id") or doc_id or "",
            drive_link=result.get("link") or doc_link or "",
            error_detail="dry-run: Drive not configured; PDF kept locally" if result.get("dry_run") else "",
        )
    except Exception as exc:
        _fail(job, db, "publishing", exc)
        raise
    return job_out(job) or {}


def recent_jobs(db: Session, limit: int = 30) -> list[dict]:
    rows = db.query(ReleaseJob).order_by(ReleaseJob.id.desc()).limit(limit).all()
    return [job_out(row) for row in rows if row]


def pending_jobs(db: Session) -> list[dict]:
    return [
        row
        for row in recent_jobs(db)
        if (row or {}).get("status") in {"pending_review", "error:publishing"}
    ]


def catchup_stuck_jobs() -> int:
    db = SessionLocal()
    n = 0
    try:
        rows = db.query(ReleaseJob).filter(ReleaseJob.status.in_(tuple(IN_FLIGHT))).all()
        for job in rows:
            if job.status == "publishing":
                _touch(job, db, "error:publishing", error_detail=job.error_detail or "Interrupted while publishing. Retry Approve.")
                continue
            if job.status == "pdf_done":
                n += 1
                schedule_worker(job.id)
                continue
            if job.status == "generated" and job.pack_id:
                n += 1
                schedule_worker(job.id)
                continue
            n += 1
            schedule_worker(job.id)
        return n
    except Exception:
        db.rollback()
        log.exception("release job catch-up failed")
        return n
    finally:
        db.close()


def detect_and_enqueue(db: Session, triggered_by: str = "auto") -> list[dict]:
    from app.services.release_detect import enqueue_detected, new_release_merges

    fresh = new_release_merges(db)
    jobs = enqueue_detected(db, fresh, triggered_by=triggered_by)
    for job in jobs:
        schedule_worker(job.id)
    return [job_out(job) for job in jobs]


def comms_release_payload(db: Session) -> dict:
    jobs = recent_jobs(db)
    return {
        "release_jobs": jobs,
        "pending_releases": [row for row in jobs if (row or {}).get("status") in {"pending_review", "error:publishing"}],
        "drive": drive_status(),
        "drive_configured": drive_configured(),
    }

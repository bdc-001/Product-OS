"""Background worker: index → extract → capture → write one note per feature → PDF → draft Docs → pending_review.

Each checked feature gets its own release note, a copy of the release-note template doc
(see release_note.py). Approve exports every note Doc to PDF and files it in Drive.
"""

from __future__ import annotations

import logging
from app.context import ContextThreadPoolExecutor as ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import ReleaseJob, ReleasePack
from app.services.codebase import latest_snapshot, update_index
from app.services.comms import generate_pack
from app.services.feature_extract import default_checked, extract_features, features_to_features_in_short
from app.services.gdocs import export_pdf, trash_file, upload_screenshot
from app.services.gdrive import drive_configured, drive_status, upload_pdf
from app.services.pdf_notes import pdf_filename, write_release_pdf
from app.services.release_note import (
    ASSETS_ROOT,
    clean_note,
    feature_evidence,
    generate_note,
    prepare_images,
    publish_note,
    slug,
    verify_note,
    write_note_pdf,
)
from app.services.release_shots import capture_release_shots, good_shots
from app.services.time_window import now_local, tz
from app.storage import from_stored, to_stored, workspace_path

log = logging.getLogger(__name__)

NOTE_WRITERS = 3

IN_FLIGHT = {
    "detected",
    "indexing",
    "extracting",
    "capturing",
    "writing",
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
        "notes": [_note_out(row.id, index, note) for index, note in enumerate(_notes(extraction))],
        **_shots_out(row.id, extraction),
    }


def _notes(extraction: dict) -> list[dict]:
    return [note for note in extraction.get("notes") or [] if isinstance(note, dict) and isinstance(note.get("content"), dict)]


def _note_out(job_id: int, index: int, note: dict) -> dict:
    content = note["content"]
    pdf = (note.get("pdf_path") or "").strip()
    return {
        "index": index,
        "feature": note.get("feature") or content.get("feature") or "",
        "title": content.get("title") or "",
        "dek": content.get("dek") or "",
        "sections": [section.get("heading") or "" for section in content.get("sections") or []],
        "status": note.get("status") or "ok",
        "error": note.get("error") or "",
        "warnings": note.get("warnings") or [],
        "images": len(note.get("images") or []),
        "doc_id": note.get("doc_id") or "",
        "url": note.get("url") or "",
        "pdf_url": f"/api/comms/release-jobs/{job_id}/pdf?note={index}" if pdf and from_stored(pdf).is_file() else "",
    }


def _shots_out(job_id: int, extraction: dict) -> dict:
    capture = extraction.get("shots") if isinstance(extraction.get("shots"), dict) else {}
    placed = _doc_refs(extraction)
    shots = []
    for item in capture.get("shots") or []:
        if not isinstance(item, dict):
            continue
        ok = item.get("status") == "ok" and bool(item.get("path"))
        shots.append(
            {
                **{k: item.get(k) or "" for k in ("id", "feature", "section", "caption", "module", "error")},
                "status": item.get("status") or "failed",
                "in_doc": item.get("id") in placed,
                "repaired": bool(item.get("repaired")),
                "width": item.get("width") or 0,
                "height": item.get("height") or 0,
                "url": f"/api/comms/release-jobs/{job_id}/shots/{item.get('id')}" if ok else "",
            }
        )
    return {"shots": shots, "shots_status": capture.get("status") or "", "shots_reason": capture.get("reason") or ""}


def _doc_refs(extraction: dict) -> set[str]:
    refs = set()
    for note in _notes(extraction):
        for section in note["content"].get("sections") or []:
            shot = section.get("screenshot") if isinstance(section, dict) else None
            if isinstance(shot, dict) and shot.get("id"):
                refs.add(str(shot["id"]))
    return refs


def _selected(extraction: dict, names: list[str] | None = None) -> list[dict]:
    features = [item for item in extraction.get("features") or [] if isinstance(item, dict) and item.get("name")]
    if names is None:
        return [item for item in features if default_checked(str(item.get("confidence") or ""))]
    wanted = {name.strip() for name in names if name and name.strip()}
    return [item for item in features if item["name"] in wanted]


def _checked(extraction: dict) -> list[str] | None:
    checked = extraction.get("checked")
    return [str(name) for name in checked] if isinstance(checked, list) else None


def _write_one(base_sha: str, head_sha: str, feature: dict, capture: dict, prior: dict) -> dict:
    name = feature["name"]
    shots = good_shots(capture, [name])
    try:
        evidence = feature_evidence(base_sha, head_sha, feature)
    except Exception:
        log.exception("could not gather evidence for %s", name)
        evidence = {"commits": [], "files": []}
    content, error = generate_note(feature, evidence, shots)
    return {
        "feature": name,
        "content": content,
        "status": "fallback" if error else "ok",
        "error": error,
        "doc_id": prior.get("doc_id") or "",
        "url": prior.get("url") or "",
        "images": prior.get("images") or [],
        "pdf_path": "",
    }


def _build_notes(job: ReleaseJob, features: list[dict], capture: dict | None, previous: list[dict] | None) -> list[dict]:
    """Write one note per feature, reusing each feature's existing draft Doc."""
    old = {note.get("feature"): note for note in previous or [] if isinstance(note, dict)}
    if not features:
        return []
    base, head = job.base_sha or "", job.sha or ""
    with ThreadPoolExecutor(max_workers=min(NOTE_WRITERS, len(features)), thread_name_prefix=f"note-{job.id}") as pool:
        futures = [pool.submit(_write_one, base, head, feature, capture or {}, old.get(feature["name"]) or {}) for feature in features]
        return [future.result() for future in futures]


def _trash_dropped(previous: list[dict] | None, notes: list[dict]) -> None:
    keep = {note["feature"] for note in notes}
    for note in previous or []:
        doc_id = (note or {}).get("doc_id") or ""
        if doc_id and doc_id != "dryrun" and note.get("feature") not in keep:
            trash_file(doc_id)


def _capture(job: ReleaseJob, features: list[dict]) -> dict:
    if not features:
        return {"status": "skipped", "reason": "No feature selected.", "shots": []}
    return capture_release_shots(job_id=job.id, base_sha=job.base_sha, head_sha=job.sha, features=features)


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


def schedule_worker(job_id: int, from_stage: str | None = None) -> None:
    from app.services.jobs import enqueue

    db = SessionLocal()
    try:
        enqueue(db, f"release-job-{job_id}", task="release-job", params={"job_id": job_id, "from_stage": from_stage or ""}, pipeline_id="release-notes", trigger="release")
    finally:
        db.close()


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
        if stage in {"extracting", "capturing"}:
            _stage_extract(db, job)
            stage = "writing"
        if stage == "writing":
            _stage_write(db, job)
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
    extraction = extraction if isinstance(extraction, dict) else {}
    selected = _selected(extraction)
    extraction["checked"] = [item["name"] for item in selected]
    _touch(job, db, "capturing", extraction=extraction)
    capture = _capture(job, selected)
    _touch(job, db, "writing", extraction={**extraction, "shots": capture})


def _stage_write(db: Session, job: ReleaseJob) -> None:
    """Refresh the Comms pack, then write one release note per checked feature."""
    _touch(job, db, "writing")
    extraction = job.extraction if isinstance(job.extraction, dict) else {}
    names = _checked(extraction)
    selected = _selected(extraction, names)
    angle = (extraction.get("angle") or "").strip() or features_to_features_in_short(extraction, [item["name"] for item in selected])
    if not angle:
        angle = f"Product release {(job.branch or '').split('/')[-1]}. Cover what shipped versus main."
    pack = generate_pack(
        db,
        title=f"Product release {(job.branch or '').split('/')[-1]}",
        angle=angle,
        kind="release_notes",
        snapshot_id=job.snapshot_id or None,
        create_artifacts=bool(extraction.get("create_artifacts")),
    )
    previous = _notes(extraction)
    notes = _build_notes(job, selected, extraction.get("shots"), previous)
    _trash_dropped(previous, notes)
    extraction = {**extraction, "notes": notes}
    if extraction.get("create_artifacts") and pack.get("artifacts"):
        extraction["artifacts"] = pack["artifacts"]
    _touch(job, db, "generated", extraction=extraction, pack_id=pack.get("id") or 0)


def _date_str(branch: str) -> str:
    day = (branch or "").split("/")[-1]
    try:
        return datetime.strptime(day, "%Y-%m-%d").strftime("%d %b %Y")
    except ValueError:
        return now_local().strftime("%d %b %Y")


def _note_pdf_path(job: ReleaseJob, feature: str) -> Path:
    return workspace_path("release_notes") / f"job-{job.id}" / pdf_filename(job.branch, feature)


def _stage_pdf(db: Session, job: ReleaseJob) -> None:
    """Frame shots, render diagrams and write a local preview PDF for every note."""
    _touch(job, db, "pdf_done")
    extraction = job.extraction if isinstance(job.extraction, dict) else {}
    day = (job.branch or "").split("/")[-1]
    notes = []
    for note in _notes(extraction):
        feature = note["feature"]
        content = dict(note["content"])
        folder = ASSETS_ROOT / f"job-{job.id}" / slug(feature)
        images = prepare_images(content, good_shots(extraction.get("shots"), [feature]), folder, note.get("images"))
        dest = _note_pdf_path(job, feature)
        write_note_pdf(content, images, dest, branch=job.branch, sha=(job.sha or "")[:12], date_str=_date_str(job.branch), version=day)
        notes.append({**note, "content": content, "images": images, "pdf_path": to_stored(dest)})
    if notes:
        _touch(job, db, "pdf_done", extraction={**extraction, "notes": notes}, pdf_path=notes[0]["pdf_path"], error_detail="")
        return
    pack_row = db.query(ReleasePack).filter(ReleasePack.id == job.pack_id).one_or_none() if job.pack_id else None
    title = (pack_row.title if pack_row else "") or f"Product release {day}"
    path = write_release_pdf(
        title=title,
        branch=job.branch,
        sha=(job.sha or "")[:12],
        body=(pack_row.release_notes if pack_row else "") or "",
        dest=workspace_path("release_notes") / pdf_filename(job.branch, title),
        date_str=_date_str(job.branch),
        audience="Clients",
        version=day,
    )
    _touch(job, db, "pdf_done", pdf_path=to_stored(path), error_detail="")


def _upload_images(branch: str, images: list[dict]) -> list[dict]:
    """Upload framed shots and diagrams once per file hash; Docs inserts them by URI."""
    out = []
    for item in images:
        if not item.get("uri") or item.get("drive_sha") != item.get("sha"):
            file_id, uri = upload_screenshot(from_stored(item["path"]), branch)
            item = {**item, "drive_file_id": file_id, "uri": uri, "drive_sha": item.get("sha")}
        out.append(item)
    return out


def _stage_doc(db: Session, job: ReleaseJob) -> None:
    _touch(job, db, "doc_draft")
    extraction = job.extraction if isinstance(job.extraction, dict) else {}
    if not drive_configured():
        _touch(job, db, "pending_review", error_detail="")
        return
    notes = []
    for note in _notes(extraction):
        images = _upload_images(job.branch, note.get("images") or [])
        doc_id, url = publish_note(note["content"], images, note.get("doc_id") or "")
        try:
            warnings = verify_note(doc_id, note["content"], len(images))
        except Exception as exc:
            log.exception("could not verify release note %s", doc_id)
            warnings = [f"Could not verify the Doc export: {exc}"[:200]]
        notes.append({**note, "images": images, "doc_id": doc_id, "url": url, "warnings": warnings})
        extraction = {**extraction, "notes": notes + _notes(extraction)[len(notes):]}
        _touch(job, db, "doc_draft", extraction=extraction)
    artifacts = list(extraction.get("artifacts") or [])
    if extraction.get("create_artifacts") and not artifacts:
        from app.services.feature_artifacts import publish_feature_artifacts

        pack_row = db.query(ReleasePack).filter(ReleasePack.id == job.pack_id).one_or_none() if job.pack_id else None
        artifacts = publish_feature_artifacts(
            features_in_short=(pack_row.angle if pack_row else "") or "",
            branch=job.branch,
            notes=(pack_row.release_notes if pack_row else "") or "",
        )
    first = notes[0] if notes else {}
    _touch(
        job,
        db,
        "pending_review",
        drive_file_id=first.get("doc_id") or "",
        drive_link=first.get("url") or "",
        extraction={**extraction, "artifacts": artifacts},
        error_detail="",
    )


def regenerate(db: Session, job: ReleaseJob, checked: list[str] | None = None, features_in_short: str = "", create_artifacts: bool = False) -> dict:
    """Rewrite the notes for the checked features in the background; drafts keep their Doc links."""
    if job.status in IN_FLIGHT:
        raise RuntimeError(f"Job is {job.status}; wait for it to finish before regenerating.")
    extraction = job.extraction if isinstance(job.extraction, dict) else {}
    names = list(checked) if checked is not None else None
    angle = "" if checked is not None else (features_in_short or "").strip()
    if not _selected(extraction, names) and not angle:
        raise RuntimeError("Select at least one feature to regenerate.")
    extraction = {
        **extraction,
        "checked": [item["name"] for item in _selected(extraction, names)],
        "angle": angle,
        "create_artifacts": create_artifacts,
        "artifacts": [],
    }
    _touch(job, db, "writing", extraction=extraction, error_detail="")
    schedule_worker(job.id, from_stage="writing")
    return job_out(job) or {}


RECAPTURE_FROM = {"pending_review", "generated", "error:capturing", "error:writing", "error:pdf_done", "error:doc_draft", "error:publishing"}


def start_recapture(db: Session, job: ReleaseJob, checked: list[str] | None = None) -> dict:
    if job.status not in RECAPTURE_FROM:
        raise RuntimeError(f"Job is {job.status}; wait for the draft before recapturing screenshots.")
    _touch(job, db, "capturing", error_detail="")
    from app.services.jobs import enqueue

    enqueue(db, f"release-shots-{job.id}", task="release-shots", params={"job_id": job.id, "checked": checked}, pipeline_id="release-notes", trigger="release")
    return job_out(job) or {}


def recapture_shots(job_id: int, checked: list[str] | None = None) -> None:
    """Re-render screenshots from the current code and re-place them in the existing draft copy."""
    db = SessionLocal()
    try:
        job = db.query(ReleaseJob).filter(ReleaseJob.id == job_id).one_or_none()
        if not job:
            return
        extraction = job.extraction if isinstance(job.extraction, dict) else {}
        selected = _selected(extraction, checked if checked is not None else _checked(extraction))
        capture = _capture(job, selected)
        extraction = {**extraction, "shots": capture}
        notes = _notes(extraction)
        if not notes:
            _touch(job, db, "writing", extraction={**extraction, "checked": [item["name"] for item in selected]})
            run_job(job.id, from_stage="writing")
            return
        by_name = {item["name"]: item for item in selected}
        for note in notes:
            feature = by_name.get(note["feature"]) or {"name": note["feature"]}
            shots = good_shots(capture, [note["feature"]])
            unplaced = {**note["content"], "sections": [
                {k: v for k, v in section.items() if k != "screenshot" or v.get("id") in {s.get("id") for s in shots}}
                for section in note["content"].get("sections") or []
            ]}
            note["content"] = clean_note(unplaced, feature, shots)
        _touch(job, db, "generated", extraction={**extraction, "notes": notes})
        _stage_pdf(db, job)
        _stage_doc(db, job)
    except Exception as exc:
        job = db.query(ReleaseJob).filter(ReleaseJob.id == job_id).one_or_none()
        if job:
            _fail(job, db, "capturing", exc)
    finally:
        db.close()


def approve_and_publish(db: Session, job: ReleaseJob) -> dict:
    if job.status not in {"pending_review", "error:publishing"}:
        raise RuntimeError(f"Job is {job.status}, not pending_review")
    _touch(job, db, "publishing", error_detail="")
    extraction = job.extraction if isinstance(job.extraction, dict) else {}
    notes = _notes(extraction)
    if notes:
        try:
            return _publish_notes(db, job, extraction, notes)
        except Exception as exc:
            _fail(job, db, "publishing", exc)
            raise
    pack_row = db.query(ReleasePack).filter(ReleasePack.id == job.pack_id).one_or_none() if job.pack_id else None
    title = (pack_row.title if pack_row else "") or "Release notes"
    filename = pdf_filename(job.branch, title)
    dest = workspace_path("release_notes") / filename
    doc_id = (job.drive_file_id or "").strip()
    doc_link = (job.drive_link or "").strip()
    try:
        if doc_id and doc_id != "dryrun" and drive_configured():
            export_pdf(doc_id, dest)
            upload_pdf(dest, job.branch, filename=filename)
            _touch(job, db, "uploaded", pdf_path=to_stored(dest), drive_file_id=doc_id, drive_link=doc_link, error_detail="")
            return job_out(job) or {}
        local_pdf = from_stored(job.pdf_path)
        if not local_pdf or not local_pdf.is_file():
            raise RuntimeError("No Google Doc or local PDF to publish. Regenerate the draft first.")
        result = upload_pdf(local_pdf, job.branch, filename=filename)
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


def _publish_notes(db: Session, job: ReleaseJob, extraction: dict, notes: list[dict]) -> dict:
    """Export each note Doc to PDF and file it in Drive; without Drive, file the local previews."""
    published = []
    dry_run = False
    for note in notes:
        filename = pdf_filename(job.branch, note["feature"])
        doc_id = (note.get("doc_id") or "").strip()
        if doc_id and doc_id != "dryrun" and drive_configured():
            dest = workspace_path("release_notes") / filename
            export_pdf(doc_id, dest)
            upload_pdf(dest, job.branch, filename=filename)
            published.append({**note, "pdf_path": to_stored(dest)})
            continue
        local = from_stored(note.get("pdf_path")) or Path("")
        if not local.is_file():
            raise RuntimeError(f"No Google Doc or local PDF for {note['feature']}. Regenerate the draft first.")
        result = upload_pdf(local, job.branch, filename=filename)
        dry_run = dry_run or bool(result.get("dry_run"))
        published.append({**note, "doc_id": doc_id or result.get("file_id") or "", "url": note.get("url") or result.get("link") or ""})
    first = published[0]
    _touch(
        job,
        db,
        "uploaded",
        extraction={**extraction, "notes": published},
        pdf_path=first.get("pdf_path") or job.pdf_path,
        drive_file_id=first.get("doc_id") or "",
        drive_link=first.get("url") or "",
        error_detail="dry-run: Drive not configured; PDF kept locally" if dry_run else "",
    )
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

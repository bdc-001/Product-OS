import logging
import re
import threading
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.common import CommsBody, ReleaseRegenBody
from app.config import settings
from app.database import SessionLocal, get_db
from app.models import ReleaseJob
from app.services.codebase import snapshot_out
from app.services.comms import generate_pack, get_pack, list_packs
from app.services.pdf_notes import PDF_DIR, write_release_pdf
from app.services.release_notes_job import run_daily_release_notes, schedule_meta
from app.services.release_worker import approve_and_publish, comms_release_payload, job_out, regenerate, schedule_worker

router = APIRouter()
log = logging.getLogger(__name__)


@router.get("/comms")
def comms_list(db: Session = Depends(get_db)):
    return {"packs": list_packs(db), "codebase": snapshot_out(db), **schedule_meta(db), **comms_release_payload(db)}


@router.get("/comms/release-jobs/{job_id}/pdf")
def comms_release_pdf(job_id: int, db: Session = Depends(get_db)):
    job = db.query(ReleaseJob).filter(ReleaseJob.id == job_id).one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Release job not found")
    path = Path(job.pdf_path) if job.pdf_path else None
    if not path or not path.is_file():
        raise HTTPException(status_code=404, detail="PDF not ready")
    return FileResponse(path, media_type="application/pdf", filename=path.name)


@router.post("/comms/release-jobs/{job_id}/regenerate")
def comms_release_regen(job_id: int, body: ReleaseRegenBody, db: Session = Depends(get_db)):
    job = db.query(ReleaseJob).filter(ReleaseJob.id == job_id).one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Release job not found")
    try:
        return regenerate(db, job, checked=body.checked, features_in_short=body.features_in_short, create_artifacts=bool(body.artifacts))
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/comms/release-jobs/{job_id}/approve")
def comms_release_approve(job_id: int, db: Session = Depends(get_db)):
    job = db.query(ReleaseJob).filter(ReleaseJob.id == job_id).one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Release job not found")
    if job.status not in {"pending_review", "error:publishing"}:
        raise HTTPException(status_code=409, detail=f"Job is {job.status}, not pending_review")
    try:
        return approve_and_publish(db, job)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)[:500]) from exc


@router.post("/comms/release-jobs/{job_id}/retry")
def comms_release_retry(job_id: int, db: Session = Depends(get_db)):
    job = db.query(ReleaseJob).filter(ReleaseJob.id == job_id).one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Release job not found")
    schedule_worker(job.id)
    return job_out(job)


@router.get("/comms/{pack_id}")
def comms_detail(pack_id: int, db: Session = Depends(get_db)):
    row = get_pack(db, pack_id)
    if not row:
        raise HTTPException(status_code=404, detail="Release pack not found")
    return row


@router.get("/comms/{pack_id}/pdf")
def comms_pdf(pack_id: int, db: Session = Depends(get_db)):
    pack = get_pack(db, pack_id)
    if not pack:
        raise HTTPException(status_code=404, detail="Release pack not found")
    kind = pack.get("kind") or "release_notes"
    if kind == "whatsapp":
        body = pack.get("whatsapp") or pack.get("internal_update") or ""
    elif kind == "newsletter":
        body = pack.get("newsletter_markdown") or ""
    else:
        body = pack.get("release_notes") or ""
    dest = PDF_DIR / f"pack-{pack_id}.pdf"
    write_release_pdf(
        title=pack.get("title") or "Release notes",
        branch=pack.get("branch") or "",
        sha=pack.get("commit_sha") or "",
        body=body,
        dest=dest,
    )
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", pack.get("title") or "release-notes").strip("-")[:80] or "release-notes"
    return FileResponse(dest, media_type="application/pdf", filename=f"{safe}.pdf")


@router.post("/comms/generate")
def comms_generate(body: CommsBody, db: Session = Depends(get_db)):
    try:
        return generate_pack(
            db,
            title=(body.title or "").strip(),
            angle=(body.angle or "").strip(),
            kind=(body.kind or "release_notes").strip(),
            create_artifacts=bool(body.artifacts),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.api_route("/comms/release-notes/run", methods=["GET", "POST"])
def comms_release_run(
    force: bool = False,
    wait: bool = True,
    token: str = "",
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    expected = (settings.release_notes_cron_token or "").strip()
    provided = (token or "").strip()
    if authorization and authorization.lower().startswith("bearer "):
        provided = authorization.split(" ", 1)[1].strip()
    if not wait:
        if expected and provided != expected:
            raise HTTPException(status_code=401, detail="Bad cron token")

        def work() -> None:
            session = SessionLocal()
            try:
                run_daily_release_notes(session, force=force)
            except Exception:
                log.exception("background release notes failed")
            finally:
                session.close()

        threading.Thread(target=work, daemon=True).start()
        return {"ok": True, "started": True}
    try:
        return run_daily_release_notes(db, force=force)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

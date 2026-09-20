from __future__ import annotations

import logging
import re
import smtplib
from email.message import EmailMessage
from datetime import timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.models import ReleaseNotesJob, ReleasePack
from app.services.codebase import list_recent_branches, snapshot_out, update_index
from app.services.comms import generate_pack, pack_out
from app.services.pdf_notes import write_release_pdf
from app.services.time_window import now_local

log = logging.getLogger(__name__)

RELEASE_NAME = re.compile(r"^release/\d{4}-\d{2}-\d{2}$", re.I)


def smtp_ready() -> bool:
    return bool((settings.smtp_host or "").strip() and (settings.smtp_user or "").strip() and (settings.smtp_password or "").strip())


def job_out(row: ReleaseNotesJob | None) -> dict | None:
    if not row:
        return None
    return {
        "id": row.id,
        "branch": row.branch,
        "commit_sha": row.commit_sha,
        "pack_id": row.pack_id,
        "pdf_path": row.pdf_path,
        "emailed_to": row.emailed_to,
        "status": row.status,
        "error": row.error,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def latest_job(db: Session) -> ReleaseNotesJob | None:
    return db.query(ReleaseNotesJob).order_by(ReleaseNotesJob.id.desc()).first()


def schedule_meta(db: Session) -> dict:
    return {
        "release_hour": settings.release_notes_hour,
        "release_email": settings.release_notes_email or "arsalaan@convin.ai",
        "smtp_ready": smtp_ready(),
        "release_job": job_out(latest_job(db)),
    }


def send_pdf_email(*, to: str, subject: str, body: str, pdf_path: Path) -> None:
    sender = (settings.smtp_from or settings.smtp_user or to).strip()
    message = EmailMessage()
    message["From"] = sender
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    message.add_attachment(
        pdf_path.read_bytes(),
        maintype="application",
        subtype="pdf",
        filename=pdf_path.name,
    )
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(message)


def _merged_releases(fetch: bool, *, fresh_days: int | None = None) -> tuple[list[dict], str]:
    listed = list_recent_branches(fetch=fetch, limit=80)
    error = (listed.get("error") or "").strip()
    cutoff = None
    if fresh_days and fresh_days > 0:
        cutoff = (now_local().date() - timedelta(days=fresh_days)).isoformat()
    rows = []
    for row in listed.get("branches") or []:
        name = (row.get("name") or "").strip()
        if not RELEASE_NAME.match(name) or not row.get("merged"):
            continue
        day = (row.get("day") or "")[:10]
        if cutoff and day and day < cutoff:
            continue
        rows.append(row)
    return rows, error


def _already_sent(db: Session, sha: str) -> ReleaseNotesJob | None:
    if not sha:
        return None
    return (
        db.query(ReleaseNotesJob)
        .filter(ReleaseNotesJob.commit_sha == sha, ReleaseNotesJob.status.in_(("sent", "saved")))
        .order_by(ReleaseNotesJob.id.desc())
        .first()
    )


def _record(db: Session, **fields) -> ReleaseNotesJob:
    row = ReleaseNotesJob(created_at=now_local().replace(tzinfo=None), **fields)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def run_daily_release_notes(db: Session, *, force: bool = False) -> dict:
    to = (settings.release_notes_email or "arsalaan@convin.ai").strip()
    fresh = None if force else settings.release_notes_fresh_days
    releases, list_error = _merged_releases(fetch=True, fresh_days=fresh)
    if not releases:
        row = _record(
            db,
            branch="",
            commit_sha="",
            status="skipped",
            error=list_error or "No merged release/YYYY-MM-DD branch in the last few days.",
        )
        return {"job": job_out(row), "pack": None, "status": snapshot_out(db)}

    newest = releases[0]
    name = newest["name"]
    sha = (newest.get("sha") or "")[:12]
    existing = _already_sent(db, sha)
    if existing and not force:
        pack_row = db.query(ReleasePack).filter(ReleasePack.id == existing.pack_id).one_or_none() if existing.pack_id else None
        return {"job": job_out(existing), "pack": pack_out(pack_row) if pack_row else None, "status": snapshot_out(db)}

    date = name.split("/", 1)[-1]
    title = f"Product release {date}"
    try:
        indexed = update_index(db, branch=name)
        pack = generate_pack(db, title=title, angle="Product release for CSMs and training. Cover what shipped versus main.", kind="release_notes")
        notes = pack.get("release_notes") or ""
        pdf_path = write_release_pdf(title=pack.get("title") or title, branch=pack.get("branch") or name, sha=pack.get("commit_sha") or sha, body=notes)
        mailed = ""
        status = "saved"
        error = ""
        if smtp_ready():
            send_pdf_email(
                to=to,
                subject=f"Product release notes · {name}",
                body=f"Attached: product release notes for {name} ({pack.get('commit_sha') or sha}).\n\nGenerated by PM Platform.",
                pdf_path=pdf_path,
            )
            mailed = to
            status = "sent"
        else:
            error = f"PDF saved at {pdf_path}. Set SMTP_USER and SMTP_PASSWORD in .env to email {to}."
        row = _record(
            db,
            branch=pack.get("branch") or name,
            commit_sha=pack.get("commit_sha") or sha,
            pack_id=pack.get("id") or 0,
            pdf_path=str(pdf_path),
            emailed_to=mailed,
            status=status,
            error=error,
        )
        return {"job": job_out(row), "pack": pack, "status": indexed}
    except Exception as exc:
        log.exception("daily release notes failed for %s", name)
        row = _record(db, branch=name, commit_sha=sha, status="error", error=str(exc)[:800])
        return {"job": job_out(row), "pack": None, "status": snapshot_out(db)}

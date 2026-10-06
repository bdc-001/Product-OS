from datetime import datetime
import logging
import time

from sqlalchemy.orm import Session

from app.clients.cliq import CliqClient
from app.config import settings
from app.models import PipelineRun, Standup
from app.services.evaluate import evaluate_standup
from app.models import CliqMessage, JiraIssue
from app.services.filter import classify_message
from app.services.ingest import ingest_cliq, ingest_jira
from app.services.intelligence import build_insights, correlate, detect_changes
from app.services.standup import generate_standup
from app.services.time_window import briefing_window

log = logging.getLogger(__name__)


def run_pipeline(db: Session, trigger: str = "manual", ingest: bool = True) -> PipelineRun:
    existing = (
        db.query(PipelineRun)
        .filter(PipelineRun.status == "running")
        .order_by(PipelineRun.id.desc())
        .first()
    )
    if existing and existing.started_at and (datetime.utcnow() - existing.started_at).total_seconds() < 180:
        return _wait_for_run(db, existing.id)
    if existing:
        existing.status = "failed"
        existing.error = existing.error or "stale run"
        existing.finished_at = datetime.utcnow()
        db.commit()

    window = briefing_window()
    window_start, window_end = window.as_naive()
    run = PipelineRun(
        status="running",
        trigger=trigger,
        window_start=window_start,
        window_end=window_end,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    try:
        cliq_error = ""
        if ingest:
            jira_count = ingest_jira(db, window_start)
            db.commit()
            cliq_count, relevant_count, cliq_error = ingest_cliq(db, window_start, window_end)
            db.commit()
        else:
            from app.repositories.issues import list_active

            jira_count = len(list_active(db))
            cliq_count = db.query(CliqMessage).count()
            relevant_count = 0
        relevant_count = refresh_message_metadata(db)
        db.commit()
        change_count = detect_changes(db, window_start, window_end)
        db.commit()
        correlate(db, window_start, window_end)
        db.commit()
        insights = build_insights(db, run.id, window_start, window_end)
        db.commit()
        standup = generate_standup(db, run.id, window_start, window_end, insights, period=window.period, headline=window.headline)
        try:
            evaluate_standup(db, standup, insights)
        except Exception:
            log.exception("standup evaluation failed; keeping ingest")
        run.jira_count = jira_count
        run.cliq_count = cliq_count
        run.relevant_cliq_count = relevant_count
        run.change_count = change_count
        run.insight_count = len(insights)
        run.status = "completed"
        run.error = f"cliq: {cliq_error}" if cliq_error else ""
        run.finished_at = datetime.utcnow()
        db.commit()
    except Exception as exc:
        run.status = "failed"
        run.error = str(exc)
        run.finished_at = datetime.utcnow()
        db.commit()
        raise
    db.refresh(run)
    return run


def _wait_for_run(db: Session, run_id: int, timeout: int = 150) -> PipelineRun:
    deadline = time.time() + timeout
    run = db.query(PipelineRun).filter(PipelineRun.id == run_id).one()
    while time.time() < deadline:
        db.expire_all()
        run = db.query(PipelineRun).filter(PipelineRun.id == run_id).one()
        if run.status != "running":
            return run
        time.sleep(1)
    raise RuntimeError("Another refresh is still running. Wait a few seconds and click Refresh again.")


def refresh_message_metadata(db: Session) -> int:
    relevant = 0
    for message in db.query(CliqMessage).all():
        relevance = classify_message(message.message, message.chat_name, sender_id=message.sender_id, sender=message.sender)
        message.relevant = relevance["relevant"]
        message.relevance_reasons = relevance["reasons"]
        message.ticket_keys = relevance["ticket_keys"]
        if message.relevant:
            relevant += 1
    db.commit()
    return relevant


def email_standup(db: Session, standup: Standup | None = None, *, nudge: bool = False) -> dict:
    from app.services.mail import send_text_email, smtp_ready

    if standup is None:
        standup = db.query(Standup).order_by(Standup.id.desc()).first()
    if standup is None:
        return {"ok": False, "error": "No standup to email"}
    if not smtp_ready():
        return {"ok": False, "error": "SMTP is not configured"}
    to = (settings.release_notes_email or settings.smtp_from or settings.smtp_user or "").strip()
    if not to:
        return {"ok": False, "error": "No standup email recipient"}
    if nudge:
        subject = "Standup ready in 5 minutes"
        body = (
            f"The 09:00 IST standup job is about to run.\n\n"
            f"Last briefing ({standup.window_end}):\n\n"
            f"{standup.raw_markdown or '(empty)'}"
        )
    else:
        subject = "Today's standup"
        body = standup.raw_markdown or ""
        if not standup.llm_used:
            body = "Standup built from rules — LLM was unavailable.\n\n" + body
    try:
        send_text_email(to=to, subject=subject, body=body)
        return {"ok": True, "emailed_to": to}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:400]}


def deliver_standup(db: Session, standup: Standup | None = None) -> dict:
    if standup is None:
        standup = db.query(Standup).order_by(Standup.id.desc()).first()
    if standup is None:
        return {"ok": False, "error": "No standup to deliver"}
    mailed = email_standup(db, standup)
    client = CliqClient()
    if not client.configured:
        standup.delivery_status = "skipped_unconfigured" if not mailed.get("ok") else "emailed"
        db.commit()
        return {"ok": mailed.get("ok"), "error": mailed.get("error") or "Cliq is not configured", "email": mailed}
    text = standup.raw_markdown
    try:
        if settings.cliq_pm_chat_id:
            client.send_message(settings.cliq_pm_chat_id, text)
        elif settings.cliq_pm_email:
            client.send_to_email(settings.cliq_pm_email, text)
        else:
            standup.delivery_status = "emailed" if mailed.get("ok") else "skipped_no_recipient"
            db.commit()
            return {"ok": mailed.get("ok"), "error": mailed.get("error") or "Set CLIQ_PM_CHAT_ID or CLIQ_PM_EMAIL", "email": mailed}
        standup.delivered_at = datetime.utcnow()
        standup.delivery_status = "sent"
        db.commit()
        return {"ok": True, "standup_id": standup.id, "email": mailed}
    except Exception as exc:
        standup.delivery_status = "failed"
        db.commit()
        return {"ok": False, "error": str(exc), "email": mailed}

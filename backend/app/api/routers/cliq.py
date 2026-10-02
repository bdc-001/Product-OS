from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CliqMessage, PipelineRun, Standup
from app.services.cliq_briefing import filter_cliq_briefing, heuristic_cliq_briefing
from app.services.hidden import hidden_keys
from app.services.people import name_for, resolve_text

router = APIRouter()


@router.get("/messages")
def list_messages(relevant_only: bool = True, db: Session = Depends(get_db)):
    query = db.query(CliqMessage).order_by(CliqMessage.timestamp.desc())
    if relevant_only:
        query = query.filter(CliqMessage.relevant.is_(True))
    messages = query.limit(200).all()
    return {
        "messages": [
            {
                "id": m.id,
                "chat_name": m.chat_name,
                "sender": name_for(m.sender_id, m.sender) or m.sender,
                "message": resolve_text(m.message),
                "timestamp": m.timestamp.isoformat() if m.timestamp else None,
                "relevant": m.relevant,
                "reasons": m.relevance_reasons,
                "ticket_keys": m.ticket_keys,
            }
            for m in messages
        ]
    }


@router.get("/cliq/digest")
def cliq_summary(db: Session = Depends(get_db)):
    standup = db.query(Standup).order_by(Standup.id.desc()).first()
    briefing = getattr(standup, "cliq_briefing", None) if standup else None
    if briefing and (briefing.get("conversations") or briefing.get("promises") or briefing.get("unanswered") or briefing.get("follow_up_tomorrow")):
        payload = briefing
    else:
        payload = heuristic_cliq_briefing(db)
    payload = filter_cliq_briefing(payload, hidden_keys(db))
    run = db.query(PipelineRun).order_by(PipelineRun.id.desc()).first()
    error = (run.error or "") if run else ""
    if error.lower().startswith("cliq:"):
        payload["ingest_error"] = error.split(":", 1)[1].strip()
        payload["stale"] = True
    elif run and run.cliq_count == 0 and run.status == "completed":
        payload["stale"] = True
    return payload

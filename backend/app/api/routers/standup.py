from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.common import CommandBody, parse_since, standup_out
from app.database import get_db
from app.models import Evaluation, Standup
from app.services.hidden import hidden_keys
from app.services.pipeline import deliver_standup
from app.services.standup import answer_command
from app.services.week_actions import attach_ticket_to_week_item

router = APIRouter()


class AttachTicketBody(BaseModel):
    issue_key: str = ""
    title: str = ""
    card_key: str = ""


@router.get("/standup/latest")
def latest_standup(since: str | None = None, db: Session = Depends(get_db)):
    standup = db.query(Standup).order_by(Standup.id.desc()).first()
    if not standup:
        return {"standup": None, "unchanged": False}
    stamp = parse_since(since)
    created = standup.created_at.replace(tzinfo=None) if standup.created_at else None
    if stamp and created and created <= stamp:
        return {"standup": None, "unchanged": True, "created_at": standup.created_at.isoformat()}
    evaluation = db.query(Evaluation).filter(Evaluation.standup_id == standup.id).one_or_none()
    return {"standup": standup_out(standup, evaluation, hidden_keys(db), db), "unchanged": False}


@router.post("/standup/ask")
def ask_standup(body: CommandBody, db: Session = Depends(get_db)):
    standup = db.query(Standup).order_by(Standup.id.desc()).first()
    return answer_command(standup, body.query, db)


@router.post("/standup/attach-ticket")
def attach_ticket(body: AttachTicketBody, db: Session = Depends(get_db)):
    try:
        item = attach_ticket_to_week_item(
            db,
            issue_key=body.issue_key,
            title=body.title,
            card_key=body.card_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "item": item}


@router.post("/standup/deliver")
def send_standup(db: Session = Depends(get_db)):
    result = deliver_standup(db)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result

@router.get("/dashboard/{section}")
def dashboard_section(section: str, db: Session = Depends(get_db)):
    from sqlalchemy.orm import load_only
    from app.services.hidden import filter_items
    from app.services.week_actions import hydrate_action_items, merge_dev_load
    from app.services.time_window import format_ist
    columns = {"summary": [Standup.id, Standup.window_start, Standup.window_end], "actions": [Standup.id, Standup.this_week, Standup.other_actions, Standup.week_actions], "developer-load": [Standup.id, Standup.dev_load]}
    if section not in columns: raise HTTPException(404, "Unknown dashboard section")
    row = db.query(Standup).options(load_only(*columns[section])).order_by(Standup.id.desc()).first()
    if not row: return {"standup": None}
    data = {"id": row.id}
    if section == "summary":
        data["window_label"] = f"{format_ist(row.window_start)} → {format_ist(row.window_end)}" if row.window_start and row.window_end else ""
    elif section == "actions":
        hidden = hidden_keys(db)
        for key in ("this_week", "other_actions", "week_actions"):
            data[key] = hydrate_action_items(db, filter_items(getattr(row,key) or [], hidden))
    else: data["dev_load"] = merge_dev_load(row.dev_load or [])
    return {"standup": data}

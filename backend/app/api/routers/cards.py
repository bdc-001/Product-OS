from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.common import HideBody
from app.database import get_db
from app.models import HiddenCard
from app.services.hidden import hide_card, unhide_card

router = APIRouter()


@router.get("/cards/hidden")
def list_hidden(db: Session = Depends(get_db)):
    rows = db.query(HiddenCard).order_by(HiddenCard.created_at.desc()).all()
    return {"hidden": [{"card_key": row.card_key, "title": row.title} for row in rows]}


@router.post("/cards/hide")
def hide_from_view(body: HideBody, db: Session = Depends(get_db)):
    if not (body.issue_key or "").strip() and not (body.title or "").strip() and not (body.card_key or "").strip():
        raise HTTPException(status_code=400, detail="issue_key or title is required")
    row = hide_card(db, issue_key=body.issue_key, title=body.title, card_key=body.card_key)
    return {"ok": True, "card_key": row.card_key}


@router.delete("/cards/hide")
def restore_to_view(card_key: str, db: Session = Depends(get_db)):
    if not unhide_card(db, card_key):
        raise HTTPException(status_code=404, detail="Card is not hidden")
    return {"ok": True}

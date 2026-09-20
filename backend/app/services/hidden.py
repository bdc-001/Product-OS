"""Cards the PM removed from their view. Persist across refreshes."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import HiddenCard


def card_key_for(item: dict | None, issue_key: str = "", title: str = "") -> str:
    payload = item or {}
    key = (issue_key or payload.get("issue_key") or "").strip().upper()
    if key:
        return f"issue:{key}"
    heading = (title or payload.get("title") or "").strip().lower()
    return f"title:{heading[:160]}"


def hidden_keys(db: Session) -> set[str]:
    return {row.card_key for row in db.query(HiddenCard).all()}


def is_hidden_item(item: dict, keys: set[str]) -> bool:
    explicit = (item.get("card_key") or "").strip()
    if explicit and explicit in keys:
        return True
    if card_key_for(item) in keys:
        return True
    issue = (item.get("issue_key") or "").strip().upper()
    return bool(issue) and f"issue:{issue}" in keys


def filter_items(items: list | None, keys: set[str]) -> list:
    return [item for item in (items or []) if isinstance(item, dict) and not is_hidden_item(item, keys)]


def filter_sections(sections: dict, keys: set[str]) -> dict:
    return {name: filter_items(items, keys) if isinstance(items, list) else items for name, items in sections.items()}


def hide_card(db: Session, issue_key: str = "", title: str = "", card_key: str = "") -> HiddenCard:
    key = (card_key or "").strip() or card_key_for({}, issue_key=issue_key, title=title)
    existing = db.query(HiddenCard).filter(HiddenCard.card_key == key).one_or_none()
    if existing:
        return existing
    row = HiddenCard(card_key=key, title=(title or issue_key or key)[:256])
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def unhide_card(db: Session, card_key: str) -> bool:
    row = db.query(HiddenCard).filter(HiddenCard.card_key == card_key).one_or_none()
    if not row:
        return False
    db.delete(row)
    db.commit()
    return True

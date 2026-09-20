"""Active Jira issues. Soft-deleted (archived) rows stay for history."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import JiraIssue
from app.services.jira_scope import is_aborted_status


def active_query(db: Session):
    return db.query(JiraIssue).filter(JiraIssue.archived_at.is_(None))


def list_active(db: Session) -> list[JiraIssue]:
    return active_query(db).all()


def get_by_key(db: Session, key: str, *, include_archived: bool = False) -> JiraIssue | None:
    query = db.query(JiraIssue).filter(JiraIssue.issue_key == (key or "").strip().upper())
    row = query.one_or_none()
    if row is None:
        return None
    if not include_archived and row.archived_at is not None:
        return None
    return row


def archive_issue(row: JiraIssue, when: datetime | None = None) -> None:
    row.archived_at = when or datetime.utcnow()


def restore_issue(row: JiraIssue) -> None:
    row.archived_at = None


CHANGELOG_KEEP = {"status", "assignee", "priority", "parent", "epic link", "sprint", "issuetype", "summary", "resolution"}


def merge_comments(old, new) -> list:
    by_id: dict[str, dict] = {}
    orphan = []
    for comment in list(old or []) + list(new or []):
        if not isinstance(comment, dict):
            continue
        cid = str(comment.get("id") or "")
        if not cid:
            orphan.append(comment)
            continue
        prev = by_id.get(cid)
        if not prev or (comment.get("updated") or "") >= (prev.get("updated") or ""):
            by_id[cid] = comment
    return list(by_id.values()) + orphan


def compact_changelog(items) -> list:
    out = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        field = (item.get("field") or "").lower()
        if field not in CHANGELOG_KEEP:
            continue
        out.append(
            {
                "id": item.get("id") or "",
                "author": item.get("author") or "",
                "created": item.get("created") or "",
                "field": item.get("field") or "",
                "from": item.get("from") or "",
                "to": item.get("to") or "",
            }
        )
    return out[-80:]


STRING_FIELDS = (
    "issue_key", "jira_id", "summary", "description", "status", "status_category",
    "priority", "issue_type", "assignee", "assignee_id", "creator", "labels", "url",
)
DATE_FIELDS = ("created_at", "updated_at", "due_date")


def apply_normalized(existing: JiraIssue | None, data: dict, db: Session) -> JiraIssue:
    payload: dict = {}
    for field in STRING_FIELDS:
        value = data.get(field)
        if value is None:
            value = getattr(existing, field) if existing else ""
        payload[field] = value or ""
    for field in DATE_FIELDS:
        value = data.get(field)
        if value is None and existing is not None and field not in data:
            value = getattr(existing, field)
        payload[field] = value
    payload["comments_json"] = merge_comments(
        getattr(existing, "comments_json", None) if existing else [],
        data.get("comments_json"),
    )
    payload["changelog_json"] = compact_changelog(data.get("changelog_json") if data.get("changelog_json") is not None else (getattr(existing, "changelog_json", None) if existing else []))
    payload["extra_json"] = data.get("extra_json") if isinstance(data.get("extra_json"), dict) else (getattr(existing, "extra_json", None) if existing else {}) or {}
    payload["ingested_at"] = datetime.utcnow()
    aborted = is_aborted_status(payload.get("status") or "")
    if existing:
        for field, value in payload.items():
            setattr(existing, field, value)
        existing.archived_at = datetime.utcnow() if aborted else None
        return existing
    row = JiraIssue(**payload)
    row.archived_at = datetime.utcnow() if aborted else None
    db.add(row)
    return row


def should_archive(status: str) -> bool:
    return is_aborted_status(status)

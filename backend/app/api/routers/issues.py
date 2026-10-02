from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import false, func, or_
from sqlalchemy.orm import Session, load_only

from app.api.common import board_for, issue_out
from app.clients.jira import primary_project, support_project
from app.config import settings
from app.database import get_db
from app.models import CliqMessage, Correlation, Insight, IssueChange, JiraIssue
from app.services.filter import REPORT_TYPE_NEEDLES, classify_issue
from app.services.hidden import hidden_keys
from app.services.jira_fields import BUG_FIELDS, REPORT_FIELDS, TASK_FIELDS
from app.services.jira_scope import ABORTED_TOKENS, is_aborted_status
from app.services.people import name_for, resolve_text

router = APIRouter()

DONE_STATUSES = ("done", "closed", "released", "resolved")
BUG_TYPES = ("bug", "defect", "incident")


def _untyped_support(type_col):
    support = support_project()
    if not support or support == primary_project():
        return false()
    return (type_col == "") & JiraIssue.issue_key.ilike(f"{support}-%")


def _apply_kind_filter(query, kind: str):
    if kind == "all":
        return query
    type_col = func.lower(func.coalesce(JiraIssue.issue_type, ""))
    if kind == "bug":
        return query.filter(or_(type_col.in_(BUG_TYPES), _untyped_support(type_col)))
    if kind == "report":
        return query.filter(or_(*[type_col.contains(needle) for needle in REPORT_TYPE_NEEDLES]))
    if kind == "task":
        report = or_(*[type_col.contains(needle) for needle in REPORT_TYPE_NEEDLES])
        bug = or_(type_col.in_(BUG_TYPES), _untyped_support(type_col))
        return query.filter(~report, ~bug)
    return query


def _apply_state_filter(query, state: str):
    if state not in {"open", "done"}:
        return query
    status_l = func.lower(func.coalesce(JiraIssue.status, ""))
    cat_l = func.lower(func.coalesce(JiraIssue.status_category, ""))
    done = or_(cat_l == "done", status_l.in_(DONE_STATUSES))
    if state == "open":
        return query.filter(~done)
    return query.filter(done)


@router.get("/jira/schemas")
def jira_schemas():
    return {
        "connected": bool(settings.jira_email and settings.jira_api_token),
        "bug": [{"key": k, "label": l, "required": r} for k, l, r in BUG_FIELDS],
        "task": [{"key": k, "label": l, "required": r} for k, l, r in TASK_FIELDS],
        "report": [{"key": k, "label": l, "required": r} for k, l, r in REPORT_FIELDS],
        "why_unknown": (
            None
            if settings.jira_email and settings.jira_api_token
            else "Jira details are unknown because JIRA_EMAIL and JIRA_API_TOKEN are not set. The agent can only see Cliq text until those are added."
        ),
    }


@router.get("/issues")
def list_issues(board: str | None = None, q: str = "", kind: str = "all", state: str = "all", compact: bool = False, offset: int = 0, limit: int | None = None, db: Session = Depends(get_db)):
    prefix = (board or "").upper()
    columns = [
        JiraIssue.id, JiraIssue.issue_key, JiraIssue.summary, JiraIssue.status, JiraIssue.status_category,
        JiraIssue.priority, JiraIssue.assignee, JiraIssue.issue_type, JiraIssue.updated_at, JiraIssue.created_at,
    ]
    if not compact:
        columns.extend([
            JiraIssue.creator, JiraIssue.labels, JiraIssue.url, JiraIssue.due_date,
            JiraIssue.description, JiraIssue.extra_json,
        ])
    query = db.query(JiraIssue).options(load_only(*columns)).filter(JiraIssue.archived_at.is_(None))
    if prefix:
        import re
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", prefix):
            raise HTTPException(400, "Invalid Jira project key")
        query = query.filter(JiraIssue.issue_key.ilike(f"{prefix}-%"))
    if q:
        needle = f"%{q}%"
        query = query.filter(or_(
            JiraIssue.issue_key.ilike(needle),
            JiraIssue.summary.ilike(needle),
            JiraIssue.assignee.ilike(needle),
            JiraIssue.status.ilike(needle),
        ))
    query = query.filter(~or_(*[JiraIssue.status.ilike(f"%{token}%") for token in ABORTED_TOKENS]))
    hidden_issue_keys = sorted({key[6:].upper() for key in hidden_keys(db) if key.startswith("issue:") and len(key) > 6})
    if hidden_issue_keys:
        query = query.filter(~JiraIssue.issue_key.in_(hidden_issue_keys))
    query = _apply_kind_filter(query, kind)
    query = _apply_state_filter(query, state)
    query = query.order_by(func.coalesce(JiraIssue.updated_at, JiraIssue.created_at).desc(), JiraIssue.id.desc())
    total = query.count()
    page_size = min(100, max(1, limit)) if limit is not None else (200 if compact else None)
    if page_size is not None:
        query = query.offset(max(0, offset)).limit(page_size)
    issues = query.all()
    issues = [i for i in issues if not is_aborted_status(i.status)]
    def summary(i):
        return {"issue_key": i.issue_key, "summary": i.summary, "status": i.status, "priority": i.priority, "assignee": i.assignee, "issue_type": i.issue_type, "kind": classify_issue(i.issue_type, i.issue_key), "updated_at": i.updated_at.isoformat() if i.updated_at else None, "board": prefix}

    return {
        "issues": [summary(i) if compact else issue_out(i) for i in issues],
        "total": total,
        "connected": bool(settings.jira_email and settings.jira_api_token),
        "board": prefix,
    }


@router.get("/issues/{issue_key}")
def issue_detail(issue_key: str, db: Session = Depends(get_db)):
    key = issue_key.upper()
    issue = db.query(JiraIssue).filter(JiraIssue.issue_key == key).one_or_none()
    changes = db.query(IssueChange).filter(IssueChange.issue_key == key).all()
    messages = db.query(CliqMessage).filter(CliqMessage.message.ilike(f"%{key}%")).all()
    insights = db.query(Insight).filter(Insight.issue_key == key).order_by(Insight.id.desc()).limit(20).all()
    links = db.query(Correlation).filter(Correlation.issue_key == key).all()
    msg_by_id = {m.id: m for m in messages}
    if not issue and not messages and not insights:
        raise HTTPException(status_code=404, detail="Issue not found")
    return {
        "issue": issue_out(issue) if issue else {
            "issue_key": key,
            "summary": "Not loaded from Jira",
            "status": "",
            "priority": "",
            "assignee": "",
            "creator": "",
            "reporter": "",
            "issue_type": "",
            "kind": classify_issue("", key),
            "board": board_for(key),
            "due_date": None,
            "created_at": None,
            "updated_at": None,
            "url": f"{settings.jira_base_url}/browse/{key}",
            "labels": "",
            "fields": {},
            "missing_fields": [],
            "field_checklist": [],
            "schema_kind": classify_issue("", key),
        },
        "jira_connected": bool(settings.jira_email and settings.jira_api_token),
        "why_unknown": (
            None
            if issue
            else (
                "This key was seen in Cliq, but Jira was not queried. "
                "Set JIRA_EMAIL and JIRA_API_TOKEN, then Refresh now."
                if not (settings.jira_email and settings.jira_api_token)
                else "Jira is connected but this key was not returned by search."
            )
        ),
        "description": issue.description if issue else "",
        "comments": issue.comments_json if issue else [],
        "changes": [
            {
                "type": c.change_type,
                "field": c.field,
                "from": c.from_value,
                "to": c.to_value,
                "author": c.author,
                "changed_at": c.changed_at.isoformat() if c.changed_at else None,
                "noisy": c.noisy,
                "impact": c.impact,
            }
            for c in changes
        ],
        "cliq": [
            {
                "id": m.id,
                "chat_name": m.chat_name,
                "sender": name_for(m.sender_id, m.sender) or m.sender,
                "message": resolve_text(m.message),
                "timestamp": m.timestamp.isoformat() if m.timestamp else None,
                "relevant": m.relevant,
            }
            for m in messages
        ],
        "insights": [
            {
                "type": i.type,
                "title": i.title,
                "description": i.description,
                "action": i.action,
                "confidence": i.confidence,
                "why": i.why,
                "sources": i.sources,
            }
            for i in insights
        ],
        "correlations": [
            {
                "confidence": row.confidence,
                "match_reason": row.match_reason,
                "chat_name": (msg_by_id.get(row.message_id).chat_name if msg_by_id.get(row.message_id) else ""),
            }
            for row in links
        ],
    }

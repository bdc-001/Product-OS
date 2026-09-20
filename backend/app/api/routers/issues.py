from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, load_only

from app.api.common import board_for, issue_out
from app.config import settings
from app.database import get_db
from app.models import CliqMessage, Correlation, Insight, IssueChange, JiraIssue
from app.services.filter import classify_issue
from app.services.hidden import hidden_keys
from app.services.jira_fields import BUG_FIELDS, REPORT_FIELDS, TASK_FIELDS
from app.services.jira_scope import is_aborted_status
from app.services.people import name_for, resolve_text

router = APIRouter()


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
        JiraIssue.issue_key, JiraIssue.summary, JiraIssue.status, JiraIssue.status_category,
        JiraIssue.priority, JiraIssue.assignee, JiraIssue.issue_type, JiraIssue.updated_at, JiraIssue.created_at,
    ]
    if not compact:
        columns.extend([
            JiraIssue.creator, JiraIssue.labels, JiraIssue.url, JiraIssue.due_date,
            JiraIssue.description, JiraIssue.extra_json,
        ])
    query = db.query(JiraIssue).options(load_only(*columns)).filter(JiraIssue.archived_at.is_(None))
    if prefix in {"AC", "PS"}:
        query = query.filter(JiraIssue.issue_key.ilike(f"{prefix}-%"))
    issues = query.all()
    hidden = hidden_keys(db)
    issues = [
        i
        for i in issues
        if not is_aborted_status(i.status) and f"issue:{i.issue_key.upper()}" not in hidden
    ]
    if q:
        needle = q.lower()
        issues = [i for i in issues if needle in f"{i.issue_key} {i.summary} {i.assignee} {i.status}".lower()]
    if kind != "all": issues = [i for i in issues if classify_issue(i.issue_type, i.issue_key) == kind]
    if state == "open": issues = [i for i in issues if i.status_category.lower() != "done" and i.status.lower() not in {"done", "closed", "released", "resolved"}]
    if state == "done": issues = [i for i in issues if i.status_category.lower() == "done" or i.status.lower() in {"done", "closed", "released", "resolved"}]
    issues.sort(key=lambda row: (row.updated_at or row.created_at).isoformat() if (row.updated_at or row.created_at) else "", reverse=True)
    total = len(issues)
    if limit is not None: issues = issues[max(0, offset):max(0, offset) + min(100, max(1,limit))]
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

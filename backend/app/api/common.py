"""Shared request bodies and response helpers for /api routers."""

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models import Evaluation, JiraIssue, Standup
from app.services.filter import classify_issue
from app.services.hidden import filter_items
from app.services.jira_fields import missing_fields
from app.services.week_actions import hydrate_action_items, merge_dev_load
from app.services.time_window import format_ist, now_local, period_for, week_range_label


class CommandBody(BaseModel):
    query: str


class HideBody(BaseModel):
    issue_key: str = ""
    title: str = ""
    card_key: str = ""


class PrdBody(BaseModel):
    title: str = ""
    problem: str = ""
    service: str = ""
    issue_key: str = ""
    issue_keys: list[str] = []
    prototype_id: int = 0


class CodebaseIndexBody(BaseModel):
    branch: str = ""
    pull: bool = True


class CodebaseAskBody(BaseModel):
    question: str = ""
    branch: str = ""


class ArtifactBody(BaseModel):
    feature: str = ""
    notes: str = ""
    format: str = "brief"


class CommsBody(BaseModel):
    title: str = ""
    angle: str = ""
    kind: str = "release_notes"
    artifacts: bool = False


class ReleaseRegenBody(BaseModel):
    checked: list[str] | None = None
    features_in_short: str = ""
    artifacts: bool = False


class RoadmapBody(BaseModel):
    notes: str | None = None
    epics: list | None = None


class CopilotPlanBody(BaseModel):
    document_ids: list[int] = []
    note_ids: list[int] = []
    prototype_ids: list[int] = []
    parent_plan_id: int = 0
    code_scope: str = ""
    prompt: str = ""
    notes: str = ""
    branch: str = ""
    ticket_keys: list[str] = []
    people: list[str] = []
    image_ids: list[str] = []


class CopilotRunBody(BaseModel):
    plan_id: int
    approved: bool = False
    action_ids: list[str] = []
    overrides: dict[str, dict] = {}


class CopilotUndoBody(BaseModel):
    plan_id: int


class ProfileBody(BaseModel):
    pm_display_name: str | None = None
    pm_cliq_user_id: str | None = None
    pm_cliq_mentions: str | None = None
    timezone: str | None = None
    data_branch: str | None = None
    jira: dict | None = None
    cliq: dict | None = None
    llm: dict | None = None
    mail: dict | None = None
    workspace: dict | None = None
    people: dict[str, str] | None = None
    team: dict | None = None


def board_for(key: str) -> str:
    k = (key or "").upper()
    if k.startswith("PS-"):
        return "Product Support"
    if k.startswith("AC-"):
        return "Sense"
    return ""


def issue_out(issue: JiraIssue) -> dict:
    extras = getattr(issue, "extra_json", None) or {}
    schema = missing_fields(
        {
            "issue_key": issue.issue_key,
            "issue_type": issue.issue_type,
            "summary": issue.summary,
            "description": issue.description,
            "status": issue.status,
            "priority": issue.priority,
            "assignee": issue.assignee,
            "reporter": extras.get("reporter") or issue.creator,
            "due_date": issue.due_date.isoformat() if issue.due_date else "",
            "labels": issue.labels,
        },
        extras,
    )
    return {
        "issue_key": issue.issue_key,
        "summary": issue.summary,
        "status": issue.status,
        "priority": extras.get("priority_level") or issue.priority,
        "assignee": issue.assignee,
        "creator": issue.creator,
        "reporter": extras.get("reporter") or issue.creator,
        "issue_type": issue.issue_type,
        "kind": classify_issue(issue.issue_type, issue.issue_key),
        "board": board_for(issue.issue_key),
        "due_date": issue.due_date.isoformat() if issue.due_date else None,
        "created_at": issue.created_at.isoformat() if issue.created_at else None,
        "updated_at": issue.updated_at.isoformat() if issue.updated_at else None,
        "url": issue.url,
        "labels": issue.labels,
        "description": (issue.description or "")[:2000],
        "fields": extras,
        "missing_fields": schema["missing"],
        "field_checklist": schema["filled"],
        "schema_kind": schema["kind"],
    }


def standup_out(
    standup: Standup,
    evaluation: Evaluation | None = None,
    hidden: set[str] | None = None,
    db: Session | None = None,
) -> dict:
    keys = hidden or set()
    this_week = filter_items(getattr(standup, "this_week", None) or [], keys)
    other_actions = filter_items(getattr(standup, "other_actions", None) or [], keys)
    week_actions = filter_items(getattr(standup, "week_actions", None) or [], keys)
    if db is not None:
        this_week = hydrate_action_items(db, this_week)
        other_actions = hydrate_action_items(db, other_actions)
        week_actions = hydrate_action_items(db, week_actions)
    return {
        "id": standup.id,
        "run_id": standup.run_id,
        "window_start": standup.window_start.isoformat() if standup.window_start else None,
        "window_end": standup.window_end.isoformat() if standup.window_end else None,
        "needs_attention": filter_items(standup.needs_attention, keys),
        "at_risk": filter_items(standup.at_risk, keys),
        "completed": filter_items(standup.completed, keys),
        "team_signals": filter_items(standup.team_signals or [], keys),
        "todays_actions": filter_items(standup.todays_actions or [], keys),
        "bugs": filter_items(standup.bugs or [], keys),
        "tasks": filter_items(standup.tasks or [], keys),
        "wallet_requests": filter_items(standup.wallet_requests or [], keys),
        "long_pending": filter_items(standup.long_pending or [], keys),
        "week_actions": week_actions,
        "this_week": this_week,
        "other_actions": other_actions,
        "cliq_briefing": getattr(standup, "cliq_briefing", None) or {},
        "dev_load": merge_dev_load(getattr(standup, "dev_load", None) or []),
        "monday_plan": getattr(standup, "monday_plan", None) or {},
        "raw_markdown": standup.raw_markdown,
        "llm_used": standup.llm_used,
        "period": period_for(standup.window_end) if standup.window_end else period_for(),
        "headline": "This week's actionables",
        "week_label": week_range_label(standup.window_end) if standup.window_end else week_range_label(),
        "now_label": format_ist(standup.window_end) if standup.window_end else format_ist(now_local()),
        "window_label": (
            f"{format_ist(standup.window_start)} → {format_ist(standup.window_end)}"
            if standup.window_start and standup.window_end
            else ""
        ),
        "created_at": standup.created_at.isoformat() if standup.created_at else None,
        "delivery_status": standup.delivery_status,
        "evaluation": {
            "overall": evaluation.overall,
            "signal_detection": evaluation.signal_detection,
            "prioritization": evaluation.prioritization,
            "grounding": evaluation.grounding,
            "actionability": evaluation.actionability,
            "completeness": evaluation.completeness,
            "noise": evaluation.noise,
            "hallucination": evaluation.hallucination,
            "notes": evaluation.notes,
        }
        if evaluation
        else None,
    }


def parse_since(since: str | None) -> datetime | None:
    if not since:
        return None
    try:
        return datetime.fromisoformat(since.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None

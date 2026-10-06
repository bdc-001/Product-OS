"""Monday #product-internal plan → Jira tickets (or create-ticket)."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import CliqChat, CliqMessage, JiraIssue
from app.services.filter import extract_ticket_keys, is_product_internal_chat
from app.services.people import is_pm_sender
from app.services.team import product_internal_chat_id, PRODUCT_INTERNAL_NAME
from app.services.time_window import timestamp_in_window, week_monday, week_range_label

HEADING_RE = re.compile(r"^\s*\*?\s*(\d+)\s*[.)]\s*(.+?)\s*\*?\s*$")
BULLET_RE = re.compile(r"^\s*[-•]\s+(.+)$")
STOP = {
    "the",
    "of",
    "for",
    "and",
    "on",
    "a",
    "an",
    "to",
    "in",
    "with",
    "at",
    "least",
    "atleast",
    "this",
    "week",
    "last",
    "from",
    "into",
    "via",
}


def strip_md(text: str) -> str:
    return re.sub(r"[*_`]+", "", text or "").strip()


def product_internal_chat_ids(db: Session | None = None) -> list[str]:
    ids = [product_internal_chat_id()]
    if db is None:
        return ids
    for chat in db.query(CliqChat).all():
        if is_product_internal_chat(chat.name, chat.chat_id) and chat.chat_id not in ids:
            ids.append(chat.chat_id)
    return ids


def split_this_week(text: str) -> str:
    lines = (text or "").splitlines()
    start = None
    for i, line in enumerate(lines):
        compact = strip_md(line).lower()
        if compact.startswith("this week"):
            start = i + 1
            break
    if start is None:
        return ""
    end = len(lines)
    for j in range(start, len(lines)):
        compact = strip_md(lines[j]).lower()
        if compact.startswith("last week"):
            end = j
            break
    return "\n".join(lines[start:end]).strip()


def parse_week_tasks(section: str) -> list[dict]:
    heading = ""
    heading_has_bullets = False
    tasks: list[dict] = []

    def flush_heading() -> None:
        nonlocal heading, heading_has_bullets
        if heading and not heading_has_bullets:
            tasks.append(_task(heading, heading))
        heading = ""
        heading_has_bullets = False

    for line in (section or "").splitlines():
        raw = strip_md(line)
        if not raw:
            continue
        numbered = HEADING_RE.match(raw)
        bullet = BULLET_RE.match(line) or BULLET_RE.match(raw)
        if numbered:
            flush_heading()
            heading = strip_md(numbered.group(2))
            heading_has_bullets = False
            continue
        if bullet:
            title = strip_md(bullet.group(1))
            if not title:
                continue
            heading_has_bullets = True
            tasks.append(_task(title, heading))
            continue
    flush_heading()
    return [task for task in tasks if len(task["title"]) > 3]


def _task(title: str, area: str) -> dict:
    return {
        "title": title,
        "area": area,
        "keys": extract_ticket_keys(f"{area} {title}"),
        "line": f"{area}: {title}" if area and area.lower() not in title.lower() else title,
    }


def tokens(text: str) -> list[str]:
    cleaned = re.sub(r"[^a-z0-9\s]", " ", (text or "").lower())
    words = []
    for word in cleaned.split():
        if word in STOP or len(word) < 3:
            continue
        stem = word
        for suffix in ("ing", "ed", "es", "s"):
            if len(stem) > 5 and stem.endswith(suffix):
                stem = stem[: -len(suffix)]
                break
        words.append(stem)
    return words


def _score(plan: str, summary: str) -> float:
    plan_l = (plan or "").lower()
    summary_l = (summary or "").lower()
    if not plan_l or not summary_l:
        return 0.0
    if plan_l in summary_l or summary_l in plan_l:
        return 1.0
    plan_toks = tokens(plan)
    summary_toks = set(tokens(summary))
    if not plan_toks:
        return 0.0
    overlap = [word for word in plan_toks if word in summary_toks]
    return len(overlap) / len(set(plan_toks))


def match_task_to_issue(task: dict, issues: list[JiraIssue]) -> tuple[JiraIssue | None, float]:
    for key in task.get("keys") or []:
        for issue in issues:
            if (issue.issue_key or "").upper() == key.upper():
                return issue, 1.0
    title = task.get("title") or ""
    best: tuple[JiraIssue | None, float] = (None, 0.0)
    for issue in issues:
        score = _score(title, issue.summary or "")
        if score > best[1]:
            best = (issue, score)
    issue, score = best
    if issue and score >= 0.55:
        return issue, score
    return None, score


def monday_plan_message(db: Session, now: datetime | None = None) -> CliqMessage | None:
    monday = week_monday(now)
    week_end = monday + timedelta(days=7)
    chat_ids = set(product_internal_chat_ids(db))
    rows = (
        db.query(CliqMessage)
        .filter(CliqMessage.chat_id.in_(chat_ids))
        .order_by(CliqMessage.timestamp.asc())
        .all()
    )
    candidates: list[CliqMessage] = []
    for message in rows:
        if not is_pm_sender(message.sender_id, message.sender):
            continue
        if not timestamp_in_window(message.timestamp, monday, week_end):
            continue
        text = message.message or ""
        if "this week" not in text.lower():
            continue
        candidates.append(message)
    if not candidates:
        return None

    def sort_key(message: CliqMessage) -> tuple[int, int]:
        on_monday = 0 if timestamp_in_window(message.timestamp, monday, monday + timedelta(days=1)) else 1
        return (on_monday, -(len(message.message or "")))

    candidates.sort(key=sort_key)
    return candidates[0]


def planned_tasks_from_db(db: Session, now: datetime | None = None) -> dict:
    message = monday_plan_message(db, now)
    if not message:
        return {
            "found": False,
            "week_label": week_range_label(now),
            "message": "",
            "chat": PRODUCT_INTERNAL_NAME,
            "tasks": [],
        }
    section = split_this_week(message.message or "")
    tasks = parse_week_tasks(section or message.message or "")
    issues = list(db.query(JiraIssue).all())
    mapped = []
    for task in tasks:
        issue, score = match_task_to_issue(task, issues)
        mapped.append(
            {
                **task,
                "issue_key": issue.issue_key if issue else "",
                "issue_summary": issue.summary if issue else "",
                "status": issue.status if issue else "",
                "assignee": issue.assignee if issue else "",
                "priority": issue.priority if issue else "",
                "match_score": round(score, 2),
                "needs_ticket": issue is None,
            }
        )
    return {
        "found": True,
        "week_label": week_range_label(now),
        "message": message.message or "",
        "chat": message.chat_name or PRODUCT_INTERNAL_NAME,
        "sender": message.sender,
        "timestamp": message.timestamp.isoformat() if message.timestamp else None,
        "tasks": mapped,
    }


def unmatched_search_phrases(plan: dict) -> list[str]:
    phrases = []
    for task in plan.get("tasks") or []:
        if task.get("issue_key"):
            continue
        title = (task.get("title") or "").strip()
        if title:
            phrases.append(title)
    return phrases

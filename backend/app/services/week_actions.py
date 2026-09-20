"""Weekly PM actionables: UAT, QA remind, assign Done, Monday plan."""

from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy.orm import Session

from app.clients.jira import JiraClient
from app.models import Insight, JiraIssue, Standup
from app.repositories.issues import list_active
from app.services.filter import classify_issue, is_bug_ticket
from app.services.jira_fields import age_days, stale_days
from app.services.jira_scope import is_aborted_status, matches_pm
from app.services.team import developers, match_developer, match_qa, qa_person
from app.services.week_plan import planned_tasks_from_db

DONE_STATUSES = {"done", "completed", "complete"}
CLOSED_TOKENS = ("released", "closed", "resolved", "cancelled", "canceled", "won't do", "wont do")
STAGING_TOKENS = ("staging", "uat")
IN_PROGRESS_TOKENS = ("in progress", "in qa", "picked by qa")
BANDWIDTH_SKIP_TYPES = {"epic", "subtask", "sub-task", "sub task"}


def is_done_status(status: str) -> bool:
    return (status or "").strip().lower() in DONE_STATUSES


def is_closed_status(status: str) -> bool:
    text = (status or "").strip().lower()
    return any(token in text for token in CLOSED_TOKENS)


def is_staging_status(status: str) -> bool:
    text = (status or "").lower()
    if is_closed_status(text) or is_done_status(text):
        return False
    return any(token in text for token in STAGING_TOKENS)


def is_in_progress_status(status: str, category: str = "") -> bool:
    cat = (category or "").lower()
    if cat in {"indeterminate", "in progress"}:
        return True
    text = (status or "").lower()
    return any(token in text for token in IN_PROGRESS_TOKENS) and not is_done_status(status) and not is_staging_status(status)


def is_p1(issue: JiraIssue) -> bool:
    extras = getattr(issue, "extra_json", None) or {}
    blob = f"{issue.priority or ''} {extras.get('priority_level') or ''}".lower()
    return "p1" in blob or blob.strip() in {"highest", "high", "critical", "blocker"}


def issue_is_pm(issue: JiraIssue) -> bool:
    extras = getattr(issue, "extra_json", None) or {}
    return matches_pm(extras.get("product_manager") or "") or matches_pm(issue.assignee or "")


def issue_pm_field(issue: JiraIssue) -> bool:
    extras = getattr(issue, "extra_json", None) or {}
    return matches_pm(extras.get("product_manager") or "")


def is_bandwidth_type(issue_type: str) -> bool:
    return (issue_type or "").strip().lower() not in BANDWIDTH_SKIP_TYPES


def empty_dev_load() -> list[dict]:
    return [
        {
            "short": person["short"],
            "name": person["name"],
            "account_id": person["account_id"],
            "bugs": 0,
            "tasks": 0,
            "in_progress": 0,
            "keys": [],
            "bug_keys": [],
            "task_keys": [],
            "tickets": [],
        }
        for person in developers()
    ]


def apply_dev_load_rows(rows: list[dict]) -> list[dict]:
    load = empty_dev_load()
    by_id = {item["account_id"]: item for item in load}
    by_short = {item["short"].lower(): item for item in load}
    for row in rows:
        person = match_developer(row.get("assignee") or "", row.get("assignee_id") or "")
        if not person:
            continue
        bucket = by_id.get(person["account_id"]) or by_short.get(person["short"].lower())
        if not bucket:
            continue
        key = row.get("issue_key") or ""
        if not key or key in bucket["keys"]:
            continue
        kind = classify_issue(row.get("issue_type") or "", key)
        bucket["keys"].append(key)
        bucket.setdefault("tickets", []).append(
            {"key": key, "summary": (row.get("summary") or key).strip() or key, "kind": kind}
        )
        if kind == "bug":
            bucket["bug_keys"].append(key)
        else:
            bucket["task_keys"].append(key)
        bucket["bugs"] = len(bucket["bug_keys"])
        bucket["tasks"] = len(bucket["task_keys"])
        bucket["in_progress"] = bucket["bugs"] + bucket["tasks"]
    return load


def merge_dev_load(rows: list[dict] | None) -> list[dict]:
    load = empty_dev_load()
    by_id = {item["account_id"]: item for item in load}
    by_short = {item["short"].lower(): item for item in load}
    for row in rows or []:
        person = match_developer(row.get("name") or "", row.get("account_id") or "")
        bucket = None
        if person:
            bucket = by_id.get(person["account_id"]) or by_short.get(person["short"].lower())
        if not bucket:
            bucket = by_short.get((row.get("short") or "").lower())
        if not bucket:
            continue
        bugs = int(row.get("bugs") or 0)
        tasks = int(row.get("tasks") or 0)
        total = int(row.get("in_progress") or bugs + tasks)
        bucket["bugs"] = bugs
        bucket["tasks"] = tasks
        bucket["in_progress"] = total
        bucket["keys"] = list(row.get("keys") or [])
        bucket["bug_keys"] = list(row.get("bug_keys") or [])
        bucket["task_keys"] = list(row.get("task_keys") or [])
        tickets = list(row.get("tickets") or [])
        if not tickets and bucket["keys"]:
            tickets = [{"key": key, "summary": key, "kind": "bug" if key in bucket["bug_keys"] else "task"} for key in bucket["keys"]]
        bucket["tickets"] = tickets
    return load


def current_dev_load() -> list[dict]:
    client = JiraClient()
    if not client.configured:
        return empty_dev_load()
    try:
        rows = client.fetch_dev_in_progress()
    except Exception:
        return empty_dev_load()
    parsed = []
    for raw in rows:
        fields = raw.get("fields") or {}
        assignee = fields.get("assignee") or {}
        issue_type = ((fields.get("issuetype") or {}).get("name") or "")
        if not is_bandwidth_type(issue_type):
            continue
        parsed.append(
            {
                "issue_key": raw.get("key") or "",
                "assignee": assignee.get("displayName") or "",
                "assignee_id": assignee.get("accountId") or "",
                "summary": fields.get("summary") or "",
                "issue_type": issue_type,
            }
        )
    return apply_dev_load_rows(parsed)


def recommend_assignee(load: list[dict], taken: dict[str, int] | None = None) -> dict:
    projected = {item["short"]: item["in_progress"] + (taken or {}).get(item["short"], 0) for item in load}
    if not projected:
        return {"short": "", "name": "", "in_progress": 0, "why": "No developers configured."}
    winner = min(load, key=lambda item: projected[item["short"]])
    snapshot = ", ".join(f"{item['short']} {projected[item['short']]}" for item in load)
    return {
        "short": winner["short"],
        "name": winner["name"],
        "in_progress": winner["in_progress"],
        "why": f"{winner['name']} has the fewest In Progress tickets ({winner['in_progress']}). Load now: {snapshot}.",
    }


def _item(
    *,
    kind: str,
    urgency: int,
    title: str,
    action: str,
    body: str = "",
    why: str = "",
    issue_key: str = "",
    status: str = "",
    assignee: str = "",
    recommend: str = "",
    confidence: str = "HIGH",
    sources: list | None = None,
    action_type: str = "follow_up",
    flag: str = "",
) -> dict:
    return {
        "kind": kind,
        "urgency": urgency,
        "title": title,
        "body": body,
        "action": action,
        "why": why,
        "issue_key": issue_key,
        "board": "PS" if (issue_key or "").upper().startswith("PS-") else "AC" if (issue_key or "").upper().startswith("AC-") else "",
        "status": status,
        "assignee": assignee,
        "recommend": recommend,
        "confidence": confidence,
        "sources": sources or [],
        "action_type": action_type,
        "flag": flag or kind,
        "age_days": None,
        "state_days": None,
    }


def _status_age_days(issue: JiraIssue, now: datetime) -> int | None:
    for item in reversed(issue.changelog_json or []):
        if (item.get("field") or "").lower() != "status":
            continue
        raw = item.get("created")
        if not raw:
            continue
        try:
            stamp = datetime.fromisoformat(str(raw).replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            continue
        return max(0, (now.replace(tzinfo=None) - stamp).days)
    return stale_days(issue.updated_at, now.replace(tzinfo=None) if now.tzinfo else now)


def _annotate_age(item: dict, issue: JiraIssue | None, now: datetime) -> dict:
    if not issue:
        return item
    item["age_days"] = age_days(issue.created_at, now.replace(tzinfo=None) if getattr(now, "tzinfo", None) else now)
    item["state_days"] = _status_age_days(issue, now)
    return item


def _uat_urgency(issue: JiraIssue) -> int:
    base = 10 if is_staging_status(issue.status) else 14
    if is_p1(issue):
        base -= 2
    return max(8, base)


def build_week_actions(db: Session, now: datetime, insights: list[Insight] | None = None, dev_load: list[dict] | None = None) -> dict:
    issues = [issue for issue in list_active(db) if not is_aborted_status(issue.status)]
    load = [
        dict(
            item,
            keys=list(item.get("keys") or []),
            bug_keys=list(item.get("bug_keys") or []),
            task_keys=list(item.get("task_keys") or []),
            bugs=int(item.get("bugs") or 0),
            tasks=int(item.get("tasks") or 0),
            in_progress=int(item.get("in_progress") or 0),
        )
        for item in (dev_load or current_dev_load())
    ]
    working_load = [
        dict(
            item,
            keys=list(item.get("keys") or []),
            bug_keys=list(item.get("bug_keys") or []),
            task_keys=list(item.get("task_keys") or []),
        )
        for item in load
    ]
    plan = planned_tasks_from_db(db, now)
    actions: list[dict] = []

    for issue in issues:
        if is_closed_status(issue.status):
            continue
        if not issue_pm_field(issue) and not (is_done_status(issue.status) and matches_pm(issue.assignee or "")):
            continue
        extras = issue.extra_json or {}
        pm_ok = issue_pm_field(issue)
        developer = match_developer(issue.assignee or "", issue.assignee_id or "")
        qa = match_qa(issue.assignee or "", issue.assignee_id or "")
        p1 = "P1" if is_p1(issue) else (issue.priority or extras.get("priority_level") or "")

        if pm_ok and qa and is_in_progress_status(issue.status, issue.status_category):
            actions.append(
                _item(
                    kind="qa_remind",
                    urgency=20,
                    title=f"Remind {qa_person().get('short') or qa_person().get('name') or 'QA'} · {issue.issue_key}",
                    body=f"{issue.summary}. Status {issue.status}, assignee {qa_person().get('name') or 'QA'}.",
                    action=f"Remind {qa_person().get('name') or 'QA'} to move {issue.issue_key} — it is In Progress on QA and you are the PM.",
                    why=f"QA In Progress on {qa_person().get('name') or 'QA'} while you are Product Manager.",
                    issue_key=issue.issue_key,
                    status=issue.status,
                    assignee=issue.assignee,
                    sources=[{"type": "jira", "ref": issue.issue_key}],
                    action_type="follow_up",
                )
            )
            continue

        if is_staging_status(issue.status) and pm_ok:
            who = developer["name"] if developer else (issue.assignee or "unassigned")
            actions.append(
                _item(
                    kind="uat",
                    urgency=_uat_urgency(issue),
                    title=f"UAT · {issue.issue_key}",
                    body=f"{issue.summary}. {issue.status} · {who}" + (f" · {p1}" if p1 else ""),
                    action=f"Do UAT on {issue.issue_key} ({issue.status}).",
                    why="Ticket where you are PM is in Staging/UAT.",
                    issue_key=issue.issue_key,
                    status=issue.status,
                    assignee=issue.assignee,
                    sources=[{"type": "jira", "ref": issue.issue_key}],
                    action_type="review",
                )
            )
            continue

        if is_done_status(issue.status) and pm_ok and developer:
            actions.append(
                _item(
                    kind="uat",
                    urgency=_uat_urgency(issue),
                    title=f"UAT · {issue.issue_key}",
                    body=f"{issue.summary}. Done on {developer['name']}." + (f" {p1}." if p1 else ""),
                    action=f"Look into UAT for {issue.issue_key} — it is Done on {developer['name']}.",
                    why="You are PM and this ticket is Done on a developer.",
                    issue_key=issue.issue_key,
                    status=issue.status,
                    assignee=issue.assignee,
                    sources=[{"type": "jira", "ref": issue.issue_key}],
                    action_type="review",
                )
            )
            continue

        if is_done_status(issue.status) and (pm_ok or matches_pm(issue.assignee or "")) and not developer and not qa:
            if is_bug_ticket(issue.issue_key, issue.issue_type):
                continue
            rec = recommend_assignee(working_load)
            actions.append(
                _item(
                    kind="assign_dev",
                    urgency=24 if is_p1(issue) else 26,
                    title=f"Assign developer · {issue.issue_key}",
                    body=f"{issue.summary}. Done on your board, not yet with a developer.",
                    action=f"Assign {issue.issue_key} to {rec['name']} to keep In Progress load even.",
                    why=rec["why"],
                    issue_key=issue.issue_key,
                    status=issue.status,
                    assignee=issue.assignee,
                    recommend=rec["name"],
                    sources=[{"type": "jira", "ref": issue.issue_key}],
                    action_type="follow_up",
                )
            )
            for item in working_load:
                if item["name"] == rec["name"] or item["short"] == rec["short"]:
                    item["in_progress"] += 1
                    break

    plan_items: list[dict] = []
    if plan.get("found"):
        for task in plan.get("tasks") or []:
            if task.get("needs_ticket"):
                area = f" ({task['area']})" if task.get("area") else ""
                item = _item(
                    kind="create_ticket",
                    urgency=30,
                    title=task["title"],
                    body=f"From your Monday {plan.get('chat') or '#product-internal'} post{area}. No Jira ticket matched this plan item.",
                    action=f"Create a Jira task ticket for: {task['title']}",
                    why="This week's plan item has no matching ticket.",
                    sources=[{"type": "cliq", "ref": plan.get("chat") or "#product-internal"}],
                    action_type="follow_up",
                    flag="create_ticket",
                )
                actions.append(item)
                plan_items.append(item)
                continue
            key = task.get("issue_key") or ""
            item = _item(
                kind="week_plan",
                urgency=34,
                title=f"{key}: {task['title']}" if key else task["title"],
                body=f"{task.get('issue_summary') or task['title']}. {task.get('status') or ''} · {task.get('assignee') or ''}".strip(),
                action=f"Work {key} this week — {task['title']}." if key else f"Work on {task['title']} this week.",
                why=f"Mapped from your Monday #product-internal post (match {task.get('match_score')}).",
                issue_key=key,
                status=task.get("status") or "",
                assignee=task.get("assignee") or "",
                sources=[{"type": "cliq", "ref": plan.get("chat") or "#product-internal"}, {"type": "jira", "ref": key}],
                action_type="follow_up",
            )
            actions.append(item)
            plan_items.append(item)
    else:
        item = _item(
            kind="create_ticket",
            urgency=28,
            title="Monday plan missing in #product-internal",
            body="No message from you in #product-internal this week that lists this week's tasks.",
            action="Post this week's plan in #product-internal, or refresh once Cliq can read the channel.",
            why="Weekly actionables start from your Monday product-internal post.",
            sources=[{"type": "cliq", "ref": "#product-internal"}],
            confidence="MEDIUM",
        )
        actions.append(item)
        plan_items.append(item)

    seen_keys = {(item.get("issue_key") or "", item.get("title") or "") for item in actions}
    insight_kinds = {
        "blocker": ("blocker", 18, "Unblock"),
        "wallet": ("wallet", 50, "Triage wallet"),
    }
    wallet_added = 0
    for insight in insights or []:
        mapped = insight_kinds.get(insight.type)
        if not mapped:
            continue
        kind, urgency, _ = mapped
        key = insight.issue_key or ""
        marker = (key, insight.title)
        if marker in seen_keys or (key and any(item.get("issue_key") == key and item.get("kind") in {"uat", "qa_remind", "assign_dev", "week_plan"} for item in actions)):
            continue
        related = next((issue for issue in issues if issue.issue_key == key), None)
        if kind == "blocker" and related and is_p1(related):
            urgency = 16
        if kind == "wallet":
            if wallet_added >= 3:
                continue
            wallet_added += 1
        actions.append(
            _item(
                kind=kind,
                urgency=urgency,
                title=insight.title,
                body=insight.description,
                action=insight.action,
                why=insight.why,
                issue_key=key,
                sources=insight.sources or [],
                confidence=insight.confidence,
                action_type=insight.action_type or "follow_up",
            )
        )
        seen_keys.add(marker)

    actions.sort(key=lambda item: (item.get("urgency") or 99, item.get("title") or ""))
    other = [item for item in actions if (item.get("kind") or "") not in {"week_plan", "create_ticket"}]
    this_week, other = heuristic_prioritize_actions(plan_items, other)
    for index, item in enumerate(this_week, start=1):
        item["rank"] = index
    for index, item in enumerate(other, start=1):
        item["rank"] = index
    combined = this_week + other
    for index, item in enumerate(combined, start=1):
        item.setdefault("rank", index)

    return {
        "week_label": plan.get("week_label") or "",
        "monday_plan": {
            "found": bool(plan.get("found")),
            "chat": plan.get("chat") or "#product-internal",
            "excerpt": (plan.get("message") or "")[:1200],
            "tasks": plan.get("tasks") or [],
        },
        "dev_load": load,
        "week_actions": combined,
        "this_week": this_week,
        "other_actions": other,
        "qa_name": qa_person().get("name") or "QA",
    }


KIND_WEIGHTS = {
    "assign_dev": 0,
    "uat": 1,
    "qa_remind": 2,
    "blocker": 3,
    "week_plan": 0,
    "create_ticket": 1,
}


def heuristic_prioritize_actions(this_week: list[dict], other: list[dict]) -> tuple[list[dict], list[dict]]:
    """Deterministic order. LLM reorder can silently drop UATs."""
    week = list(this_week or [])
    rest = list(other or [])
    rest.sort(
        key=lambda item: (
            KIND_WEIGHTS.get(item.get("kind") or "", 8),
            item.get("urgency") or 99,
            item.get("title") or "",
        )
    )
    return week, rest[:12]


def llm_prioritize_actions(this_week: list[dict], other: list[dict]) -> tuple[list[dict], list[dict]]:
    return heuristic_prioritize_actions(this_week, other)


def hydrate_action_items(db: Session, items: list[dict] | None) -> list[dict]:
    from app.services.hidden import card_key_for

    rows = [dict(item) for item in (items or []) if isinstance(item, dict)]
    keys = [item.get("issue_key") for item in rows if item.get("issue_key")]
    found = {}
    if keys:
        found = {
            issue.issue_key: issue
            for issue in db.query(JiraIssue).filter(JiraIssue.issue_key.in_(keys)).all()
        }
    now = datetime.utcnow()
    out = []
    for item in rows:
        key = item.get("issue_key") or ""
        item["card_key"] = item.get("card_key") or card_key_for(item)
        issue = found.get(key)
        if issue:
            item["status"] = issue.status
            item["assignee"] = issue.assignee or item.get("assignee") or ""
            item["url"] = issue.url or item.get("url") or ""
            if not (item.get("title") or "").strip() or (item.get("title") or "").strip().upper() == key:
                item["title"] = issue.summary or item.get("title") or key
            _annotate_age(item, issue, now)
            if (item.get("state_days") or 0) >= 3:
                item["aging"] = True
                why = item.get("why") or ""
                if "in this state" not in why.lower():
                    item["why"] = (why + f" In this state for {item['state_days']} days.").strip()
            kind = (item.get("kind") or "").lower()
            if is_closed_status(issue.status) and kind in {"uat", "assign_dev", "qa_remind"}:
                continue
        out.append(item)
    return out


def attach_ticket_to_week_item(
    db: Session,
    *,
    issue_key: str,
    title: str = "",
    card_key: str = "",
) -> dict:
    """Link a Jira key onto a week-plan card that the LLM left without a ticket."""
    from sqlalchemy.orm.attributes import flag_modified

    from app.services.hidden import card_key_for

    key = (issue_key or "").strip().upper()
    if not re.match(r"^[A-Z][A-Z0-9]+-\d+$", key):
        raise ValueError("issue_key must look like AC-123 or PS-45")

    standup = db.query(Standup).order_by(Standup.id.desc()).first()
    if not standup:
        raise ValueError("No standup loaded yet. Refresh first.")

    issue = db.query(JiraIssue).filter(JiraIssue.issue_key == key).one_or_none()
    wanted_card = (card_key or "").strip() or card_key_for({}, title=title)
    wanted_title = (title or "").strip().lower()

    def matches(item: dict) -> bool:
        if not isinstance(item, dict):
            return False
        if item.get("issue_key"):
            return False
        explicit = (item.get("card_key") or "").strip()
        if wanted_card and (explicit == wanted_card or card_key_for(item) == wanted_card):
            return True
        heading = (item.get("title") or "").strip().lower()
        return bool(wanted_title) and heading == wanted_title

    updated = None
    for field in ("this_week", "other_actions", "week_actions"):
        rows = list(getattr(standup, field) or [])
        changed = False
        for index, item in enumerate(rows):
            if not matches(item):
                continue
            row = dict(item)
            row["issue_key"] = key
            row["board"] = "PS" if key.startswith("PS-") else "AC" if key.startswith("AC-") else row.get("board") or ""
            if (row.get("kind") or "").lower() == "create_ticket":
                row["kind"] = "week_plan"
            if issue:
                row["status"] = issue.status or row.get("status") or ""
                row["assignee"] = issue.assignee or row.get("assignee") or ""
                row["url"] = issue.url or row.get("url") or ""
                if not (row.get("title") or "").strip() or "ticket" in (row.get("title") or "").lower():
                    row["title"] = issue.summary or row.get("title") or key
            row["card_key"] = card_key_for(row)
            row["sources"] = list(row.get("sources") or []) + [{"type": "jira", "ref": key}]
            rows[index] = row
            updated = row
            changed = True
            break
        if changed:
            setattr(standup, field, rows)
            flag_modified(standup, field)

    if not updated:
        raise ValueError("Could not find that week item (it may already have a ticket).")

    db.add(standup)
    db.commit()
    hydrated = hydrate_action_items(db, [updated])
    return hydrated[0] if hydrated else updated


def partition_week_actions(actions: list[dict]) -> tuple[list[dict], list[dict]]:
    this_week = [item for item in actions if (item.get("kind") or "") in {"week_plan", "create_ticket"}]
    other = [item for item in actions if (item.get("kind") or "") not in {"week_plan", "create_ticket"}]
    return this_week, other


def insights_from_week_actions(run_id: int, payload: dict) -> list[Insight]:
    items = payload.get("week_actions") or []
    if not items:
        items = (payload.get("this_week") or []) + (payload.get("other_actions") or [])
    insights = []
    for item in items:
        kind = item.get("kind") or "week_plan"
        insights.append(
            Insight(
                run_id=run_id,
                type=kind[:32],
                title=item.get("title") or kind,
                description=item.get("body") or "",
                action=item.get("action") or "",
                action_type=item.get("action_type") or "follow_up",
                confidence=item.get("confidence") or "HIGH",
                issue_key=item.get("issue_key") or "",
                sources=item.get("sources") or [],
                why=item.get("why") or "",
            )
        )
    return insights

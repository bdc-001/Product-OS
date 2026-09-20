from datetime import datetime, timedelta
import re

from sqlalchemy.orm import Session

from app.config import settings
from app.models import CliqMessage, Correlation, Insight, IssueChange, JiraIssue, Standup
from app.repositories.issues import list_active
from app.services.filter import BLOCKER_PATTERNS, extract_ticket_keys, is_bug_ticket, is_noisy_field, is_wallet_chat, strip_jira_links
from app.services.jira_fields import age_days, missing_fields, stale_days
from app.services.jira_scope import is_aborted_status
from app.services.people import is_pm_tagged, load_directory, name_for, resolve_text
from app.services.team import developer_handoff_names, roster_prompt_block
from app.services.time_window import PERIOD_FOCUS, briefing_label, briefing_window, format_ist, period_for, timestamp_in_window
from app.services.week_plan import planned_tasks_from_db


DONE_STATUSES = {
    "done",
    "closed",
    "resolved",
    "complete",
    "completed",
    "aborted",
    "cancelled",
    "canceled",
    "won't do",
    "wont do",
    "released",
}
BLOCKED_STATUSES = {"blocked", "impediment", "waiting"}
HIGH_PRIORITIES = {"highest", "high", "critical", "blocker"}


def _in_window(value: str | datetime | None, start: datetime, end: datetime) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return False
    else:
        parsed = value
    return start <= parsed <= end


def detect_changes(db: Session, window_start: datetime, window_end: datetime) -> int:
    db.query(IssueChange).delete()
    count = 0
    issues = list_active(db)
    for issue in issues:
        if is_aborted_status(issue.status) or getattr(issue, "archived_at", None):
            continue
        if issue.created_at and _in_window(issue.created_at, window_start, window_end):
            db.add(
                IssueChange(
                    issue_key=issue.issue_key,
                    change_type="created",
                    field="status",
                    to_value=issue.status,
                    changed_at=issue.created_at,
                    impact="high" if issue.priority.lower() in HIGH_PRIORITIES else "medium",
                )
            )
            count += 1
        for item in issue.changelog_json or []:
            changed_at = item.get("created")
            if not _in_window(changed_at, window_start, window_end):
                continue
            field = (item.get("field") or "").lower()
            noisy = is_noisy_field(field)
            change_type = _change_type(field, item.get("from") or "", item.get("to") or "")
            impact = "low" if noisy else _impact(issue, field, item.get("to") or "")
            db.add(
                IssueChange(
                    issue_key=issue.issue_key,
                    change_type=change_type,
                    field=field,
                    from_value=item.get("from") or "",
                    to_value=item.get("to") or "",
                    author=item.get("author") or "",
                    changed_at=datetime.fromisoformat(changed_at.replace("Z", "+00:00")).replace(tzinfo=None)
                    if isinstance(changed_at, str)
                    else None,
                    noisy=noisy,
                    impact=impact,
                )
            )
            count += 1
        for comment in issue.comments_json or []:
            created = comment.get("created")
            if not _in_window(created, window_start, window_end):
                continue
            db.add(
                IssueChange(
                    issue_key=issue.issue_key,
                    change_type="comment",
                    field="comment",
                    to_value=(comment.get("body") or "")[:500],
                    author=comment.get("author") or "",
                    changed_at=datetime.fromisoformat(created.replace("Z", "+00:00")).replace(tzinfo=None)
                    if isinstance(created, str)
                    else None,
                    impact="medium",
                )
            )
            count += 1
    db.commit()
    return count


def _change_type(field: str, from_value: str, to_value: str) -> str:
    to_l = to_value.lower()
    from_l = from_value.lower()
    if field == "status":
        if to_l in DONE_STATUSES:
            return "completed"
        if to_l in BLOCKED_STATUSES:
            return "blocked"
        if from_l in DONE_STATUSES and to_l not in DONE_STATUSES:
            return "reopened"
        return "status_change"
    if field == "priority":
        return "priority_change"
    if field == "assignee":
        return "assignee_change"
    if field in {"duedate", "due date"}:
        return "due_date_change"
    if field == "description":
        return "description_change"
    return f"{field}_change"


def _impact(issue: JiraIssue, field: str, to_value: str) -> str:
    if field in {"status", "priority", "assignee", "duedate", "due date"}:
        if issue.priority.lower() in HIGH_PRIORITIES or to_value.lower() in BLOCKED_STATUSES:
            return "high"
        return "medium"
    return "low"


def _cliq_in_window(db: Session, window_start: datetime, window_end: datetime, relevant_only: bool = True) -> list[CliqMessage]:
    query = db.query(CliqMessage)
    if relevant_only:
        query = query.filter(CliqMessage.relevant.is_(True))
    return [
        message
        for message in query.order_by(CliqMessage.timestamp.asc()).all()
        if timestamp_in_window(message.timestamp, window_start, window_end)
    ]


def correlate(db: Session, window_start: datetime | None = None, window_end: datetime | None = None) -> int:
    db.query(Correlation).delete()
    issues = {i.issue_key: i for i in list_active(db)}
    if window_start and window_end:
        messages = _cliq_in_window(db, window_start, window_end)
    else:
        messages = db.query(CliqMessage).filter(CliqMessage.relevant.is_(True)).all()
    count = 0
    for message in messages:
        matched = set(message.ticket_keys or extract_ticket_keys(message.message))
        for key in matched:
            db.add(
                Correlation(
                    issue_key=key,
                    message_id=message.id,
                    level=1,
                    confidence="HIGH",
                match_reason=f"linked via mention of {key} in {message.chat_name or 'Cliq'}",
                )
            )
            count += 1
        if matched:
            continue
        lower = (message.message or "").lower()
        for key, issue in issues.items():
            summary = (issue.summary or "").strip()
            if len(summary) >= 12 and summary.lower() in lower:
                db.add(
                    Correlation(
                        issue_key=key,
                        message_id=message.id,
                        level=2,
                        confidence="MEDIUM",
                        match_reason=f"linked via title match in {message.chat_name or 'Cliq'}",
                    )
                )
                count += 1
    db.commit()
    return count


def build_insights(db: Session, run_id: int, window_start: datetime, window_end: datetime) -> list[Insight]:
    db.query(Insight).filter(Insight.run_id == run_id).delete()
    issues = list_active(db)
    changes = db.query(IssueChange).filter(IssueChange.noisy.is_(False)).all()
    messages = _cliq_in_window(db, window_start, window_end)
    correlations = db.query(Correlation).all()
    messages_by_id = {m.id: m for m in messages}
    cliq_by_issue: dict[str, list[CliqMessage]] = {}
    for corr in correlations:
        msg = messages_by_id.get(corr.message_id)
        if msg:
            cliq_by_issue.setdefault(corr.issue_key, []).append(msg)

    insights: list[Insight] = []
    now = window_end

    for issue in issues:
        if is_aborted_status(issue.status) or getattr(issue, "archived_at", None):
            continue
        issue_changes = [c for c in changes if c.issue_key == issue.issue_key]
        cliq_msgs = [m for m in cliq_by_issue.get(issue.issue_key, []) if not is_wallet_chat(m.chat_name)]
        cliq_texts = [m.message for m in cliq_msgs]
        ticket_type = "bug" if is_bug_ticket(issue.issue_key, issue.issue_type) else "task"
        emitted_board = False
        blocker = _detect_blocker(issue, issue_changes, cliq_msgs)
        if blocker:
            insights.append(
                Insight(
                    run_id=run_id,
                    type="blocker",
                    title=f"{issue.issue_key} is blocked",
                    description=blocker["description"],
                    action=blocker["action"],
                    action_type="follow_up",
                    confidence=blocker["confidence"],
                    issue_key=issue.issue_key,
                    sources=blocker["sources"],
                    why=blocker["why"],
                )
            )
        risk = _detect_risk(issue, issue_changes, cliq_msgs, now)
        if risk:
            insights.append(
                Insight(
                    run_id=run_id,
                    type="risk",
                    title=f"{issue.issue_key} is at risk",
                    description=risk["description"],
                    action=risk["action"],
                    action_type=risk["action_type"],
                    confidence=risk["confidence"],
                    issue_key=issue.issue_key,
                    sources=risk["sources"],
                    why=risk["why"],
                )
            )
        completed = next((c for c in issue_changes if c.change_type == "completed"), None)
        if completed:
            insights.append(
                Insight(
                    run_id=run_id,
                    type="completed",
                    title=f"{issue.issue_key} completed",
                    description=issue.summary,
                    action=f"Review completion of {issue.issue_key}",
                    action_type="review",
                    confidence="HIGH",
                    issue_key=issue.issue_key,
                    sources=[{"type": "jira", "ref": issue.issue_key, "url": issue.url}],
                    why=f"Status changed from {completed.from_value or 'Unknown'} to {completed.to_value}.",
                )
            )
        elif issue_changes:
            notable = [c for c in issue_changes if c.impact != "low" and c.change_type != "comment"]
            if notable:
                top = notable[0]
                emitted_board = True
                insights.append(
                    Insight(
                        run_id=run_id,
                        type=ticket_type,
                        title=f"{issue.issue_key} {top.change_type.replace('_', ' ')}",
                        description=f"{issue.summary}. {top.field}: {top.from_value or 'Unknown'} → {top.to_value or 'Unknown'}",
                        action=f"Review the {top.field} change on {issue.issue_key}",
                        action_type="review",
                        confidence="HIGH",
                        issue_key=issue.issue_key,
                        sources=[{"type": "jira", "ref": issue.issue_key, "url": issue.url}],
                        why=f"Jira changelog recorded a {top.field} change in the analysis window.",
                    )
                )
        if cliq_texts and not blocker:
            joined = _thread_body(cliq_msgs)
            conflict = _looks_like_conflict(cliq_msgs)
            emitted_board = True
            insights.append(
                Insight(
                    run_id=run_id,
                    type=ticket_type,
                    title=f"Conflict on {issue.issue_key}" if conflict else f"{issue.issue_key}: Jira + Cliq",
                    description=joined[:800],
                    action=f"Confirm the RCA and next step on {issue.issue_key}",
                    action_type="investigate" if conflict else "confirm",
                    confidence="HIGH",
                    issue_key=issue.issue_key,
                    sources=[{"type": "jira", "ref": issue.issue_key, "url": issue.url}]
                    + [{"type": "cliq", "ref": name_for(m.sender_id, m.chat_name), "chat_id": m.chat_id} for m in cliq_msgs[:4]],
                    why="Combined Jira state with Cliq thread."
                    + (" Multiple explanations/RCAs appear in chat." if conflict else ""),
                )
            )

    jira_ok = bool(settings.jira_email and settings.jira_api_token)
    if not jira_ok:
        insights.append(
            Insight(
                run_id=run_id,
                type="blocker",
                title="Jira API is not connected",
                description=(
                    "Bug and Task fields (status, owner, due date, Product Area, Steps to Reproduce, PRD link) "
                    "cannot be read. Add JIRA_EMAIL and JIRA_API_TOKEN to .env, then hit Refresh now."
                ),
                action="Connect Jira so the agent can load Sense and Product Support boards",
                action_type="follow_up",
                confidence="HIGH",
                why="JIRA_EMAIL and JIRA_API_TOKEN are empty, so Convin Jira was never queried.",
            )
        )
    critical_ranked: list[tuple[int, JiraIssue, dict]] = []
    for issue in issues:
        verdict = _critical_pending(issue, now)
        if not verdict:
            continue
        critical_ranked.append((verdict["score"], issue, verdict))
    critical_ranked.sort(key=lambda row: row[0], reverse=True)
    for _, issue, verdict in critical_ranked[:8]:
        board = "Product Support" if issue.issue_key.upper().startswith("PS-") else "Sense"
        insights.append(
            Insight(
                run_id=run_id,
                type="critical",
                title=f"Long pending · {issue.issue_key}: {issue.summary or 'Untitled'}",
                description=verdict["description"],
                action=verdict["action"],
                action_type="escalate",
                confidence="HIGH",
                issue_key=issue.issue_key,
                sources=[{"type": "jira", "ref": issue.issue_key}],
                why=verdict["why"],
            )
        )

    known_keys = {i.issue_key for i in issues}
    mentioned: dict[str, list[CliqMessage]] = {}
    for message in messages:
        if is_wallet_chat(message.chat_name):
            continue
        for key in message.ticket_keys or extract_ticket_keys(message.message):
            mentioned.setdefault(key, []).append(message)
    for key, msgs in mentioned.items():
        if key in known_keys:
            continue
        conflict = _looks_like_conflict(msgs)
        tagged = any(is_pm_tagged(m.message) for m in msgs)
        ticket_type = "bug" if is_bug_ticket(key) else "task"
        insights.append(
            Insight(
                run_id=run_id,
                type=ticket_type,
                title=f"Conflict on {key}" if conflict else f"{key} — combined Cliq thread",
                description=_thread_body(msgs)[:800],
                action=f"Review {key} and confirm the RCA with the people named in chat",
                action_type="investigate" if conflict else "review",
                confidence="HIGH",
                issue_key=key,
                sources=[{"type": "cliq", "ref": name_for(m.sender_id, m.chat_name), "chat_id": m.chat_id} for m in msgs[:5]],
                why=("PM tagged. " if tagged else "")
                + (
                    "Jira API is not connected, so status, owner, and due date cannot be loaded. Set JIRA_EMAIL and JIRA_API_TOKEN, then refresh."
                    if not (settings.jira_email and settings.jira_api_token)
                    else "Ticket discussed in Cliq."
                )
                + (" Conflicting explanations in the thread." if conflict else ""),
            )
        )

    wallet_groups = _group_wallet_messages(messages)
    for bucket, msgs in list(wallet_groups.items())[:12]:
        key = "" if bucket.startswith("open-") else bucket
        sender = name_for(msgs[0].sender_id, msgs[0].sender) or msgs[0].chat_name
        insights.append(
            Insight(
                run_id=run_id,
                type="wallet",
                title=f"Wallet request {key}".strip() if key else f"Wallet request from {sender}",
                description=_thread_body(msgs)[:800],
                action=f"Triage this wallet request{' for ' + key if key else ''} today",
                action_type="follow_up",
                confidence="HIGH",
                issue_key=key,
                sources=[{"type": "cliq", "ref": m.chat_name or "wallet-recharge", "chat_id": m.chat_id} for m in msgs[:5]],
                why="Raised in the wallet-balance / wallet-recharge Cliq group.",
            )
        )

    tagged_open = [
        m
        for m in messages
        if is_pm_tagged(m.message)
        and not is_wallet_chat(m.chat_name)
        and not (m.ticket_keys or extract_ticket_keys(m.message))
        and len(re.sub(r"@\w+", "", resolve_text(m.message or "")).strip()) > 12
    ]
    for message in tagged_open[:10]:
        insights.append(
            Insight(
                run_id=run_id,
                type="change",
                title=f"Open point from {name_for(message.sender_id, message.sender) or message.chat_name}",
                description=resolve_text(message.message)[:400],
                action="Reply or close this tagged thread today",
                action_type="follow_up",
                confidence="HIGH",
                sources=[{"type": "cliq", "ref": name_for(message.sender_id, message.chat_name), "chat_id": message.chat_id}],
                why="Arsalaan was tagged on an open Cliq point without a ticket ID.",
            )
        )

    unmatched = [
        m
        for m in messages
        if not is_wallet_chat(m.chat_name)
        and not extract_ticket_keys(m.message)
        and not is_pm_tagged(m.message)
        and any(re.search(sig, (m.message or "").lower()) for sig in BLOCKER_PATTERNS)
    ]
    for message in unmatched[:8]:
        insights.append(
            Insight(
                run_id=run_id,
                type="team_signal",
                title=f"Team signal in {message.chat_name or 'Cliq'}",
                description=message.message[:400],
                action="Investigate this conversation today",
                action_type="investigate",
                confidence="MEDIUM",
                sources=[{"type": "cliq", "ref": message.chat_name, "chat_id": message.chat_id}],
                why="Cliq contained a blocker or decision signal without an exact ticket match.",
            )
        )

    for insight in insights:
        db.add(insight)
    db.commit()
    return insights


def _detect_blocker(issue: JiraIssue, changes: list[IssueChange], messages: list[CliqMessage]) -> dict | None:
    sources = [{"type": "jira", "ref": issue.issue_key, "url": issue.url}]
    jira_blocked = issue.status.lower() in BLOCKED_STATUSES or any(c.change_type == "blocked" for c in changes)
    cliq_blocked = [m for m in messages if any(re.search(sig, (m.message or "").lower()) for sig in BLOCKER_PATTERNS)]
    if not jira_blocked and not cliq_blocked:
        return None
    if cliq_blocked:
        sources.extend({"type": "cliq", "ref": m.chat_name, "chat_id": m.chat_id} for m in cliq_blocked[:3])
    if jira_blocked and cliq_blocked:
        confidence = "HIGH"
        why = f"Jira status is {issue.status or 'Unknown'} and Cliq discussed a blocker."
        description = cliq_blocked[0].message[:280]
    elif cliq_blocked and issue.status.lower() not in BLOCKED_STATUSES:
        confidence = "HIGH"
        why = f"Jira shows {issue.status or 'Unknown'}, while Cliq says the work is waiting/blocked."
        description = cliq_blocked[0].message[:280]
    else:
        confidence = "HIGH"
        why = f"Jira status is {issue.status}."
        description = f"{issue.summary} is in {issue.status}."
    owner = issue.assignee or "the owner"
    return {
        "description": description,
        "action": f"Follow up with {owner} on {issue.issue_key} today",
        "confidence": confidence,
        "sources": sources,
        "why": why,
    }


def _detect_risk(issue: JiraIssue, changes: list[IssueChange], messages: list[CliqMessage], now: datetime) -> dict | None:
    high = issue.priority.lower() in HIGH_PRIORITIES
    due_soon = False
    if issue.due_date:
        due_soon = issue.due_date <= now + timedelta(days=3)
    no_progress = not any(c.change_type in {"status_change", "completed"} for c in changes)
    blocked = issue.status.lower() in BLOCKED_STATUSES or any(c.change_type == "blocked" for c in changes)
    repeated = len(messages) >= 2
    if not ((high and due_soon and no_progress) or (blocked and due_soon) or (repeated and blocked)):
        return None
    sources = [{"type": "jira", "ref": issue.issue_key, "url": issue.url}]
    sources.extend({"type": "cliq", "ref": m.chat_name, "chat_id": m.chat_id} for m in messages[:2])
    due = issue.due_date.date().isoformat() if issue.due_date else "Unknown"
    return {
        "description": f"{issue.priority or 'Unknown'} priority ticket, due {due}, status {issue.status or 'Unknown'}.",
        "action": f"Escalate or confirm a recovery plan for {issue.issue_key}",
        "action_type": "escalate" if high or blocked else "monitor",
        "confidence": "HIGH" if blocked and due_soon else "MEDIUM",
        "sources": sources,
        "why": "Priority, deadline, progress, and/or unresolved blocker discussion met the risk rule.",
    }


def _thread_body(messages: list[CliqMessage]) -> str:
    lines = []
    seen = set()
    for message in messages:
        text = strip_jira_links(resolve_text(message.message or "")).strip()
        text = re.sub(r"^\s*(ticket:?\s*)+", "", text, flags=re.I).strip(" :-")
        if not text:
            keys = extract_ticket_keys(message.message or "")
            text = f"Ticket {' '.join(keys)} mentioned, no extra detail in chat." if keys else ""
        if not text or text in seen:
            continue
        seen.add(text)
        sender = name_for(message.sender_id, message.sender) or message.sender or "Unknown"
        lines.append(f"{sender} ({message.chat_name}): {text}")
        if len(lines) >= 8:
            break
    return "\n".join(lines)


WALLET_REQUEST_HINT = re.compile(r"\b(recharge|credits?|top[- ]?up|add(?:ing)?|wallet)\b", re.I)
WALLET_ACK_HINT = re.compile(r"^(ok(ay)?|done|checked|noted|---+|thanks|thank you|fyi)[\s.!]*$", re.I)


def _wallet_text(message: CliqMessage) -> str:
    return strip_jira_links(resolve_text(message.message or "")).strip()


def _is_wallet_request(message: CliqMessage) -> bool:
    text = _wallet_text(message)
    if not text or WALLET_ACK_HINT.match(text):
        return False
    if is_pm_tagged(message.message):
        return True
    if message.ticket_keys or extract_ticket_keys(message.message):
        return True
    return bool(WALLET_REQUEST_HINT.search(text)) and len(text) > 18


def _group_wallet_messages(messages: list[CliqMessage]) -> dict[str, list[CliqMessage]]:
    ordered = sorted(
        [m for m in messages if is_wallet_chat(m.chat_name)],
        key=lambda m: m.timestamp or datetime.min,
    )
    groups: dict[str, list[CliqMessage]] = {}
    last_bucket = ""
    for message in ordered:
        keys = message.ticket_keys or extract_ticket_keys(message.message)
        if keys:
            last_bucket = keys[0]
            groups.setdefault(last_bucket, []).append(message)
            continue
        if _is_wallet_request(message):
            last_bucket = f"open-{message.id}"
            groups.setdefault(last_bucket, []).append(message)
            continue
        if last_bucket:
            groups[last_bucket].append(message)
    return groups


RCA_HINT = re.compile(
    r"\b(rca|root cause|because|caused by|due to|issue is|the problem is|wrong|not the (?:cause|rca))\b",
    re.I,
)


def _looks_like_conflict(messages: list[CliqMessage]) -> bool:
    hits = [m for m in messages if RCA_HINT.search(resolve_text(m.message or ""))]
    return len(hits) >= 2


HIGH_PRI_TOKENS = {"p1", "p0", "highest", "high", "critical", "blocker"}


def _is_high_priority(issue: JiraIssue, extras: dict) -> bool:
    pri = f"{issue.priority or ''} {extras.get('priority_level') or ''}".lower().replace("/", " ")
    tokens = {part.strip(".,") for part in pri.split() if part}
    return bool(tokens & HIGH_PRI_TOKENS)


def _critical_pending(issue: JiraIssue, now: datetime) -> dict | None:
    status = (issue.status or "").lower()
    if any(token in status for token in DONE_STATUSES) or (issue.status_category or "").lower() == "done":
        return None
    extras = getattr(issue, "extra_json", None) or {}
    age = age_days(issue.created_at, now)
    stale = stale_days(issue.updated_at, now)
    high = _is_high_priority(issue, extras)
    aborted = extras.get("aborted_links") or []
    reasons = []
    score = 0
    if high and age is not None and age >= 14:
        reasons.append(f"High priority and open for {age} days")
        score += 40 + min(age, 90)
    elif age is not None and age >= 45 and (stale or 0) >= 14:
        reasons.append(f"Open for {age} days with no meaningful close")
        score += 20 + min(age, 90)
    if high and stale is not None and stale >= 7:
        reasons.append(f"No Jira movement in {stale} days")
        score += 15 + min(stale, 40)
    if aborted:
        reasons.append("Linked work was aborted: " + ", ".join(aborted[:4]))
        score += 35
    if high and not issue.due_date and age is not None and age >= 14:
        reasons.append("High priority with no due date")
        score += 10
    if not reasons:
        return None
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
    missing = schema.get("missing") or []
    why = "; ".join(reasons)
    if missing:
        why += ". Missing fields: " + ", ".join(missing[:6])
    board = "Product Support" if issue.issue_key.upper().startswith("PS-") else "Sense"
    return {
        "score": score,
        "description": (
            f"{issue.summary or 'Untitled'} · {issue.status or 'Unknown'} · "
            f"{issue.priority or extras.get('priority_level') or 'Unknown'} · "
            f"owner {issue.assignee or 'Unknown'}. {why}."
        ),
        "action": f"Unblock or re-scope {issue.issue_key} on the {board} board today",
        "why": why,
    }


def context_payload(db: Session, insights: list[Insight], window_start: datetime | None = None, window_end: datetime | None = None, period: str = "") -> dict:
    issues = {i.issue_key: i for i in list_active(db)}
    if window_start and window_end:
        messages = _cliq_in_window(db, window_start, window_end)
    else:
        messages = db.query(CliqMessage).filter(CliqMessage.relevant.is_(True)).all()
    window = briefing_window()
    period = period or window.period
    changes = db.query(IssueChange).filter(IssueChange.noisy.is_(False)).all()
    threads: dict[str, list[dict]] = {}
    tagged_points = []
    for message in messages:
        item = {
            "chat": message.chat_name,
            "sender": name_for(message.sender_id, message.sender) or message.sender,
            "message": resolve_text(message.message),
            "pm_tagged": is_pm_tagged(message.message),
            "ticket_keys": message.ticket_keys or extract_ticket_keys(message.message),
            "reasons": message.relevance_reasons,
        }
        keys = item["ticket_keys"]
        if is_wallet_chat(message.chat_name):
            continue
        if keys:
            for key in keys:
                threads.setdefault(key, []).append(item)
        elif item["pm_tagged"]:
            tagged_points.append(item)
    combined = []
    for key, cliq in threads.items():
        issue = issues.get(key)
        combined.append(
            {
                "issue_key": key,
                "jira": {
                    "issue_type": issue.issue_type or "Unknown",
                    "summary": issue.summary,
                    "status": issue.status or "Unknown",
                    "priority": issue.priority or "Unknown",
                    "assignee": issue.assignee or "Unknown",
                    "due_date": issue.due_date.isoformat() if issue.due_date else "Unknown",
                }
                if issue
                else {"summary": "Unknown", "status": "Unknown", "priority": "Unknown", "assignee": "Unknown", "due_date": "Unknown", "issue_type": "Unknown"},
                "cliq_thread": cliq,
            }
        )
    board_snapshot = []
    for issue in issues.values():
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
        board_snapshot.append(
            {
                "issue_key": issue.issue_key,
                "board": "PS" if issue.issue_key.upper().startswith("PS-") else "AC",
                "issue_type": issue.issue_type,
                "summary": issue.summary,
                "status": issue.status or "Unknown",
                "priority": issue.priority or extras.get("priority_level") or "Unknown",
                "assignee": issue.assignee or "Unknown",
                "age_days": age_days(issue.created_at, datetime.utcnow()),
                "stale_days": stale_days(issue.updated_at, datetime.utcnow()),
                "missing_fields": schema["missing"],
                "aborted_links": extras.get("aborted_links") or [],
            }
        )
    return {
        "pm": settings.pm_display_name,
        "now": format_ist(window_end) if window_end else format_ist(window.end),
        "period": period,
        "focus": PERIOD_FOCUS.get(period, window.focus),
        "jira_connected": bool(settings.jira_email and settings.jira_api_token),
        "jira_note": (
            "Jira API is connected."
            if settings.jira_email and settings.jira_api_token
            else "Jira API is NOT connected. Do not invent status/owner/due. Say the API token is missing."
        ),
        "people": load_directory(),
        "handoff_developers": developer_handoff_names(),
        "roster": roster_prompt_block(),
        "instruction": (
            f"This is a {period} briefing at {(format_ist(window_end) if window_end else format_ist(window.end))}. {PERIOD_FOCUS.get(period, window.focus)} "
            "Only use Cliq messages and Jira changes inside the analysis window. "
            "Summarize open tickets and open Cliq points. "
            "PS-* and Bug issuetypes go in bugs (Product Support). "
            "AC-* Sense tickets go in tasks unless they are bugs. "
            "wallet-balance / wallet-recharge Cliq group requests go only in wallet_requests. "
            "monday_plan is Arsalaan's #product-internal post for this week — do not invent tickets that are not in Jira. "
            "Combine Jira+Cliq per ticket. Flag conflicting RCAs. "
            "Do not include Jira browse URLs in item bodies; the title already identifies the ticket."
        ),
        "monday_plan": planned_tasks_from_db(db, window_end or window.end),
        "combined_tickets": combined,
        "board_snapshot": board_snapshot,
        "pm_tagged_open_points": tagged_points,
        "changes": [
            {
                "issue_key": c.issue_key,
                "type": c.change_type,
                "field": c.field,
                "from": c.from_value,
                "to": c.to_value,
                "impact": c.impact,
            }
            for c in changes
            if c.impact != "low"
        ],
        "insights": [
            {
                "type": i.type,
                "title": i.title,
                "description": i.description,
                "action": i.action,
                "confidence": i.confidence,
                "issue_key": i.issue_key,
                "why": i.why,
                "sources": i.sources,
            }
            for i in insights
        ],
    }


def _digest_item(key: str, msgs: list[CliqMessage], issue: JiraIssue | None) -> dict:
    board = "Product Support" if (key or "").upper().startswith("PS-") else "Sense" if (key or "").upper().startswith("AC-") else ""
    senders = []
    chats = []
    for message in msgs:
        sender = name_for(message.sender_id, message.sender) or message.sender
        if sender and sender not in senders:
            senders.append(sender)
        if message.chat_name and message.chat_name not in chats:
            chats.append(message.chat_name)
    return {
        "issue_key": key,
        "board": board,
        "jira_summary": (issue.summary if issue else "") or ("Unknown until Jira is connected" if key else ""),
        "status": (issue.status if issue else "") or ("Unknown" if key else ""),
        "assignee": (issue.assignee if issue else "") or ("Unknown" if key else ""),
        "issue_type": (issue.issue_type if issue else "") or "",
        "summary": _thread_body(msgs)[:700],
        "chats": chats,
        "people": senders,
        "from": senders[0] if senders else "",
        "message_count": len(msgs),
    }


def cliq_digest(db: Session) -> dict:
    issues = {i.issue_key: i for i in list_active(db)}
    standup = db.query(Standup).order_by(Standup.id.desc()).first()
    if standup and standup.window_start and standup.window_end:
        start, end = standup.window_start, standup.window_end
    else:
        start, end = briefing_window().as_naive()
    messages = list(reversed(_cliq_in_window(db, start, end)))
    bugs: dict[str, list[CliqMessage]] = {}
    tasks: dict[str, list[CliqMessage]] = {}
    open_points: list[dict] = []
    for message in messages:
        keys = message.ticket_keys or extract_ticket_keys(message.message)
        if is_wallet_chat(message.chat_name):
            continue
        if keys:
            for key in keys:
                issue = issues.get(key)
                if is_bug_ticket(key, issue.issue_type if issue else ""):
                    bugs.setdefault(key, []).append(message)
                else:
                    tasks.setdefault(key, []).append(message)
            continue
        if is_pm_tagged(message.message) and len(re.sub(r"@\w+", "", resolve_text(message.message or "")).strip()) > 12:
            open_points.append(
                {
                    "from": name_for(message.sender_id, message.sender) or message.sender,
                    "chat": message.chat_name,
                    "summary": strip_jira_links(resolve_text(message.message))[:400],
                    "timestamp": message.timestamp.isoformat() if message.timestamp else None,
                }
            )
    return {
        "period": period_for(end),
        "headline": briefing_label(end),
        "window_label": f"{format_ist(start)} → {format_ist(end)}",
        "tasks": [_digest_item(key, msgs, issues.get(key)) for key, msgs in tasks.items()],
        "bugs": [_digest_item(key, msgs, issues.get(key)) for key, msgs in bugs.items()],
        "open_points": open_points[:20],
        "wallet_requests": [
            _digest_item("" if bucket.startswith("open-") else bucket, msgs, issues.get("" if bucket.startswith("open-") else bucket))
            for bucket, msgs in _group_wallet_messages(messages).items()
        ],
    }


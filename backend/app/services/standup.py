from datetime import datetime
import re

from sqlalchemy.orm import Session

from app.clients.llm import LLMClient
from app.models import Insight, JiraIssue, Standup
from app.repositories.issues import get_by_key, list_active
from app.services.filter import is_bug_ticket, strip_jira_links
from app.services.hidden import filter_sections, hidden_keys
from app.services.intelligence import context_payload
from app.services.jira_scope import is_aborted_status
from app.services.prompts import (
    evidence_not_enough,
    labeled_evidence,
    log_not_enough,
    parse_standup_items,
    parse_standup_sections,
    with_preamble,
)
from app.services.time_window import PERIOD_FOCUS, briefing_label, format_ist, period_for, week_range_label
from app.services.cliq_briefing import build_cliq_briefing
from app.services.week_actions import build_week_actions, insights_from_week_actions


SECTION_LIMIT = {
    "needs_attention": 6,
    "at_risk": 6,
    "completed": 6,
    "team_signals": 6,
    "todays_actions": 6,
    "bugs": 8,
    "tasks": 8,
    "wallet_requests": 8,
    "long_pending": 6,
}

BRIEFING_PROMPT = with_preamble(
    """Write the period-aware narrative briefing. Do NOT detect conflicts. Do NOT pick long_pending.

Period in the payload (morning|afternoon|evening|night). Follow focus.
Only use messages and changes inside the analysis window.

Your job:
1. Summarize OPEN Jira tickets that matter in this window (AC and PS).
2. Summarize OPEN Cliq points where Arsalaan is tagged (pm_tagged=true).
3. Combine Jira + Cliq into ONE item per ticket.
4. Put wallet-balance / wallet-recharge Cliq group requests into wallet_requests only.
5. Apply PM process from the payload (monday_plan, handoff developers) — do not invent extra process.

Sections to fill:
1. needs_attention — tagged open points with no ticket, blockers. Do not invent Conflict: titles.
2. at_risk
3. bugs — PS-* and Bug/Defect
4. tasks — AC Sense tickets that are not bugs
5. wallet_requests
7. completed
8. team_signals — untagged context only if it affects the PM
9. todays_actions — max 6, most urgent first, name a person when known

If jira_connected is false, say the Jira API is not connected. Unknown status is missing data, not a story.
Prefer pm_tagged messages. Ignore keyword-only noise unless tagged or a ticket key is present.
One combined item per ticket.

Item shape is authoritative. Every item MUST be:
{
  "title": "...",
  "body": "...",
  "action": "...",
  "action_type": "follow_up" | "investigate" | "review" | "confirm" | "escalate" | "decide" | "monitor",
  "confidence": "HIGH" | "MEDIUM" | "LOW",
  "issue_key": "AC-123" | "PS-123" | "",
  "flag": "open_point" | "ticket" | "wallet" | "",
  "why": "evidence explanation",
  "sources": [{"type":"cliq"|"jira","ref":"..."}]
}
action_type MUST be exactly one of those seven values. sources: 1-3 entries. type is exactly "cliq" or "jira".
If a field is unknown, omit the claim. Do not invent action_type values.

Return JSON only:
{
  "needs_attention": [item],
  "at_risk": [item],
  "bugs": [item],
  "tasks": [item],
  "wallet_requests": [item],
  "completed": [item],
  "team_signals": [item],
  "todays_actions": [item],
  "not_enough_evidence": ""
}
"""
)

ANALYTICS_PROMPT = with_preamble(
    """Analytical pass only. Two jobs: conflict flags, and long_pending triage.

Conflict: mismatched RCAs, contradictory owners, a chat explanation that disagrees with Jira.
Unknown Jira status is NOT a conflict. Missing fields are NOT a conflict.
Conflict titles MUST start with "Conflict:". flag MUST be "conflict".

long_pending: from board_snapshot, pick tickets that are both long-pending AND critical (age_days, stale_days, P1/high, aborted linked work, missing due date). Do not dump every old ticket. Only items you would escalate tonight. Max 6.

Return JSON only:
{
  "conflicts": [item],
  "long_pending": [item],
  "not_enough_evidence": ""
}

Item shape is the same as the briefing: title, body, action, action_type (exactly follow_up|investigate|review|confirm|escalate|decide|monitor), confidence HIGH|MEDIUM|LOW, issue_key, flag, why, sources (1-3, type cliq or jira).
"""
)



def _strip_jira_links(text: str) -> str:
    return strip_jira_links(text)


def _item_from_insight(insight: Insight) -> dict:
    sources = [
        {k: v for k, v in (source or {}).items() if k != "url"}
        for source in (insight.sources or [])
        if (source or {}).get("type") != "jira"
    ]
    return {
        "title": insight.title,
        "body": _strip_jira_links(insight.description),
        "action": insight.action,
        "action_type": insight.action_type,
        "confidence": insight.confidence,
        "issue_key": insight.issue_key,
        "board": "PS" if (insight.issue_key or "").upper().startswith("PS-") else "AC" if (insight.issue_key or "").upper().startswith("AC-") else "",
        "why": insight.why,
        "sources": sources,
    }


def _section_for(insight: Insight) -> str:
    if insight.type == "critical":
        return "long_pending"
    if insight.type == "wallet":
        return "wallet_requests"
    if insight.type == "blocker":
        return "needs_attention"
    if insight.type == "risk":
        return "at_risk"
    if insight.type == "completed":
        return "completed"
    if insight.type == "team_signal":
        return "team_signals"
    if (insight.title or "").startswith("Open point"):
        return "needs_attention"
    if insight.type == "bug" or is_bug_ticket(insight.issue_key or ""):
        return "bugs"
    if insight.type == "task" or (insight.issue_key or "").upper().startswith("AC-"):
        return "tasks"
    return "needs_attention"


def heuristic_standup(insights: list[Insight]) -> dict:
    sections = {key: [] for key in SECTION_LIMIT}
    ranked = sorted(
        insights,
        key=lambda i: ({"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(i.confidence, 3), i.type != "blocker"),
    )
    seen_actions = set()
    for insight in ranked:
        section = _section_for(insight)
        item = _item_from_insight(insight)
        if len(sections[section]) < SECTION_LIMIT[section]:
            sections[section].append(item)
        action_key = insight.action.strip().lower()
        if insight.action and action_key not in seen_actions and len(sections["todays_actions"]) < SECTION_LIMIT["todays_actions"]:
            if insight.confidence == "LOW":
                continue
            sections["todays_actions"].append(item)
            seen_actions.add(action_key)
    return sections


def generate_standup(
    db: Session,
    run_id: int,
    window_start: datetime,
    window_end: datetime,
    insights: list[Insight],
    period: str = "",
    headline: str = "",
) -> Standup:
    llm = LLMClient()
    sections = heuristic_standup(insights)
    period = period or period_for(window_end)
    headline = headline or briefing_label(window_end)
    llm_used = False
    evidence_note = ""
    if llm.configured:
        try:
            payload = context_payload(db, insights, window_start=window_start, window_end=window_end, period=period)
            blocks = labeled_evidence(payload)
            compact = {
                "period": payload.get("period"),
                "now": payload.get("now"),
                "focus": payload.get("focus"),
                "jira_connected": payload.get("jira_connected"),
                "jira_note": payload.get("jira_note"),
                "handoff_developers": payload.get("handoff_developers"),
                "monday_plan": payload.get("monday_plan"),
            }
            briefing = llm.complete_json(
                compact,
                system_prompt=BRIEFING_PROMPT,
                user_text=blocks,
                surface="standup_briefing",
                max_chars=28000,
            )
            parsed = parse_standup_sections(briefing, limits=SECTION_LIMIT)
            filled = 0
            for key in SECTION_LIMIT:
                if key in {"long_pending"}:
                    continue
                items = parsed.get(key) or []
                if items:
                    sections[key] = [_clean_item(item) for item in items][: SECTION_LIMIT[key]]
                    filled += 1
            llm_used = filled > 0
            evidence_note = evidence_not_enough(briefing)
            log_not_enough("standup_briefing", evidence_note)
        except Exception:
            llm_used = False
        try:
            payload = payload if "payload" in locals() else context_payload(
                db, insights, window_start=window_start, window_end=window_end, period=period
            )
            blocks = labeled_evidence(payload)
            analytics = llm.complete_json(
                {
                    "period": payload.get("period"),
                    "jira_connected": payload.get("jira_connected"),
                    "board_snapshot": payload.get("board_snapshot"),
                    "combined_tickets": payload.get("combined_tickets"),
                    "changes": payload.get("changes"),
                },
                system_prompt=ANALYTICS_PROMPT,
                user_text=blocks,
                surface="standup_analytics",
                max_chars=24000,
            )
            conflicts = parse_standup_items(analytics.get("conflicts") or [], limit=6)
            long_pending = parse_standup_items(analytics.get("long_pending") or [], limit=SECTION_LIMIT["long_pending"])
            if conflicts:
                attention = sections.setdefault("needs_attention", [])
                titles = {(item.get("title") or "").lower() for item in attention}
                for item in reversed(conflicts):
                    cleaned = _clean_item(item)
                    if not (cleaned.get("title") or "").lower().startswith("conflict"):
                        cleaned["title"] = f"Conflict: {cleaned.get('title') or 'mismatch'}"
                    cleaned["flag"] = "conflict"
                    if cleaned["title"].lower() in titles:
                        continue
                    attention.insert(0, cleaned)
                sections["needs_attention"] = attention[: SECTION_LIMIT["needs_attention"]]
            if long_pending:
                sections["long_pending"] = [_clean_item(item) for item in long_pending][: SECTION_LIMIT["long_pending"]]
                llm_used = True
            note_b = evidence_not_enough(analytics)
            log_not_enough("standup_analytics", note_b)
            evidence_note = evidence_note or note_b
        except Exception:
            pass
        if evidence_note and not any("not enough evidence" in (item.get("title") or "").lower() for item in (sections.get("needs_attention") or [])):
            sections.setdefault("needs_attention", [])
            if len(sections["needs_attention"]) < SECTION_LIMIT["needs_attention"]:
                sections["needs_attention"].append(
                    {
                        "title": "Not enough evidence",
                        "body": evidence_note,
                        "action": "",
                        "action_type": "monitor",
                        "confidence": "LOW",
                        "issue_key": "",
                        "why": evidence_note,
                        "sources": [],
                    }
                )
        if llm_used:
            _drop_false_conflicts(sections, insights)
            _keep_tagged_open_points(sections, insights)
            _keep_jira_disconnected(sections, insights)
            _keep_section_if_empty(sections, insights, "wallet_requests", lambda i: i.type == "wallet")
            _keep_section_if_empty(sections, insights, "long_pending", lambda i: i.type == "critical")
            _ensure_board_tickets(sections, insights)
    sections["todays_actions"] = (sections.get("todays_actions") or [])[: SECTION_LIMIT["todays_actions"]]
    sections = _drop_aborted_items(db, sections)
    sections = filter_sections(sections, hidden_keys(db))
    week = build_week_actions(db, window_end, insights)
    week_actions = filter_sections({"week_actions": week.get("week_actions") or []}, hidden_keys(db)).get("week_actions") or []
    this_week = filter_sections({"this_week": week.get("this_week") or []}, hidden_keys(db)).get("this_week") or []
    other_actions = filter_sections({"other_actions": week.get("other_actions") or []}, hidden_keys(db)).get("other_actions") or []
    sections["week_actions"] = week_actions
    sections["this_week"] = this_week
    sections["other_actions"] = other_actions
    if not sections.get("todays_actions"):
        sections["todays_actions"] = this_week[:6] or other_actions[:6]
    for extra in insights_from_week_actions(run_id, week):
        db.add(extra)
    try:
        cliq_briefing = build_cliq_briefing(db, window_start, window_end)
    except Exception:
        cliq_briefing = {}
    standup = Standup(
        run_id=run_id,
        window_start=window_start,
        window_end=window_end,
        needs_attention=sections["needs_attention"],
        at_risk=sections["at_risk"],
        completed=sections["completed"],
        team_signals=sections["team_signals"],
        todays_actions=sections["todays_actions"],
        bugs=sections["bugs"],
        tasks=sections["tasks"],
        wallet_requests=sections["wallet_requests"],
        long_pending=sections.get("long_pending") or [],
        week_actions=week_actions,
        this_week=this_week,
        other_actions=other_actions,
        cliq_briefing=cliq_briefing,
        dev_load=week.get("dev_load") or [],
        monday_plan=week.get("monday_plan") or {},
        raw_markdown=to_markdown(sections, window_start, window_end, period=period, headline=headline),
        llm_used=llm_used,
    )
    db.add(standup)
    db.commit()
    db.refresh(standup)
    return standup


def _clean_item(item: dict) -> dict:
    cleaned = dict(item or {})
    cleaned["body"] = _strip_jira_links(cleaned.get("body") or "")
    sources = []
    for source in cleaned.get("sources") or []:
        if not isinstance(source, dict):
            continue
        row = {k: v for k, v in source.items() if k != "url"}
        kind = (row.get("type") or "").lower()
        if kind not in {"cliq", "jira"}:
            continue
        row["type"] = kind
        sources.append(row)
        if len(sources) >= 3:
            break
    cleaned["sources"] = sources
    return cleaned


def _drop_aborted_items(db: Session, sections: dict) -> dict:
    aborted = {
        (issue.issue_key or "").upper()
        for issue in db.query(JiraIssue).all()
        if is_aborted_status(issue.status)
    }

    def keep(item: dict) -> bool:
        key = (item.get("issue_key") or "").upper()
        return not (key and key in aborted)

    return {
        name: [item for item in items if keep(item)] if isinstance(items, list) else items
        for name, items in sections.items()
    }


def _keep_section_if_empty(sections: dict, insights: list[Insight], key: str, match) -> None:
    if sections.get(key):
        return
    items = [_item_from_insight(insight) for insight in insights if match(insight)]
    sections[key] = items[: SECTION_LIMIT.get(key, 8)]


def _ensure_board_tickets(sections: dict, insights: list[Insight]) -> None:
    for dest in ("bugs", "tasks", "long_pending"):
        bucket = sections.setdefault(dest, [])
        existing = {(item.get("issue_key") or "") for item in bucket}
        for insight in insights:
            if _section_for(insight) != dest:
                continue
            key = insight.issue_key or ""
            if key and key in existing:
                continue
            if len(bucket) >= SECTION_LIMIT[dest]:
                break
            bucket.append(_item_from_insight(insight))
            existing.add(key)


def _drop_false_conflicts(sections: dict, insights: list[Insight]) -> None:
    confirmed = {i.issue_key for i in insights if i.issue_key and i.title.lower().startswith("conflict")}
    for items in sections.values():
        if not isinstance(items, list):
            continue
        for item in items:
            title = item.get("title") or ""
            if not title.lower().startswith("conflict"):
                continue
            key = item.get("issue_key") or ""
            if key in confirmed:
                item["flag"] = "conflict"
                continue
            item["title"] = title.split(":", 1)[-1].strip()
            item["flag"] = item.get("flag") if item.get("flag") != "conflict" else ""


def _keep_tagged_open_points(sections: dict, insights: list[Insight]) -> None:
    attention = sections.setdefault("needs_attention", [])
    existing_titles = {(item.get("title") or "").lower() for item in attention}
    existing_bodies = {(item.get("body") or "")[:60].lower() for item in attention}
    for insight in insights:
        if not insight.title.startswith("Open point"):
            continue
        if insight.title.lower() in existing_titles:
            continue
        if (insight.description or "")[:60].lower() in existing_bodies:
            continue
        attention.append(_item_from_insight(insight))
        existing_titles.add(insight.title.lower())


def _keep_jira_disconnected(sections: dict, insights: list[Insight]) -> None:
    attention = sections.setdefault("needs_attention", [])
    if any("jira api is not connected" in (item.get("title") or "").lower() for item in attention):
        return
    for insight in insights:
        if insight.title.startswith("Jira API is not connected"):
            attention.insert(0, _item_from_insight(insight))
            return


def to_markdown(sections: dict, window_start: datetime, window_end: datetime, period: str = "", headline: str = "") -> str:
    period = period or period_for(window_end)
    headline = headline or briefing_label(window_end)
    focus = PERIOD_FOCUS.get(period, "")
    lines = [
        f"{headline} · {format_ist(window_end)}",
        f"Window {format_ist(window_start)} → {format_ist(window_end)}",
        f"Week {week_range_label(window_end)}",
        focus,
        "",
        "📌 This week from #product-internal",
    ]
    _section_lines(lines, sections.get("this_week") or [])
    lines += ["", "🗂️ Other work"]
    _section_lines(lines, sections.get("other_actions") or [])
    lines += ["", "🔴 Needs Attention"]
    _section_lines(lines, sections.get("needs_attention") or [])
    lines += ["", "🟡 At Risk"]
    _section_lines(lines, sections.get("at_risk") or [])
    lines += ["", "⚠️ Long pending · critical"]
    _section_lines(lines, sections.get("long_pending") or [])
    lines += ["", "🐞 Bugs · Product Support"]
    _section_lines(lines, sections.get("bugs") or [])
    lines += ["", "✅ Tasks · Sense"]
    _section_lines(lines, sections.get("tasks") or [])
    lines += ["", "💳 Wallet-balance requests"]
    _section_lines(lines, sections.get("wallet_requests") or [])
    lines += ["", "🟢 Completed"]
    _section_lines(lines, sections.get("completed") or [])
    lines += ["", "💬 Team Signals"]
    _section_lines(lines, sections.get("team_signals") or [])
    lines += ["", "🎯 Today's Actions"]
    _section_lines(lines, sections.get("todays_actions") or [])
    return "\n".join(lines)


def _section_lines(lines: list[str], items: list[dict]) -> None:
    if not items:
        lines.append("None identified from available evidence.")
        return
    for item in items:
        conf = item.get("confidence") or "MEDIUM"
        lines.append(f"- [{conf}] {item.get('title')}")
        if item.get("body"):
            lines.append(f"  {item['body']}")
        if item.get("action"):
            lines.append(f"  Action: {item['action']}")
        if item.get("why"):
            lines.append(f"  Why: {item['why']}")
        sources = item.get("sources") or []
        if sources:
            refs = ", ".join(f"{s.get('type')}:{s.get('ref')}" for s in sources if s.get("ref"))
            lines.append(f"  Sources: {refs}")


def _flatten_items(standup: Standup | None) -> list[dict]:
    if not standup:
        return []
    rows: list[dict] = []
    for bucket in (
        standup.needs_attention,
        standup.at_risk,
        standup.completed,
        standup.team_signals,
        standup.todays_actions,
        standup.bugs,
        standup.tasks,
        standup.wallet_requests,
        standup.long_pending,
        getattr(standup, "this_week", None),
        getattr(standup, "other_actions", None),
        getattr(standup, "week_actions", None),
    ):
        for item in bucket or []:
            if isinstance(item, dict):
                rows.append(item)
    return rows


def _score_text(query: str, *parts: str) -> int:
    tokens = [token for token in re.findall(r"[a-z0-9]{2,}", (query or "").lower()) if token not in {"the", "and", "for", "with"}]
    if not tokens:
        return 0
    hay = " ".join(str(part or "") for part in parts).lower()
    return sum(3 if token in hay else 0 for token in tokens) + (8 if (query or "").lower() in hay else 0)


def _snippet(hay: str, query: str, limit: int = 160) -> str:
    text = re.sub(r"\s+", " ", hay or "").strip()
    if not text:
        return ""
    needle = (query or "").strip()
    if not needle:
        return text[:limit]
    lower = text.lower()
    at = lower.find(needle.lower())
    if at < 0:
        return text[:limit]
    start = max(0, at - 40)
    chunk = text[start : start + limit]
    return ("…" if start else "") + chunk


def _with_why(item: dict, why: str, snippet: str = "") -> dict:
    row = dict(item)
    row["why"] = why
    if snippet:
        row["snippet"] = snippet
    return row


def answer_command(standup: Standup | None, command: str, db: Session) -> dict:
    from app.models import CliqMessage

    query = (command or "").strip()
    text = query.lower()
    if not query:
        return {"answer": "Search tickets, people, or blockers.", "items": []}
    key_match = re.search(r"\b([A-Z][A-Z0-9]+-\d+)\b", query, re.I)
    if key_match and re.fullmatch(r"\s*[A-Z][A-Z0-9]+-\d+\s*", query, re.I):
        key = key_match.group(1).upper()
        issue = get_by_key(db, key, include_archived=True)
        msgs = db.query(CliqMessage).filter(CliqMessage.message.ilike(f"%{key}%")).all()
        items = []
        if issue:
            items.append(
                _with_why(
                    {
                        "title": f"{issue.issue_key}: {issue.summary}",
                        "body": f"Status {issue.status or 'Unknown'}, priority {issue.priority or 'Unknown'}, assignee {issue.assignee or 'Unknown'}",
                        "issue_key": issue.issue_key,
                        "sources": [{"type": "jira", "ref": issue.issue_key, "url": issue.url}],
                        "confidence": "HIGH",
                    },
                    f"Ticket key {key}",
                    issue.summary or "",
                )
            )
        for msg in msgs[:8]:
            items.append(
                _with_why(
                    {
                        "title": f"Cliq · {msg.chat_name}",
                        "body": msg.message,
                        "issue_key": key,
                        "sources": [{"type": "cliq", "ref": msg.chat_name, "chat_id": msg.chat_id}],
                        "confidence": "HIGH",
                    },
                    f"linked via mention of {key} in {msg.chat_name or 'Cliq'}",
                    _snippet(msg.message or "", key),
                )
            )
        ticket_count = len(list_active(db))
        return {
            "answer": (f"Evidence related to {key}." if items else f"No stored evidence for {key}.") + f" Searched {ticket_count} tickets.",
            "items": items,
            "searched": ticket_count,
        }
    if standup:
        if "block" in text:
            items = [i for i in (standup.needs_attention or []) if "block" in (i.get("title") or "").lower() or "block" in (i.get("body") or "").lower()]
            return {"answer": "Current blockers from the latest briefing.", "items": items or (standup.needs_attention or [])}
        if "risk" in text:
            return {"answer": "Work currently at risk.", "items": standup.at_risk or []}
        if "changed" in text or "yesterday" in text:
            return {"answer": "Important changes in the analysis window.", "items": (standup.needs_attention or []) + (standup.completed or [])}
        if "focus" in text or (text == "today"):
            return {"answer": "Recommended focus for today.", "items": standup.todays_actions or []}

    scored: list[tuple[int, dict]] = []
    for item in _flatten_items(standup):
        score = _score_text(query, item.get("title") or "", item.get("body") or "", item.get("issue_key") or "", item.get("action") or "")
        if score:
            scored.append((score, item))
    issues = list_active(db)
    searched = len(issues)
    for issue in issues:
        extras = issue.extra_json or {}
        score = _score_text(query, issue.issue_key, issue.summary, issue.assignee, issue.status, issue.description or "", extras.get("parent_key") or "")
        if not score:
            continue
        scored.append(
            (
                score + 2,
                _with_why(
                    {
                        "title": f"{issue.issue_key}: {issue.summary}",
                        "body": f"Status {issue.status or 'Unknown'}, {issue.assignee or 'unassigned'}",
                        "issue_key": issue.issue_key,
                        "sources": [{"type": "jira", "ref": issue.issue_key, "url": issue.url}],
                        "confidence": "HIGH",
                    },
                    f"Matched {issue.issue_key} summary/status",
                    _snippet(f"{issue.issue_key} {issue.summary} {issue.description or ''}", query),
                ),
            )
        )
    needle = f"%{query[:80]}%"
    for msg in db.query(CliqMessage).filter(CliqMessage.message.ilike(needle)).order_by(CliqMessage.timestamp.desc()).limit(12).all():
        keys = msg.ticket_keys or []
        why = f"linked via mention of {keys[0]} in {msg.chat_name}" if keys else f"Matched text in {msg.chat_name or 'Cliq'}"
        scored.append(
            (
                4,
                _with_why(
                    {
                        "title": f"Cliq · {msg.chat_name}",
                        "body": msg.message,
                        "sources": [{"type": "cliq", "ref": msg.chat_name, "chat_id": msg.chat_id}],
                        "confidence": "MEDIUM",
                    },
                    why,
                    _snippet(msg.message or "", query),
                ),
            )
        )
    scored.sort(key=lambda row: row[0], reverse=True)
    seen: set[str] = set()
    items = []
    for _, item in scored:
        stamp = f"{item.get('issue_key') or ''}|{item.get('title') or ''}"
        if stamp in seen:
            continue
        seen.add(stamp)
        items.append(item)
        if len(items) >= 12:
            break
    if not items:
        return {"answer": f"No matches for “{query}”. Searched {searched} tickets.", "items": [], "searched": searched}
    return {"answer": f"{len(items)} matches for “{query}”. Searched {searched} tickets.", "items": items, "searched": searched}

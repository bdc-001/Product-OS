"""Cliq briefing: chats Arsalaan was in, follow-ups, promises, unanswered."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.clients.llm import LLMClient
from app.models import CliqMessage, Standup
from app.services.filter import is_product_internal_chat, is_wallet_chat, strip_jira_links
from app.services.people import is_pm_sender, is_pm_tagged, name_for, resolve_text
from app.services.prompts import with_preamble
from app.services.time_window import briefing_window, format_ist, timestamp_in_window, to_utc_naive

NOISE_CHATS = (
    "health-check-report",
    "flow-processing-check-report",
    "healthcheck",
)
PROMISE_RE = re.compile(
    r"\b(i['’]?ll|i will|let me|will (check|update|do|send|look|share|confirm|assign|get)|"
    r"checking|on it|will do|kal|tomorrow|eod|by tonight|follow up)\b",
    re.I,
)
TOMORROW_RE = re.compile(r"\b(tomorrow|kal|next working day|monday|follow up)\b", re.I)
SECRET_RE = re.compile(
    r"(client secret|access token|api[_-]?key|password|atatt[A-Za-z0-9_\-]{16,}|[a-f0-9]{40,})",
    re.I,
)
TOKENISH_RE = re.compile(r"^[A-Za-z0-9._\-=]{36,}$")

CLIQ_PROMPT = with_preamble(
    """Categorize HIS Cliq work. Use only the provided messages.
Never invent people, promises, or tickets. Never quote secrets, tokens, client ids, or passwords.

Return JSON:
{
  "conversations": [{"chat": "...", "summary": "one line of what Arsalaan did in this chat", "people": ["..."]}],
  "follow_up_tomorrow": [{"title": "...", "body": "...", "action": "...", "chat": "...", "people": ["..."], "why": "..."}],
  "promises": [{"title": "...", "body": "...", "action": "what Arsalaan still owes", "chat": "...", "people": ["..."], "why": "..."}],
  "unanswered": [{"title": "...", "body": "what they asked", "action": "reply to NAME", "chat": "...", "people": ["..."], "why": "no reply from Arsalaan after this"}],
  "not_enough_evidence": ""
}

Rules:
- conversations: only chats Arsalaan actually wrote in. One card per chat. Skip system report channels.
- follow_up_tomorrow: things he should pick up tomorrow (he said tomorrow, or an open loop that carries overnight).
- promises: he committed to someone (I'll / I will / checking / will assign) and it still looks open.
- unanswered: someone wrote to him or tagged him and he has not addressed it.
- If a heuristic item is noise, drop it. Do not add items without evidence in the payload.
- Keep each body under 280 characters.
"""
)


def _noisy_chat(name: str) -> bool:
    compact = re.sub(r"[^a-z0-9]", "", (name or "").lower())
    return any(token.replace("-", "") in compact for token in NOISE_CHATS)


def _looks_secret(text: str) -> bool:
    if SECRET_RE.search(text or ""):
        return True
    compact = re.sub(r"\s", "", text or "")
    return bool(TOKENISH_RE.match(compact))


def _safe_text(text: str) -> str:
    cleaned = resolve_text(strip_jira_links(text or ""))
    if _looks_secret(cleaned):
        return "[redacted]"
    return cleaned


def _card_key(title: str, chat: str, body: str = "", timestamp: str | None = None) -> str:
    blob = f"{chat}|{title}|{timestamp or ''}|{(body or '')[:80]}"
    digest = hashlib.sha1(blob.encode("utf-8", errors="ignore")).hexdigest()[:20]
    return f"cliq:{digest}"


def _item(title: str, body: str, action: str, chat: str, people: list[str], why: str, timestamp: str | None = None) -> dict:
    return {
        "title": title,
        "body": body[:400],
        "action": action,
        "chat": chat,
        "people": people,
        "why": why,
        "summary": body[:400],
        "timestamp": timestamp,
        "card_key": _card_key(title, chat, body, timestamp),
    }


def heuristic_cliq_briefing(db: Session, window_start: datetime | None = None, window_end: datetime | None = None) -> dict:
    if window_start and window_end:
        start, end = window_start, window_end
    else:
        standup = db.query(Standup).order_by(Standup.id.desc()).first()
        if standup and standup.window_start and standup.window_end:
            start, end = standup.window_start, standup.window_end
        else:
            start, end = briefing_window().as_naive()

    utc_start, utc_end = to_utc_naive(start), to_utc_naive(end)
    start_naive = start.replace(tzinfo=None) if start.tzinfo else start
    end_naive = end.replace(tzinfo=None) if end.tzinfo else end
    lo = min(utc_start, start_naive)
    hi = max(utc_end, end_naive)
    rows = (
        db.query(CliqMessage)
        .filter(CliqMessage.timestamp.isnot(None), CliqMessage.timestamp.between(lo, hi))
        .order_by(CliqMessage.timestamp.asc())
        .all()
    )
    messages = [
        m
        for m in rows
        if timestamp_in_window(m.timestamp, start, end)
        and not _noisy_chat(m.chat_name)
        and not is_wallet_chat(m.chat_name)
        and not is_product_internal_chat(m.chat_name, m.chat_id)
        and not _looks_secret(m.message or "")
    ]
    stale = False
    if not messages:
        wider_start = end - timedelta(days=3)
        wider_utc = to_utc_naive(wider_start)
        wider_naive = wider_start.replace(tzinfo=None) if wider_start.tzinfo else wider_start
        wider_lo = min(wider_utc, wider_naive, lo)
        rows = (
            db.query(CliqMessage)
            .filter(CliqMessage.timestamp.isnot(None), CliqMessage.timestamp.between(wider_lo, hi))
            .order_by(CliqMessage.timestamp.asc())
            .all()
        )
        messages = [
            m
            for m in rows
            if timestamp_in_window(m.timestamp, wider_start, end)
            and not _noisy_chat(m.chat_name)
            and not is_wallet_chat(m.chat_name)
            and not is_product_internal_chat(m.chat_name, m.chat_id)
            and not _looks_secret(m.message or "")
        ]
        if messages:
            stale = True
            start = wider_start

    by_chat: dict[str, list[CliqMessage]] = {}
    for message in messages:
        by_chat.setdefault(message.chat_name or "Cliq", []).append(message)

    conversations = []
    promises = []
    follow_up = []
    unanswered = []

    for chat, thread in by_chat.items():
        pm_msgs = [m for m in thread if is_pm_sender(m.sender_id, m.sender)]
        if pm_msgs:
            people = []
            for m in thread:
                who = name_for(m.sender_id, m.sender) or m.sender
                if who and who not in people and not is_pm_sender(m.sender_id, m.sender):
                    people.append(who)
            last = pm_msgs[-1]
            snippets = [text for text in (_safe_text(m.message) for m in pm_msgs[-3:]) if text]
            conversations.append(
                _item(
                    title=chat,
                    body=" · ".join(snippets)[:400] or _safe_text(last.message),
                    action="",
                    chat=chat,
                    people=people[:6],
                    why=f"{len(pm_msgs)} messages from you in this chat.",
                    timestamp=last.timestamp.isoformat() if last.timestamp else None,
                )
            )
            for m in pm_msgs:
                text = m.message or ""
                if not PROMISE_RE.search(text):
                    continue
                others = [p for p in people[:4]]
                who = ", ".join(others) if others else "this chat"
                card = _item(
                    title=f"You promised in {chat}",
                    body=_safe_text(text),
                    action=f"Close the loop with {who}",
                    chat=chat,
                    people=others,
                    why="Your message reads as a commitment.",
                    timestamp=m.timestamp.isoformat() if m.timestamp else None,
                )
                if TOMORROW_RE.search(text):
                    card["title"] = f"Follow up tomorrow · {chat}"
                    card["action"] = f"Follow up with {who} tomorrow"
                    follow_up.append(card)
                else:
                    promises.append(card)

        last = thread[-1]
        if last and not is_pm_sender(last.sender_id, last.sender) and (pm_msgs or is_pm_tagged(last.message or "") or not (chat or "").startswith("#")):
            who = name_for(last.sender_id, last.sender) or last.sender or "someone"
            unanswered.append(
                _item(
                    title=f"Unanswered · {who}",
                    body=_safe_text(last.message),
                    action=f"Reply to {who} in {chat}",
                    chat=chat,
                    people=[who],
                    why="The last message in this chat is not from you.",
                    timestamp=last.timestamp.isoformat() if last.timestamp else None,
                )
            )

    return {
        "window_label": f"{format_ist(start)} → {format_ist(end)}",
        "stale": stale,
        "conversations": conversations[-20:],
        "follow_up_tomorrow": follow_up[:12],
        "promises": promises[:12],
        "unanswered": unanswered[:12],
    }


def llm_refine_cliq(heuristic: dict) -> dict:
    llm = LLMClient()
    if not llm.configured:
        return heuristic
    slim = {
        "conversations": heuristic.get("conversations") or [],
        "follow_up_tomorrow": heuristic.get("follow_up_tomorrow") or [],
        "promises": heuristic.get("promises") or [],
        "unanswered": heuristic.get("unanswered") or [],
    }
    try:
        generated = llm.complete_json(slim, system_prompt=CLIQ_PROMPT, max_chars=16000, surface="cliq")
    except Exception:
        return heuristic
    out = dict(heuristic)
    for key in ("conversations", "follow_up_tomorrow", "promises", "unanswered"):
        rows = generated.get(key)
        if not isinstance(rows, list):
            continue
        if not rows and heuristic.get(key):
            continue
        cleaned = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            if _looks_secret(str(row.get("body") or "") + str(row.get("summary") or "")):
                continue
            cleaned.append(
                {
                    "title": row.get("title") or row.get("chat") or key,
                    "body": row.get("body") or row.get("summary") or "",
                    "summary": row.get("summary") or row.get("body") or "",
                    "action": row.get("action") or "",
                    "chat": row.get("chat") or "",
                    "people": row.get("people") or [],
                    "why": row.get("why") or "",
                    "timestamp": row.get("timestamp") or "",
                    "card_key": _card_key(
                        row.get("title") or row.get("chat") or key,
                        row.get("chat") or "",
                        row.get("body") or row.get("summary") or "",
                        row.get("timestamp") or "",
                    ),
                }
            )
        out[key] = cleaned
    return out


def filter_cliq_briefing(briefing: dict | None, hidden: set[str]) -> dict:
    payload = dict(briefing or {})
    for key in ("conversations", "follow_up_tomorrow", "promises", "unanswered"):
        rows = []
        for item in payload.get(key) or []:
            if not isinstance(item, dict):
                continue
            row = dict(item)
            if not (row.get("card_key") or "").strip():
                row["card_key"] = _card_key(
                    row.get("title") or row.get("chat") or key,
                    row.get("chat") or "",
                    row.get("body") or row.get("summary") or "",
                    row.get("timestamp") or "",
                )
            title_key = f"title:{(row.get('title') or '').strip().lower()[:160]}"
            if row["card_key"] in hidden or title_key in hidden:
                continue
            rows.append(row)
        payload[key] = rows
    payload["stale"] = bool(payload.get("stale"))
    payload["ingest_error"] = payload.get("ingest_error") or ""
    return payload


def build_cliq_briefing(db: Session, window_start: datetime | None = None, window_end: datetime | None = None) -> dict:
    heuristic = heuristic_cliq_briefing(db, window_start, window_end)
    return llm_refine_cliq(heuristic)

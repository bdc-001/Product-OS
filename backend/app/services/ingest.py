from datetime import datetime
from time import sleep

from sqlalchemy.orm import Session

from app.clients.cliq import CliqClient
from app.clients.jira import JiraClient
from app.config import settings
from app.models import CliqChat, CliqMessage, JiraIssue
from app.repositories.issues import apply_normalized
from app.services.filter import classify_message, extract_ticket_keys, is_product_internal_chat, is_wallet_chat
from app.services.people import name_for
from app.services.team import product_internal_chat_id, PRODUCT_INTERNAL_NAME
from app.services.time_window import jira_jql_date, to_millis, week_monday
from app.services.week_plan import planned_tasks_from_db, unmatched_search_phrases


def _upsert_issues(db: Session, client: JiraClient, raw_issues: list[dict], kept: set[str]) -> int:
    count = 0
    for raw in raw_issues:
        data = client.normalize(raw)
        existing = db.query(JiraIssue).filter(JiraIssue.issue_key == data["issue_key"]).one_or_none()
        apply_normalized(existing, data, db)
        kept.add(data["issue_key"])
        count += 1
    return count


def ingest_jira(db: Session, window_start: datetime) -> int:
    client = JiraClient()
    if not client.configured:
        return 0
    failures: list[str] = []

    def _fetch(label: str, fn):
        try:
            return fn() or []
        except Exception as exc:
            failures.append(f"{label}: {exc}")
            print(f"jira {label} fetch failed: {exc}")
            return []

    raw_issues = _fetch("open-board", client.fetch_open_board_issues)
    seen = {(issue.get("key") or "") for issue in raw_issues}
    recent = _fetch("recent", lambda: client.fetch_pm_issues(updated_since=jira_jql_date(window_start)))
    for issue in recent:
        key = issue.get("key") or ""
        if key and key not in seen:
            raw_issues.append(issue)
            seen.add(key)
    workflow = _fetch("workflow", client.fetch_pm_workflow_issues)
    for issue in workflow:
        key = issue.get("key") or ""
        if key and key not in seen:
            raw_issues.append(issue)
            seen.add(key)
    mentioned = set()
    for message in db.query(CliqMessage).all():
        mentioned.update(message.ticket_keys or extract_ticket_keys(message.message or ""))
    plan = planned_tasks_from_db(db, window_start)
    for task in plan.get("tasks") or []:
        mentioned.update(task.get("keys") or [])
        if task.get("issue_key"):
            mentioned.add(task["issue_key"])
    missing = [key for key in mentioned if key and key not in seen]
    if missing:
        try:
            extra = client.fetch_by_keys(missing, scoped=False)
        except Exception:
            extra = []
        for issue in extra:
            key = issue.get("key") or ""
            if key and key not in seen:
                raw_issues.append(issue)
                seen.add(key)
    for phrase in unmatched_search_phrases(plan):
        try:
            hits = client.fetch_summary_matches(phrase)
        except Exception:
            hits = []
        for issue in hits:
            key = issue.get("key") or ""
            if key and key not in seen:
                raw_issues.append(issue)
                seen.add(key)
    kept: set[str] = set()
    count = _upsert_issues(db, client, raw_issues, kept)
    if not kept:
        if failures:
            raise RuntimeError("Jira pulled nothing. " + "; ".join(failures)[:700])
        active = db.query(JiraIssue).filter(JiraIssue.archived_at.is_(None)).count()
        if active:
            print("jira returned 0 issues; leaving the existing board in place")
            return active
        db.commit()
        return 0
    board_failed = any(item.startswith("open-board:") for item in failures)
    if not board_failed:
        now = datetime.utcnow()
        for existing in list(db.query(JiraIssue).all()):
            if existing.issue_key in kept:
                continue
            if existing.archived_at is None:
                existing.archived_at = now
    db.commit()
    return count


def _cliq_error(exc: Exception) -> str:
    text = str(exc)
    if "401" in text:
        return "Cliq login expired. Add a fresh CLIQ_ACCESS_TOKEN, and CLIQ_REFRESH_TOKEN so Refresh can renew it."
    if "UNEXPECTED_EOF" in text or "EOF occurred in violation of protocol" in text:
        return "Cliq closed the TLS connection. Refresh again — this is usually a brief Zoho drop, not a bad token."
    return f"Cliq fetch failed: {text[:240]}"


def ingest_cliq(db: Session, window_start: datetime, window_end: datetime) -> tuple[int, int, str]:
    client = CliqClient()
    if not client.configured:
        return 0, 0, "Cliq is not configured."
    try:
        chats = client.list_chats(modified_after_ms=to_millis(window_start), limit=100)
    except Exception as exc:
        chats = []
        list_error = _cliq_error(exc)
    else:
        list_error = ""
    try:
        channels = client.list_channels(limit=50)
    except Exception:
        channels = []
    seen_ids = {c.get("chat_id") or c.get("id") for c in chats}
    for channel in channels:
        cid = channel.get("chat_id") or channel.get("id") or channel.get("channel_id")
        if cid and cid not in seen_ids:
            chats.append(channel)
            seen_ids.add(cid)
    if not chats:
        chats = [{"chat_id": chat.chat_id, "name": chat.name} for chat in db.query(CliqChat).all()]

    pinned = []
    rest = []
    seen_ids = {c.get("chat_id") or c.get("id") for c in chats}
    for raw_chat in chats:
        name = (raw_chat.get("name") or raw_chat.get("title") or raw_chat.get("channelname") or "")
        cid = str(raw_chat.get("chat_id") or raw_chat.get("id") or raw_chat.get("channel_id") or "")
        if is_wallet_chat(name) or is_product_internal_chat(name, cid):
            pinned.append(raw_chat)
        else:
            rest.append(raw_chat)

    for chat in db.query(CliqChat).all():
        if chat.chat_id in seen_ids:
            continue
        if is_wallet_chat(chat.name) or is_product_internal_chat(chat.name, chat.chat_id):
            pinned.append({"chat_id": chat.chat_id, "name": chat.name})
            seen_ids.add(chat.chat_id)

    pinned_id = product_internal_chat_id()
    if pinned_id not in seen_ids:
        pinned.insert(0, {"chat_id": pinned_id, "name": PRODUCT_INTERNAL_NAME})
        seen_ids.add(pinned_id)

    selected = pinned + rest[: settings.max_cliq_chats]

    message_count = 0
    relevant_count = 0
    chat_errors: list[str] = []
    monday_ms = to_millis(week_monday(window_end))
    fromtime = to_millis(window_start)
    totime = to_millis(window_end)

    for raw_chat in selected:
        chat = client.normalize_chat(raw_chat)
        if not chat["chat_id"]:
            continue
        existing = db.query(CliqChat).filter(CliqChat.chat_id == chat["chat_id"]).one_or_none()
        if existing:
            existing.name = chat["name"]
            existing.chat_type = chat["chat_type"]
            existing.last_modified = chat["last_modified"]
            existing.raw = chat["raw"]
        else:
            db.add(CliqChat(**chat))
        chat_from = monday_ms if is_product_internal_chat(chat["name"], chat["chat_id"]) else fromtime
        try:
            messages = client.get_messages(
                chat["chat_id"],
                fromtime_ms=chat_from,
                totime_ms=totime,
                limit=settings.max_messages_per_chat,
            )
        except Exception as exc:
            chat_errors.append(_cliq_error(exc))
            continue
        sleep(0.35)
        for raw_msg in messages:
            msg = client.normalize_message(chat, raw_msg)
            if not msg["message"]:
                continue
            if not msg["message_id"]:
                stamp = msg["timestamp"].isoformat() if msg["timestamp"] else "na"
                msg["message_id"] = f"{msg['chat_id']}:{stamp}:{msg['sender']}:{msg['message'][:40]}"
            relevance = classify_message(msg["message"], chat["name"], sender_id=msg.get("sender_id"), sender=msg.get("sender"))
            msg["sender"] = name_for(msg.get("sender_id"), msg.get("sender") or "") or msg.get("sender") or ""
            msg["relevant"] = relevance["relevant"]
            msg["relevance_reasons"] = relevance["reasons"]
            msg["ticket_keys"] = relevance["ticket_keys"]
            prior = (
                db.query(CliqMessage)
                .filter(CliqMessage.chat_id == msg["chat_id"], CliqMessage.message_id == msg["message_id"])
                .one_or_none()
            )
            if prior:
                for key, value in msg.items():
                    setattr(prior, key, value)
            else:
                db.add(CliqMessage(**msg))
            message_count += 1
            if msg["relevant"]:
                relevant_count += 1
    db.commit()
    if message_count:
        return message_count, relevant_count, ""
    return message_count, relevant_count, list_error or (chat_errors[0] if chat_errors else "")

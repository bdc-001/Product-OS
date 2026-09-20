"""AC Task tickets Released under Lalit / Vidhya, and the Cliq nudge to write notes."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from app.clients.cliq import CliqClient
from app.clients.jira import JiraClient
from app.config import ROOT, settings
from app.services.profile import load_profile
from app.services.team import NOTES_PMS, PRODUCT_INTERNAL_NAME, match_notes_pm
from app.services.time_window import now_local, tz

LOOKBACK_DAYS = 30
QUEUE_START = "2026-09-07"
STORES_DIR = ROOT / "data" / "stores"
_DEFAULT_STATE_PATH = ROOT / "data" / "release_asks.json"
STATE_PATH = _DEFAULT_STATE_PATH


def lookback_start(now: datetime | None = None) -> str:
    current = now or now_local()
    if current.tzinfo is None:
        current = current.replace(tzinfo=tz())
    return (current.date() - timedelta(days=LOOKBACK_DAYS)).isoformat()


def store_slug(branch: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", (branch or "").strip()).strip("-") or "branch"


def data_branch_name() -> str:
    return str(load_profile().get("data_branch") or "").strip()


def state_file() -> Path:
    if Path(STATE_PATH) != Path(_DEFAULT_STATE_PATH):
        return Path(STATE_PATH)
    branch = data_branch_name()
    if not branch:
        return Path(_DEFAULT_STATE_PATH)
    return STORES_DIR / store_slug(branch) / "release_asks.json"


def queue_after_date(now: datetime | None = None, state: dict | None = None) -> str:
    lookback = lookback_start(now)
    payload = state if state is not None else _state()
    floor = str(payload.get("queue_start") or QUEUE_START)
    return max(lookback, floor)


def parse_jira_dt(value) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if re.search(r"[+-]\d{4}$", text):
        text = text[:-5] + text[-5:-2] + ":" + text[-2:]
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz())
    return parsed.astimezone(tz())


def ist_date(value) -> str:
    parsed = parse_jira_dt(value)
    if parsed:
        return parsed.date().isoformat()
    text = str(value or "").strip()
    return text[:10] if re.match(r"\d{4}-\d{2}-\d{2}", text) else ""


def format_release_day(day: str) -> str:
    try:
        return datetime.strptime(day[:10], "%Y-%m-%d").strftime("%d %b %Y").lstrip("0")
    except ValueError:
        return day


def released_on(changelog: list | None, extras: dict | None, updated_at=None) -> str:
    days: list[str] = []
    for item in changelog or []:
        if (item.get("field") or "").strip().lower() != "status":
            continue
        if (item.get("to") or "").strip().lower() != "released":
            continue
        day = ist_date(item.get("created") or "")
        if day:
            days.append(day)
    if days:
        return min(days)
    extras = extras or {}
    for key in ("resolution_date", "resolutiondate"):
        day = ist_date(extras.get(key) or "")
        if day:
            return day
    return ""


def classify_released_task(data: dict, after_date: str) -> dict | None:
    key = (data.get("issue_key") or "").upper()
    if not key.startswith("AC-"):
        return None
    if (data.get("issue_type") or "").strip().lower() != "task":
        return None
    if (data.get("status") or "").strip().lower() != "released":
        return None
    extras = data.get("extra_json") or {}
    person = match_notes_pm(extras.get("product_manager") or "")
    if not person:
        return None
    day = released_on(data.get("changelog_json") or [], extras, data.get("updated_at"))
    if not day or day < after_date:
        return None
    return {
        "issue_key": key,
        "summary": (data.get("summary") or "").strip(),
        "status": "Released",
        "issue_type": "Task",
        "released_on": day,
        "released_label": format_release_day(day),
        "url": data.get("url") or f"{settings.jira_base_url.rstrip('/')}/browse/{key}",
        "pm": person["short"],
        "email": person.get("email") or "",
        "cliq_user_id": person.get("cliq_user_id") or "",
    }


def collect_release_asks(normalized: list[dict], after_date: str) -> list[dict]:
    by_pm: dict[str, list[dict]] = {person["short"]: [] for person in NOTES_PMS}
    for data in normalized:
        ticket = classify_released_task(data, after_date)
        if not ticket:
            continue
        by_pm[ticket["pm"]].append(ticket)
    groups = []
    for person in NOTES_PMS:
        tickets = sorted(by_pm[person["short"]], key=lambda row: (row["released_on"], row["issue_key"]), reverse=True)
        if not tickets:
            continue
        groups.append(
            {
                "pm": person["short"],
                "email": person.get("email") or "",
                "cliq_user_id": person.get("cliq_user_id") or "",
                "cliq_chat_id": person.get("cliq_chat_id") or "",
                "tickets": tickets,
            }
        )
    return groups


def _fresh_state() -> dict:
    return {
        "queue_start": QUEUE_START,
        "dismissed": [],
        "by_pm": {},
        "last_nudged_at": "",
        "sent": [],
        "data_branch": data_branch_name(),
        "reset_at": now_local().isoformat(),
    }


def _migrate_state(data: dict) -> dict:
    if str(data.get("queue_start") or "") == QUEUE_START:
        data.setdefault("dismissed", [])
        data.setdefault("by_pm", {})
        return data
    return _fresh_state()


def _state() -> dict:
    path = state_file()
    data: dict = {}
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except (OSError, json.JSONDecodeError):
            data = {}
    migrated = _migrate_state(data)
    if migrated is not data:
        _save_state(migrated)
    return migrated


def _save_state(payload: dict) -> None:
    path = state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def dismissed_keys(state: dict | None = None) -> set[str]:
    payload = state if state is not None else _state()
    return {str(key).strip().upper() for key in (payload.get("dismissed") or []) if str(key).strip()}


def _active_tickets(tickets: list[dict], skipped: set[str] | None = None) -> list[dict]:
    blocked = skipped if skipped is not None else dismissed_keys()
    return [ticket for ticket in tickets if (ticket.get("issue_key") or "").upper() not in blocked]


def list_release_asks(*, normalized: list[dict] | None = None, now: datetime | None = None) -> dict:
    state = _state()
    after = queue_after_date(now, state=state)
    skipped = dismissed_keys(state)
    cliq = CliqClient()
    payload = {
        "lookback_days": LOOKBACK_DAYS,
        "after_date": after,
        "queue_start": state.get("queue_start") or QUEUE_START,
        "data_branch": data_branch_name(),
        "connected": False,
        "cliq": cliq.configured,
        "last_nudged_at": state.get("last_nudged_at") or "",
        "dismissed": sorted(skipped),
        "groups": [],
        "count": 0,
        "error": "",
    }
    if normalized is not None:
        payload["connected"] = True
        payload["groups"] = _groups_with_state(collect_release_asks(normalized, after), state=state)
        payload["count"] = sum(len(group["tickets"]) for group in payload["groups"])
        return payload
    client = JiraClient()
    payload["connected"] = client.configured
    if not client.configured:
        payload["groups"] = _groups_with_state([], state=state)
        return payload
    try:
        raw = client.fetch_released_ac_tasks(after)
        rows = [client.normalize(issue) for issue in raw]
        payload["groups"] = _groups_with_state(collect_release_asks(rows, after), state=state)
        payload["count"] = sum(len(group["tickets"]) for group in payload["groups"])
    except Exception as exc:
        payload["error"] = str(exc)[:400]
        payload["groups"] = _groups_with_state([], state=state)
    return payload


def _groups_with_state(groups: list[dict], state: dict | None = None) -> list[dict]:
    payload = state if state is not None else _state()
    found = {group["pm"]: group for group in groups}
    by_pm = payload.get("by_pm") or {}
    skipped = dismissed_keys(payload)
    out = []
    for person in NOTES_PMS:
        group = found.get(person["short"]) or {
            "pm": person["short"],
            "email": person.get("email") or "",
            "cliq_user_id": person.get("cliq_user_id") or "",
            "cliq_chat_id": person.get("cliq_chat_id") or "",
            "tickets": [],
        }
        tickets = _active_tickets(group.get("tickets") or [], skipped)
        stamp = ((by_pm.get(person["short"]) or {}) if isinstance(by_pm, dict) else {}).get("last_nudged_at") or ""
        out.append({**group, "tickets": tickets, "last_nudged_at": stamp})
    return out


def dismiss_ticket(issue_key: str) -> dict:
    key = (issue_key or "").strip().upper()
    if not key:
        raise RuntimeError("Pick a ticket to remove.")
    state = _state()
    skipped = [str(item).strip().upper() for item in (state.get("dismissed") or []) if str(item).strip()]
    if key not in skipped:
        skipped.append(key)
    state["dismissed"] = skipped
    _save_state(state)
    return {"ok": True, "issue_key": key, "dismissed": skipped}


def _pm_label(name: str) -> str | None:
    wanted = (name or "").strip().lower()
    if not wanted:
        return None
    for person in NOTES_PMS:
        if person["short"].lower() == wanted or (person.get("name") or "").lower() == wanted:
            return person["short"]
    return None


def dm_text(pm: str, tickets: list[dict]) -> str:
    count = len(tickets)
    noun = "task" if count == 1 else "tasks"
    lines = [
        f"Hi {pm},",
        "",
        f"Release-notes reminder for {count} Released AC {noun} you own as Product Manager. "
        "Please write notes only for these Released tickets — not other open work — "
        f"and post the update in {PRODUCT_INTERNAL_NAME}.",
        "",
    ]
    current_day = ""
    for ticket in tickets:
        if ticket["released_on"] != current_day:
            current_day = ticket["released_on"]
            lines.append(f"Released {ticket['released_label']}")
            lines.append("")
        title = ticket["summary"] or ticket["issue_key"]
        lines.append(ticket["issue_key"])
        lines.append(title)
        lines.append("Type: Task")
        lines.append("Status: Released")
        lines.append(f"Released on: {ticket['released_label']}")
        if ticket.get("url"):
            lines.append(ticket["url"])
        lines.append("")
    lines.append("Thanks")
    return "\n".join(lines).strip()


def send_nudge(*, groups: list[dict] | None = None, pm: str | None = None) -> dict:
    state = _state()
    skipped = dismissed_keys(state)
    if groups is None:
        listing = list_release_asks()
    else:
        listing = {"groups": _groups_with_state(groups, state=state), "cliq": CliqClient().configured}
    targets = []
    for group in listing.get("groups") or []:
        tickets = _active_tickets(group.get("tickets") or [], skipped)
        if tickets:
            targets.append({**group, "tickets": tickets})
    label = _pm_label(pm or "")
    if pm and not label:
        raise RuntimeError("Pick Lalit or Vidhya.")
    if label:
        targets = [group for group in targets if group["pm"] == label]
        if not targets:
            raise RuntimeError(f"No Released AC tasks for {label} in the last 30 days.")
    if not targets:
        raise RuntimeError("No Released AC tasks for Lalit or Vidhya in the last 30 days.")
    client = CliqClient()
    if not client.configured:
        raise RuntimeError("Cliq is not connected.")
    sent = []
    errors = []
    for group in targets:
        tickets = _active_tickets(group.get("tickets") or [], skipped)
        if not tickets:
            continue
        keys = [(ticket.get("issue_key") or "").upper() for ticket in tickets]
        email = (group.get("email") or "").strip()
        if not email:
            errors.append(f"{group['pm']} DM: no Cliq email configured")
            sent.append({"pm": group["pm"], "ok": False, "via": "", "count": len(tickets), "keys": keys})
            continue
        text = dm_text(group["pm"], tickets)
        try:
            client.send_dm(text, chat_id=group.get("cliq_chat_id") or "", email=email)
        except Exception as exc:
            errors.append(f"{group['pm']} DM ({email}): {exc}")
            sent.append({"pm": group["pm"], "ok": False, "via": "", "count": len(tickets), "keys": keys})
            continue
        sent.append({"pm": group["pm"], "ok": True, "via": "dm", "count": len(tickets), "keys": keys})
    ok_rows = [row for row in sent if row["ok"]]
    if label and not ok_rows:
        raise RuntimeError("Cliq send failed. " + "; ".join(errors)[:400])
    if not label and not ok_rows:
        raise RuntimeError("Cliq send failed. " + "; ".join(errors)[:400])
    stamped = now_local().isoformat()
    state = _state()
    by_pm = dict(state.get("by_pm") or {})
    for row in ok_rows:
        by_pm[row["pm"]] = {"last_nudged_at": stamped, "count": row["count"]}
    state["by_pm"] = by_pm
    state["last_nudged_at"] = stamped
    state["sent"] = sent
    _save_state(state)
    return {"ok": True, "sent": sent, "last_nudged_at": stamped, "errors": errors}

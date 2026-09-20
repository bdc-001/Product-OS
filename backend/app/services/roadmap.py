"""Sense (AC) quarterly roadmap, grouped by Arsalaan's epics."""

from __future__ import annotations

from datetime import datetime
from copy import deepcopy
from pathlib import Path
import re
import uuid

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.clients.jira import JiraClient
from app.clients.llm import LLMClient
from app.config import ROOT
from app.models import JiraIssue, Roadmap
from app.services.jira_scope import is_aborted_status, matches_pm
from app.services.prompts import with_preamble
from app.services.time_window import now_local, tz

ROADMAP_PROMPT = with_preamble(
    """You are Arsalaan's PM. Build a Sense (AC) rolling roadmap from HIS epics and their child tickets.
Do not invent epics or tickets. Do not include PS / Product Support work.
Place every provided ticket into the previous month or the current month. Leave the next month empty.

month must be exactly one of month_keys, verbatim. Do not compute dates. Use current_month and previous_month from the payload.

Return JSON:
{
  "notes": "1-3 sentences on the current window",
  "epics": [
    {
      "key": "AC-123",
      "title": "epic summary",
      "note": "why this epic sits where it does",
      "tickets": [
        {"key": "AC-456", "month": "YYYY-MM", "note": "short placement reason"}
      ]
    }
  ],
  "not_enough_evidence": ""
}

Rules:
- month must be exactly one of month_keys.
- Done / released with resolution_date (or updated_at) in current_month stays in current_month.
- Done / Staging / released from earlier months belong in previous_month.
- In Progress / UAT belong in current_month.
- To Do / unstarted work stays in current_month.
- Do not place any ticket in next_month. That column is for Arsalaan to fill.
- Keep tickets under their epic. Never move a ticket to another epic.
"""
)


def _shift_month(year: int, month: int, delta: int) -> tuple[int, int]:
    value = year * 12 + (month - 1) + delta
    return value // 12, value % 12 + 1


def roadmap_window(now: datetime | None = None) -> dict:
    local = now or now_local()
    if local.tzinfo is None:
        local = local.replace(tzinfo=tz())
    triples = [_shift_month(local.year, local.month, offset) for offset in (-1, 0, 1)]
    months = [f"{year}-{month:02d}" for year, month in triples]
    labels = [datetime(year, month, 1).strftime("%b") for year, month in triples]
    end_year = triples[2][0]
    start_label, end_label = labels[0], labels[2]
    label = f"{start_label} – {end_label} {end_year}" if triples[0][0] != end_year else f"{start_label} – {end_label} {local.year}"
    return {
        "year": local.year,
        "quarter": (local.month - 1) // 3 + 1,
        "label": label,
        "months": months,
        "month_labels": labels,
        "current_month": f"{local.year}-{local.month:02d}",
        "previous_month": months[0],
        "next_month": months[2],
    }


def quarter_window(now: datetime | None = None) -> dict:
    return roadmap_window(now)


def _issue_card(issue: JiraIssue | dict, extra: dict | None = None) -> dict:
    if isinstance(issue, JiraIssue):
        extras = extra or issue.extra_json or {}
        return {
            "key": issue.issue_key,
            "summary": issue.summary,
            "status": issue.status,
            "priority": issue.priority,
            "assignee": issue.assignee or "",
            "issue_type": issue.issue_type or "",
            "due_date": issue.due_date.isoformat()[:10] if issue.due_date else "",
            "updated_at": issue.updated_at.isoformat()[:10] if getattr(issue, "updated_at", None) else "",
            "resolution_date": (extras.get("resolution_date") or "")[:10],
            "url": issue.url,
            "epic_key": extras.get("epic_key") or extras.get("parent_key") or extras.get("epic_link") or "",
        }
    extras = extra or issue.get("extra_json") or {}
    if issue.get("issue_key"):
        due = issue.get("due_date")
        due_text = due.isoformat()[:10] if hasattr(due, "isoformat") else str(due or "")[:10]
        return {
            "key": issue.get("issue_key") or "",
            "summary": issue.get("summary") or "",
            "status": issue.get("status") or "",
            "priority": issue.get("priority") or "",
            "assignee": issue.get("assignee") or "",
            "issue_type": issue.get("issue_type") or "",
            "due_date": due_text,
            "updated_at": str(issue.get("updated_at") or "")[:10],
            "resolution_date": str(extras.get("resolution_date") or "")[:10],
            "url": issue.get("url") or "",
            "epic_key": extras.get("epic_key") or extras.get("parent_key") or extras.get("epic_link") or "",
        }
    fields = issue.get("fields") or {}
    status = (fields.get("status") or {}).get("name") or ""
    return {
        "key": issue.get("key") or "",
        "summary": fields.get("summary") or "",
        "status": status,
        "priority": ((fields.get("priority") or {}).get("name") or ""),
        "assignee": ((fields.get("assignee") or {}).get("displayName") or ""),
        "issue_type": ((fields.get("issuetype") or {}).get("name") or ""),
        "due_date": (fields.get("duedate") or "")[:10],
        "updated_at": str((fields.get("updated") or ""))[:10],
        "resolution_date": str((fields.get("resolutiondate") or extras.get("resolution_date") or ""))[:10],
        "url": issue.get("url") or "",
        "epic_key": extras.get("epic_key") or extras.get("parent_key") or "",
    }


def _owns_epic(issue: JiraIssue) -> bool:
    extras = issue.extra_json or {}
    return any(
        matches_pm(value)
        for value in (
            issue.assignee,
            issue.creator,
            extras.get("reporter"),
            extras.get("product_manager"),
        )
    )


def gather_sense_epics(db: Session) -> list[dict]:
    client = JiraClient()
    epics: dict[str, dict] = {}
    children_by_epic: dict[str, list[dict]] = {}

    raw_epics: list[dict] = []
    raw_children: list[dict] = []
    if client.configured:
        try:
            raw_epics = client.fetch_sense_epics()
        except Exception:
            raw_epics = []
        epic_keys = [item.get("key") or "" for item in raw_epics if item.get("key")]
        try:
            raw_children = client.fetch_epic_children(epic_keys) if epic_keys else []
        except Exception:
            raw_children = []

    for raw in raw_epics:
        data = client.normalize(raw)
        if is_aborted_status(data.get("status") or ""):
            continue
        key = data["issue_key"]
        epics[key] = {
            "key": key,
            "title": data.get("summary") or key,
            "status": data.get("status") or "",
            "assignee": data.get("assignee") or "",
            "priority": data.get("priority") or "",
            "url": data.get("url") or "",
            "note": "",
            "tickets": [],
        }

    for raw in raw_children:
        data = client.normalize(raw)
        if is_aborted_status(data.get("status") or ""):
            continue
        extras = data.get("extra_json") or {}
        parent = extras.get("epic_key") or extras.get("parent_key") or extras.get("epic_link") or ""
        if not parent:
            continue
        children_by_epic.setdefault(parent, []).append(_issue_card(data, extras))

    for issue in db.query(JiraIssue).all():
        if not (issue.issue_key or "").upper().startswith("AC-"):
            continue
        if is_aborted_status(issue.status):
            continue
        extras = issue.extra_json or {}
        if (issue.issue_type or "").lower() == "epic":
            if not _owns_epic(issue):
                continue
            epics.setdefault(
                issue.issue_key,
                {
                    "key": issue.issue_key,
                    "title": issue.summary,
                    "status": issue.status,
                    "assignee": issue.assignee or "",
                    "priority": issue.priority or "",
                    "url": issue.url,
                    "note": "",
                    "tickets": [],
                },
            )
            continue
        parent = extras.get("epic_key") or extras.get("parent_key") or extras.get("epic_link") or ""
        if parent and parent in epics:
            cards = children_by_epic.setdefault(parent, [])
            if not any(card["key"] == issue.issue_key for card in cards):
                cards.append(_issue_card(issue, extras))

    rows = []
    for key, epic in epics.items():
        tickets = children_by_epic.get(key) or []
        seen = set()
        unique = []
        for ticket in tickets:
            if ticket["key"] in seen:
                continue
            seen.add(ticket["key"])
            unique.append(ticket)
        epic["tickets"] = unique[:40]
        rows.append(epic)
    rows.sort(key=lambda item: (item.get("status") or "", item.get("key") or ""))
    return rows[:40]


def _heuristic_place(tickets: list[dict], window: dict) -> list[dict]:
    months = window["months"]
    previous = window.get("previous_month") or months[0]
    current = window.get("current_month") or (months[1] if len(months) > 1 else months[0])
    placed = []
    for ticket in tickets:
        status = (ticket.get("status") or "").lower()
        resolved = (ticket.get("resolution_date") or ticket.get("updated_at") or "")[:7]
        doneish = any(token in status for token in ("done", "complete", "released", "closed"))
        staging = "staging" in status
        if doneish and resolved == current:
            month = current
        elif doneish or staging:
            month = previous
        else:
            month = current
        placed.append({**ticket, "month": month, "note": ticket.get("note") or ""})
    return placed


def _apply_llm(epics: list[dict], generated: dict, window: dict) -> list[dict]:
    months = set(window["months"])
    by_epic = {epic["key"]: epic for epic in epics}
    proposed = generated.get("epics") if isinstance(generated, dict) else None
    if not isinstance(proposed, list):
        return epics
    for row in proposed:
        if not isinstance(row, dict):
            continue
        epic = by_epic.get(row.get("key") or "")
        if not epic:
            continue
        if row.get("note"):
            epic["note"] = str(row["note"])[:400]
        if row.get("title"):
            epic["title"] = str(row["title"])[:200]
        placements = {item.get("key"): item for item in (row.get("tickets") or []) if isinstance(item, dict)}
        for ticket in epic["tickets"]:
            hit = placements.get(ticket["key"])
            if not hit:
                continue
            month = str(hit.get("month") or "")
            if month in months and month != window.get("next_month"):
                ticket["month"] = month
            if hit.get("note"):
                ticket["note"] = str(hit["note"])[:4000]
    return list(by_epic.values())


ROADMAP_FILES = ROOT / "data" / "roadmap_files"
PDF_FILE = re.compile(r"^[a-f0-9-]{36}\.pdf$")


def _user_ticket_extras(epics) -> dict[str, dict]:
    extras: dict[str, dict] = {}
    for epic in epics or []:
        if not isinstance(epic, dict):
            continue
        for ticket in epic.get("tickets") or []:
            if not isinstance(ticket, dict) or not ticket.get("key"):
                continue
            extras[str(ticket["key"])] = {
                "note": str(ticket.get("note") or ""),
                "attachments": [item for item in (ticket.get("attachments") or []) if isinstance(item, dict) and item.get("url")],
            }
    return extras


def _user_epic_notes(epics) -> dict[str, str]:
    notes: dict[str, str] = {}
    for epic in epics or []:
        if isinstance(epic, dict) and epic.get("key") and epic.get("note"):
            notes[str(epic["key"])] = str(epic.get("note") or "")
    return notes


def _restore_ticket_extras(epics: list[dict], extras: dict[str, dict], epic_notes: dict[str, str]) -> list[dict]:
    for epic in epics:
        saved_note = epic_notes.get(str(epic.get("key") or ""))
        if saved_note:
            epic["note"] = saved_note[:400]
        for ticket in epic.get("tickets") or []:
            hit = extras.get(str(ticket.get("key") or ""))
            if not hit:
                continue
            if hit.get("note"):
                ticket["note"] = str(hit["note"])[:4000]
            if hit.get("attachments"):
                ticket["attachments"] = hit["attachments"]
    return epics


def store_ticket_pdf(*, original_name: str, data: bytes) -> dict:
    if len(data) > 10 * 1024 * 1024:
        raise RuntimeError("PDF must be 10 MB or smaller.")
    name = (original_name or "attachment.pdf").rsplit("/", 1)[-1]
    if not name.lower().endswith(".pdf"):
        raise RuntimeError("Only PDF files can be attached.")
    if not data.startswith(b"%PDF-"):
        raise RuntimeError("That file is not a PDF.")
    from app.services.knowledge import extract
    try:
        extract(name, data)
    except ValueError as exc:
        raise RuntimeError(str(exc)) from exc
    ROADMAP_FILES.mkdir(parents=True, exist_ok=True)
    file_id = f"{uuid.uuid4()}.pdf"
    (ROADMAP_FILES / file_id).write_bytes(data)
    return {"id": file_id, "kind": "pdf", "name": name[:120], "url": f"/api/roadmap/files/{file_id}"}


def resolve_ticket_pdf(file_id: str) -> Path:
    if not PDF_FILE.match(file_id or ""):
        raise RuntimeError("Unknown file.")
    path = (ROADMAP_FILES / file_id).resolve()
    if path.parent != ROADMAP_FILES.resolve() or not path.is_file():
        raise RuntimeError("Unknown file.")
    return path


def generate_roadmap(db: Session) -> dict:
    window = quarter_window()
    previous = db.query(Roadmap).order_by(Roadmap.id.desc()).first()
    extras = _user_ticket_extras(previous.epics if previous else None)
    epic_notes = _user_epic_notes(previous.epics if previous else None)
    epics = gather_sense_epics(db)
    for epic in epics:
        epic["tickets"] = _heuristic_place(epic.get("tickets") or [], window)
    llm_used = False
    notes = f"Sense roadmap for {window['label']}. Previous month, this month, and a blank next month to plan into."
    llm = LLMClient()
    if llm.configured and epics:
        payload = {
            "quarter": window,
            "month_keys": window["months"],
            "current_month": window["current_month"],
            "previous_month": window["previous_month"],
            "next_month": window["next_month"],
            "epics": [
                {
                    "key": epic["key"],
                    "title": epic["title"],
                    "status": epic.get("status"),
                    "tickets": [
                        {
                            "key": ticket["key"],
                            "summary": ticket["summary"],
                            "status": ticket["status"],
                            "priority": ticket.get("priority"),
                            "due_date": ticket.get("due_date"),
                            "resolution_date": ticket.get("resolution_date"),
                            "updated_at": ticket.get("updated_at"),
                            "assignee": ticket.get("assignee"),
                        }
                        for ticket in epic.get("tickets") or []
                    ],
                }
                for epic in epics
            ],
        }
        try:
            generated = llm.complete_json(payload, system_prompt=ROADMAP_PROMPT, max_chars=20000, surface="roadmap")
            epics = _apply_llm(epics, generated, window)
            if generated.get("notes"):
                notes = str(generated["notes"])[:800]
            llm_used = True
        except Exception:
            llm_used = False
    epics = _restore_ticket_extras(epics, extras, epic_notes)
    now = now_local().replace(tzinfo=None)
    row = (
        db.query(Roadmap)
        .filter(Roadmap.year == window["year"], Roadmap.quarter == window["quarter"])
        .order_by(Roadmap.id.desc())
        .first()
    )
    if row:
        row.months = window["months"]
        row.month_labels = window["month_labels"]
        row.epics = epics
        flag_modified(row, "epics")
        row.notes = notes
        row.llm_used = llm_used
        row.updated_at = now
        row.label = window["label"]
    else:
        row = Roadmap(
            year=window["year"],
            quarter=window["quarter"],
            label=window["label"],
            months=window["months"],
            month_labels=window["month_labels"],
            epics=epics,
            notes=notes,
            llm_used=llm_used,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return roadmap_out(row, db)


def save_roadmap(db: Session, payload: dict) -> dict:
    row = db.query(Roadmap).order_by(Roadmap.id.desc()).first()
    if not row:
        raise RuntimeError("Generate a roadmap first.")
    if "epics" in payload and isinstance(payload["epics"], list):
        row.epics = payload["epics"]
        flag_modified(row, "epics")
    if "notes" in payload:
        row.notes = str(payload.get("notes") or "")[:2000]
    row.updated_at = now_local().replace(tzinfo=None)
    db.commit()
    db.refresh(row)
    return roadmap_out(row, db)


def _align_to_window(out: dict) -> dict:
    window = roadmap_window()
    months = window["months"]
    previous, current = months[0], window["current_month"]
    out["year"] = window["year"]
    out["quarter"] = window["quarter"]
    out["label"] = window["label"]
    out["months"] = months
    out["month_labels"] = window["month_labels"]
    out["current_month"] = current
    for epic in out.get("epics") or []:
        for ticket in epic.get("tickets") or []:
            month = ticket.get("month") or ""
            if month in months:
                continue
            if month and month < previous:
                ticket["month"] = previous
            else:
                ticket["month"] = current
    return out


def _ticket_status_fields(issue: JiraIssue | dict) -> dict:
    if isinstance(issue, JiraIssue):
        extras = issue.extra_json or {}
        return {
            "status": issue.status or "",
            "assignee": issue.assignee or "",
            "summary": issue.summary or "",
            "priority": extras.get("priority_level") or issue.priority or "",
            "issue_type": issue.issue_type or "",
            "url": issue.url or "",
        }
    return {
        "status": issue.get("status") or "",
        "assignee": issue.get("assignee") or "",
        "summary": issue.get("summary") or "",
        "priority": issue.get("priority") or "",
        "issue_type": issue.get("issue_type") or "",
        "url": issue.get("url") or "",
    }


def apply_live_ticket_status(db: Session, epics: list, fetch_missing: bool = False) -> bool:
    tickets = []
    for epic in epics or []:
        for ticket in epic.get("tickets") or []:
            if ticket.get("key"):
                tickets.append(ticket)
    if not tickets:
        return False
    keys = [ticket["key"] for ticket in tickets]
    found = {
        issue.issue_key: issue
        for issue in db.query(JiraIssue).filter(JiraIssue.issue_key.in_(keys)).all()
    }
    missing = [key for key in keys if key not in found]
    fetched: dict[str, dict] = {}
    if fetch_missing and missing:
        client = JiraClient()
        if client.configured:
            try:
                raw = client.fetch_by_keys(missing, scoped=False)
            except Exception:
                raw = []
            for item in raw:
                data = client.normalize(item)
                key = data.get("issue_key") or ""
                if key:
                    fetched[key] = data
    changed = False
    for ticket in tickets:
        key = ticket.get("key") or ""
        live = found.get(key)
        source = live or fetched.get(key)
        if not source:
            continue
        fields = _ticket_status_fields(source)
        for field, value in fields.items():
            if not value:
                continue
            if ticket.get(field) != value:
                ticket[field] = value
                changed = True
    return changed


def sync_roadmap_statuses(db: Session, fetch_missing: bool = True) -> dict | None:
    row = db.query(Roadmap).order_by(Roadmap.id.desc()).first()
    if not row:
        return None
    epics = deepcopy(row.epics or [])
    if apply_live_ticket_status(db, epics, fetch_missing=fetch_missing):
        row.epics = epics
        flag_modified(row, "epics")
        row.updated_at = now_local().replace(tzinfo=None)
        db.commit()
        db.refresh(row)
    return roadmap_out(row, db)


def roadmap_out(row: Roadmap | None, db: Session | None = None) -> dict | None:
    if not row:
        return None
    out = _align_to_window(
        {
            "id": row.id,
            "year": row.year,
            "quarter": row.quarter,
            "label": row.label,
            "months": row.months or [],
            "month_labels": row.month_labels or [],
            "epics": deepcopy(row.epics or []),
            "notes": row.notes or "",
            "llm_used": row.llm_used,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            "ticket_count": sum(len(epic.get("tickets") or []) for epic in (row.epics or [])),
            "epic_count": len(row.epics or []),
        }
    )
    if db is not None:
        apply_live_ticket_status(db, out.get("epics") or [], fetch_missing=False)
    return out


def latest_roadmap(db: Session) -> dict | None:
    row = db.query(Roadmap).order_by(Roadmap.id.desc()).first()
    return roadmap_out(row, db)

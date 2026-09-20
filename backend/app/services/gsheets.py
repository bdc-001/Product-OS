"""Google Sheets sync for the Product Marketing feature list."""
from __future__ import annotations

import logging
import re
import time
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.models import MarketingFeature

log = logging.getLogger(__name__)

SHEET_URL = "https://docs.google.com/spreadsheets/d/{id}/edit"
HEADERS = ("Module", "Feature", "Description", "Use Case", "Industry", "Status", "Script", "Video")
SCOPES = (
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
)
_ALIASES = {
    "module": {"module", "product area"},
    "name": {"feature", "name", "feature name"},
    "summary": {"description", "2 liner", "2-liner", "two liner", "two-line description", "summary"},
    "description": {"use case", "usecase", "supported use case"},
    "audience": {"industry", "relevant industry", "who to market to", "audience"},
    "sheet_status": {"status", "sheet status", "progress"},
    "script": {"script"},
    "video": {"video", "video references", "video files"},
}


def sheet_id() -> str:
    return (settings.marketing_sheet_id or "").strip()


def sheet_url() -> str:
    return SHEET_URL.format(id=sheet_id()) if sheet_id() else ""


def sheets_configured() -> bool:
    key = Path(settings.gdrive_key_file).expanduser() if settings.gdrive_key_file else None
    return bool(sheet_id() and key and key.is_file())


def sheet_status() -> dict:
    return {"configured": sheets_configured(), "url": sheet_url()}


def _retry(fn):
    last = None
    for delay in (0, 1.5, 3.0):
        if delay:
            time.sleep(delay)
        try:
            return fn()
        except Exception as exc:
            last = exc
            text = str(exc)
            transient = any(token in text for token in ("429", "500", "502", "503", "504", "backendError", "rateLimitExceeded", "timed out"))
            if not transient:
                raise
            log.warning("Google Sheets request failed; retrying if attempts remain")
    raise last


def _creds():
    from google.oauth2 import service_account

    return service_account.Credentials.from_service_account_file(
        str(Path(settings.gdrive_key_file).expanduser()), scopes=list(SCOPES)
    )


def _service():
    from googleapiclient.discovery import build

    return build("sheets", "v4", credentials=_creds(), cache_discovery=False)


def _service_email() -> str:
    try:
        return _creds().service_account_email
    except Exception:
        return "the Drive service account"


def _tab_title(service, spreadsheet: str) -> str:
    wanted = (settings.marketing_sheet_tab or "").strip()
    meta = _retry(lambda: service.spreadsheets().get(spreadsheetId=spreadsheet, fields="sheets.properties").execute())
    titles = [sheet["properties"]["title"] for sheet in meta.get("sheets") or [] if sheet.get("properties", {}).get("title")]
    if wanted:
        if wanted in titles:
            return wanted
        raise RuntimeError(f"Google Sheet tab {wanted!r} was not found.")
    if not titles:
        raise RuntimeError("The Google Sheet has no tabs.")
    return titles[0]


def _quoted(title: str) -> str:
    return "'" + title.replace("'", "''") + "'"


def _header_map(row: list) -> dict[str, int]:
    found = {}
    for index, cell in enumerate(row):
        key = re.sub(r"\s+", " ", str(cell or "")).strip().casefold()
        for field, aliases in _ALIASES.items():
            if key in aliases and field not in found:
                found[field] = index
    return found


def _cell(row: list, index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    return re.sub(r"[ \t]+", " ", str(row[index] or "").replace("\r\n", "\n").replace("\r", "\n")).strip()


def read_rows() -> list[dict]:
    service = _service()
    sid = sheet_id()
    title = _tab_title(service, sid)
    result = _retry(lambda: service.spreadsheets().values().get(
        spreadsheetId=sid, range=f"{_quoted(title)}!A1:Z2000", majorDimension="ROWS"
    ).execute())
    values = result.get("values") or []
    if not values:
        return []
    headers = _header_map(values[0])
    if "name" not in headers:
        return []
    rows = []
    for raw in values[1:]:
        name = _cell(raw, headers.get("name"))
        if not name:
            continue
        rows.append({
            "module": _cell(raw, headers.get("module"))[:120],
            "name": name[:180],
            "summary": _cell(raw, headers.get("summary"))[:280],
            "description": _cell(raw, headers.get("description"))[:4000],
            "audience": _cell(raw, headers.get("audience"))[:500],
            "sheet_status": _cell(raw, headers.get("sheet_status"))[:64],
            "script": _cell(raw, headers.get("script"))[:8000],
            "video": _cell(raw, headers.get("video"))[:4000],
        })
    return rows


def write_rows(rows: list[list[str]]) -> str:
    service = _service()
    sid = sheet_id()
    title = _tab_title(service, sid)
    quoted = _quoted(title)
    values = [list(HEADERS), *rows]
    _retry(lambda: service.spreadsheets().values().update(
        spreadsheetId=sid, range=f"{quoted}!A1", valueInputOption="RAW",
        body={"values": values},
    ).execute())
    _retry(lambda: service.spreadsheets().values().clear(
        spreadsheetId=sid, range=f"{quoted}!A{len(values) + 1}:Z2000",
    ).execute())
    return title


def feature_sheet_row(row: MarketingFeature) -> list[str]:
    from app.services.marketing import two_liner
    summary = (row.summary or "").strip() or two_liner(row.hook, row.description)
    use_case = (row.description or "").strip()
    return [
        row.module or "", row.name, summary[:280], use_case, row.audience or "",
        row.sheet_status or "", row.script or "", row.video or "",
    ]


def pull_into(db: Session) -> dict:
    if not sheets_configured():
        return {"ok": True, "skipped": True, "added": 0, "updated": 0}
    try:
        from app.services.marketing import identity
        incoming = read_rows()
        existing = {row.identity: row for row in db.query(MarketingFeature).all()}
        added = updated = 0
        for item in incoming:
            key = identity(item["name"])
            if not key:
                continue
            row = existing.get(key)
            if row is None:
                use_case = item["description"] or item["summary"] or f"Market {item['name']} for Sense buyers."
                row = MarketingFeature(
                    name=item["name"], identity=key, module=item["module"], summary=item["summary"],
                    description=use_case, audience=item["audience"], hook=item["summary"],
                    benefit=item["summary"], notes="", status="draft", source="sheet",
                    evidence=[], decision={}, revision=1,
                    sheet_status=item.get("sheet_status") or "Not started",
                    script=item.get("script") or "", video=item.get("video") or "", tag="New",
                )
                db.add(row)
                existing[key] = row
                added += 1
                continue
            changed = False
            brief_changed = False
            mapping = (
                ("module", item["module"][:120]), ("summary", item["summary"][:280]),
                ("description", item["description"][:4000]), ("audience", item["audience"][:500]),
                ("sheet_status", (item.get("sheet_status") or "")[:64]),
                ("script", (item.get("script") or "")[:8000]),
                ("video", (item.get("video") or "")[:4000]),
            )
            for field, value in mapping:
                if value and getattr(row, field) != value:
                    setattr(row, field, value)
                    changed = True
                    brief_changed |= field in {"module", "summary", "description", "audience"}
            if changed:
                if brief_changed:
                    row.revision += 1
                    row.decision = {}
                row.updated_at = datetime.utcnow()
                updated += 1
        if added or updated:
            db.commit()
        return {"ok": True, "added": added, "updated": updated, "count": len(incoming), "url": sheet_url()}
    except Exception as exc:
        db.rollback()
        log.exception("Marketing Google Sheet pull failed")
        return {"ok": False, "added": 0, "updated": 0, "error": _explain(exc), "url": sheet_url()}


def push_from(db: Session) -> dict:
    if not sheets_configured():
        return {"ok": True, "skipped": True, "count": 0}
    try:
        rows = [feature_sheet_row(row) for row in db.query(MarketingFeature).order_by(MarketingFeature.id)
                if row.status != "dismissed"]
        title = write_rows(rows)
        return {"ok": True, "count": len(rows), "tab": title, "url": sheet_url()}
    except Exception as exc:
        log.exception("Marketing Google Sheet push failed")
        return {"ok": False, "count": 0, "error": _explain(exc), "url": sheet_url()}


def best_effort_push(db: Session) -> dict:
    result = push_from(db)
    if not result.get("ok"):
        log.warning("Marketing Google Sheet push did not complete")
    return result


def _explain(exc: Exception) -> str:
    text = str(exc)
    lowered = text.lower()
    if "accessnotconfigured" in lowered or "has not been used" in lowered or "google sheets api" in lowered:
        return "Enable the Google Sheets API on the Drive service-account Cloud project, then retry refresh."
    if "403" in text or "PERMISSION_DENIED" in text or "insufficientPermissions" in text:
        return (f"Share the Product Marketing Google Sheet with {_service_email()} as Editor. "
                "The Drive service account cannot write it until then.")
    if "404" in text or "not found" in lowered:
        return "The Product Marketing Google Sheet was not found. Check MARKETING_SHEET_ID."
    return "Google Sheet sync failed. Check Drive credentials and sheet sharing, then retry refresh."

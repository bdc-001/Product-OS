"""Upload release-note PDFs to a shared Google Drive folder. Optional; dry-run if unset."""

from __future__ import annotations

import logging
from pathlib import Path

from app.config import settings

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive"]


def explain_drive_error(exc: Exception) -> Exception:
    text = str(exc)
    if "storageQuotaExceeded" in text or "storage quota has been exceeded" in text.lower():
        from app.services.google_auth import service_email

        email = service_email()
        return RuntimeError(
            "Google blocked creating files: a service account has no My Drive storage. "
            "Move the Release Notes folder into a Shared Drive and add "
            f"{email} as Content Manager. Listing the folder can work while creates still fail."
        )
    return exc


def drive_configured() -> bool:
    from app.services.google_auth import google_configured

    folder = (settings.gdrive_folder_id or "").strip()
    return bool(folder and google_configured())


def drive_status() -> dict:
    from app.services.google_auth import google_configured

    has_key = google_configured()
    folder = (settings.gdrive_folder_id or "").strip()
    if has_key and folder:
        return {"configured": True, "mode": "connected", "label": "Drive: connected"}
    if folder and not has_key:
        return {"configured": False, "mode": "local", "label": "Drive: service-account key missing (approval stores locally)"}
    return {"configured": False, "mode": "local", "label": "Drive: not configured (approval stores locally)"}


def _service():
    from googleapiclient.discovery import build

    from app.services.google_auth import credentials

    return build("drive", "v3", credentials=credentials(SCOPES), cache_discovery=False)


def ensure_year_folder(service, parent_id: str, year_month: str) -> str:
    escaped = year_month.replace("'", "\\'")
    query = (
        f"'{parent_id}' in parents and name='{escaped}' "
        f"and mimeType='application/vnd.google-apps.folder' and trashed=false"
    )
    found = (
        service.files()
        .list(
            q=query,
            fields="files(id,name)",
            pageSize=5,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute()
    )
    files = found.get("files") or []
    if files:
        return files[0]["id"]
    try:
        created = (
            service.files()
            .create(
                body={"name": year_month, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]},
                fields="id",
                supportsAllDrives=True,
            )
            .execute()
        )
    except Exception as exc:
        raise explain_drive_error(exc) from exc
    return created["id"]


def find_child_folder(parent_id: str, names: tuple[str, ...] | list[str]) -> str:
    """Return the first matching child folder id under parent_id."""
    service = _service()
    wanted = {str(name).strip().lower() for name in names if str(name).strip()}
    found = (
        service.files()
        .list(
            q=(
                f"'{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' "
                "and trashed=false"
            ),
            fields="files(id,name)",
            pageSize=50,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        )
        .execute()
    )
    for item in found.get("files") or []:
        if str(item.get("name") or "").strip().lower() in wanted:
            return str(item.get("id") or "")
    raise RuntimeError(f"no Drive folder named {list(names)} under {parent_id}")


def upload_pdf(
    pdf_path: Path,
    branch: str,
    filename: str | None = None,
    *,
    parent_id: str | None = None,
    dated: bool = True,
) -> dict:
    if not drive_configured():
        return {"file_id": "dryrun", "link": "", "dry_run": True}
    from googleapiclient.http import MediaFileUpload

    service = _service()
    parent = (parent_id or settings.gdrive_folder_id or "").strip()
    if dated:
        day = (branch or "").split("/")[-1]
        year_month = day[:7] if len(day) >= 7 else now_year_month()
        folder = ensure_year_folder(service, parent, year_month)
    else:
        folder = parent
    name = filename or pdf_path.name
    media = MediaFileUpload(str(pdf_path), mimetype="application/pdf", resumable=True)
    try:
        created = (
            service.files()
            .create(
                body={"name": name, "parents": [folder]},
                media_body=media,
                fields="id, webViewLink",
                supportsAllDrives=True,
            )
            .execute()
        )
    except Exception as exc:
        raise explain_drive_error(exc) from exc
    return {"file_id": created.get("id") or "", "link": created.get("webViewLink") or "", "dry_run": False}


def now_year_month() -> str:
    from app.services.time_window import now_local

    return now_local().strftime("%Y-%m")

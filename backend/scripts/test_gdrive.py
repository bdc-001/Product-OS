"""Check that the service account can see the shared Drive folder.

Run from backend/:
  .venv/bin/python scripts/test_gdrive.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.config import settings

SCOPES = ["https://www.googleapis.com/auth/drive"]


def main() -> int:
    key = Path(settings.gdrive_key_file).expanduser() if settings.gdrive_key_file else None
    folder_id = (settings.gdrive_folder_id or "").strip()
    if not key or not key.is_file():
        print("GDRIVE_KEY_FILE is missing or not a file:", settings.gdrive_key_file)
        return 1
    if not folder_id:
        print("GDRIVE_FOLDER_ID is empty")
        return 1

    creds = service_account.Credentials.from_service_account_file(str(key), scopes=SCOPES)
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    print("service account:", creds.service_account_email)
    print("folder id:", folder_id)
    try:
        meta = (
            drive.files()
            .get(fileId=folder_id, fields="id,name,mimeType", supportsAllDrives=True)
            .execute()
        )
        print("folder:", meta.get("name"), meta.get("id"))
        files = (
            drive.files()
            .list(
                q=f"'{folder_id}' in parents and trashed=false",
                fields="files(id,name)",
                pageSize=10,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
        print("Folder contents:", files.get("files") or [])
        print("ok — auth chain works")
        return 0
    except HttpError as exc:
        status = getattr(exc.resp, "status", None)
        print("Drive API error:", status, exc)
        if status in {403, 404}:
            print(
                "Share the folder with the service account as Editor:\n"
                f"  {creds.service_account_email}"
            )
            print("Also enable Google Drive API on project", creds.project_id)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

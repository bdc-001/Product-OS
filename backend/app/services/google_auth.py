"""Google service-account credentials for the active workspace.

Hosted workspaces keep the key JSON in their Google connection. A local install may still point
`GDRIVE_KEY_FILE` at a key on disk; that is only read, never written.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.config import settings

DRIVE_SCOPES = ("https://www.googleapis.com/auth/drive",)


def _key_info() -> dict | None:
    raw = str(settings.gdrive_key_json or "").strip()
    if raw:
        try:
            info = json.loads(raw)
        except ValueError:
            return None
        return info if isinstance(info, dict) and info.get("client_email") else None
    path = str(settings.gdrive_key_file or "").strip()
    if not path:
        return None
    key = Path(path).expanduser()
    if not key.is_file():
        return None
    try:
        info = json.loads(key.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return info if isinstance(info, dict) else None


def google_configured() -> bool:
    return _key_info() is not None


def credentials(scopes: tuple[str, ...] | list[str] = DRIVE_SCOPES):
    from google.oauth2 import service_account

    info = _key_info()
    if info is None:
        raise RuntimeError("Google is not connected for this workspace. Add a service-account key under Connections.")
    return service_account.Credentials.from_service_account_info(info, scopes=list(scopes))


def service_email(default: str = "the service account") -> str:
    info = _key_info()
    return str((info or {}).get("client_email") or default)

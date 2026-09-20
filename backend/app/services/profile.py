import json
from pathlib import Path

from app.config import ROOT, settings

PROFILE_PATH = ROOT / "data" / "profile.json"


def load_profile() -> dict:
    profile = {
        "pm_display_name": settings.pm_display_name or "",
        "pm_cliq_user_id": settings.pm_cliq_user_id or "",
        "pm_cliq_mentions": settings.pm_cliq_mentions or "",
        "timezone": settings.timezone or "Asia/Kolkata",
        "data_branch": "",
        "app_name": "PM Platform",
    }
    if PROFILE_PATH.exists():
        try:
            profile.update({str(k): str(v) for k, v in json.loads(PROFILE_PATH.read_text()).items() if v is not None})
        except json.JSONDecodeError:
            pass
    mention = str(profile.get("pm_cliq_mentions") or "")
    uid = str(profile.get("pm_cliq_user_id") or "").strip()
    if uid:
        tagged = "{@" + uid + "}"
        if tagged not in mention:
            profile["pm_cliq_mentions"] = ",".join([part for part in mention.split(",") if part.strip()] + [tagged])
    return profile


def save_profile(updates: dict) -> dict:
    current = load_profile()
    allowed = {"pm_display_name", "pm_cliq_user_id", "pm_cliq_mentions", "timezone", "data_branch"}
    for key, value in (updates or {}).items():
        if key in allowed and value is not None:
            current[key] = str(value).strip()
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(
        json.dumps(
            {k: current.get(k) or "" for k in ("pm_display_name", "pm_cliq_user_id", "pm_cliq_mentions", "timezone", "data_branch")},
            indent=2,
        )
    )
    if current.get("timezone"):
        settings.timezone = current["timezone"]
    if current.get("pm_display_name") is not None:
        settings.pm_display_name = current.get("pm_display_name") or ""
    if current.get("pm_cliq_user_id") is not None:
        settings.pm_cliq_user_id = current.get("pm_cliq_user_id") or ""
    if current.get("pm_cliq_mentions") is not None:
        settings.pm_cliq_mentions = current.get("pm_cliq_mentions") or ""
    return load_profile()

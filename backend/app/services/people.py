import json
import re
from pathlib import Path

from app.config import ROOT, settings
from app.services.profile import load_profile

# Contact profile IDs from Cliq, plus IDs that appear in {@mentions}.
# 60031837577 is Lovelesh's contact page; messages also refer to Mahen by name.
DIRECTORY: dict[str, str] = {
    "60031811823": "Arsalaan",
    "60045960384": "Nishchal",
    "60031837577": "Lovelesh",
    "60035710986": "Ramandeep",
    "60031811711": "Lalit",
    "60037154911": "Vidhya",
    "60031811770": "Naveen",
    "60031811580": "Arnab",
    "60031811898": "Neha",
}

MENTION_RE = re.compile(r"\{@(\d+)\}")
BARE_ID_RE = re.compile(r"(?<!\d)(600\d{8,})(?!\d)")


def people_path() -> Path:
    return ROOT / "data" / "people.json"


def load_directory() -> dict[str, str]:
    names = dict(DIRECTORY)
    extra = settings.cliq_people_json.strip()
    if extra:
        try:
            names.update({str(k): str(v) for k, v in json.loads(extra).items()})
        except json.JSONDecodeError:
            pass
    path = people_path()
    if path.exists():
        try:
            names.update({str(k): str(v) for k, v in json.loads(path.read_text()).items()})
        except json.JSONDecodeError:
            pass
    from app.services.workspace import people_map

    names.update(people_map())
    if settings.pm_cliq_user_id:
        names.setdefault(settings.pm_cliq_user_id, settings.pm_display_name or "PM")
    profile = load_profile()
    if profile.get("pm_cliq_user_id"):
        names[str(profile["pm_cliq_user_id"])] = profile.get("pm_display_name") or settings.pm_display_name or "PM"
    return names


def name_for(user_id: str | None, fallback: str = "") -> str:
    if not user_id:
        return fallback
    from app.services.team import canonical_name

    raw = load_directory().get(str(user_id), fallback or str(user_id))
    return canonical_name(raw) or raw


def extract_mention_ids(text: str) -> list[str]:
    return list(dict.fromkeys(MENTION_RE.findall(text or "")))


def pm_user_ids() -> set[str]:
    profile = load_profile()
    ids = {
        str(profile.get("pm_cliq_user_id") or "").strip(),
        str(settings.pm_cliq_user_id or "").strip(),
    }
    ids.discard("")
    return ids


def is_pm_tagged(text: str) -> bool:
    ids = set(extract_mention_ids(text))
    if ids & pm_user_ids():
        return True
    profile = load_profile()
    lower = (text or "").lower()
    mentions = profile.get("pm_cliq_mentions") or settings.pm_cliq_mentions or ""
    for token in mentions.split(","):
        token = token.strip().lower()
        if token and token in lower:
            return True
    return False


def is_pm_sender(sender_id: str | None, sender: str = "") -> bool:
    sid = str(sender_id or "").strip()
    if sid and sid in pm_user_ids():
        return True
    return matches_pm_name(sender)


def matches_pm_name(text: str | None) -> bool:
    haystack = (text or "").lower()
    name = (load_profile().get("pm_display_name") or settings.pm_display_name or "").strip().lower()
    return bool(name) and name in haystack


def resolve_text(text: str) -> str:
    names = load_directory()

    def mention(match: re.Match[str]) -> str:
        uid = match.group(1)
        return f"@{names.get(uid, uid)}"

    resolved = MENTION_RE.sub(mention, text or "")

    def bare(match: re.Match[str]) -> str:
        uid = match.group(1)
        return names.get(uid, uid)

    return BARE_ID_RE.sub(bare, resolved)

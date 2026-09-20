"""PM process people: developers for handoff, QA, and #product-internal."""

from __future__ import annotations

import re

DEFAULT_PRODUCT_INTERNAL_CHAT_ID = "CT_1291643132359481725_60031807119"
PRODUCT_INTERNAL_CHAT_ID = DEFAULT_PRODUCT_INTERNAL_CHAT_ID
PRODUCT_INTERNAL_UNIQUE = "productinternal"
PRODUCT_INTERNAL_NAME = "#product-internal"


def product_internal_chat_id() -> str:
    try:
        from app.services.workspace import overlay_value

        return overlay_value("product_internal_chat_id") or DEFAULT_PRODUCT_INTERNAL_CHAT_ID
    except Exception:
        return DEFAULT_PRODUCT_INTERNAL_CHAT_ID


DEVELOPERS = [
    {
        "short": "Lovelesh",
        "name": "Lovelesh Kumar",
        "account_id": "60f55c8a52162b0068d0a655",
        "aliases": ["lovelesh"],
    },
    {
        "short": "Ramandeep",
        "name": "Ramandeep Singh",
        "account_id": "712020:f88b3645-3400-4621-bf55-26c82b87ec27",
        "aliases": ["ramandeep"],
    },
    {
        "short": "Sourabh",
        "name": "Sourabh Tiwari",
        "account_id": "712020:b54ffe40-1f1e-41d7-a686-6557e089afed",
        "aliases": ["sourabh"],
    },
    {
        "short": "Nishchal",
        "name": "Nishchal Mehra",
        "account_id": "712020:183a9c33-1ddf-46aa-9cf7-27f0b431dcd6",
        "aliases": ["nishchal", "nischal"],
    },
    {
        "short": "Neha",
        "name": "Neha Singh",
        "account_id": "712020:611f0cf4-b34c-4c6f-ab91-ecfe77457592",
        "aliases": ["neha"],
    },
]

QA = {
    "short": "Ankush",
    "name": "Ankush Mangave",
    "account_id": "62e7b5a8da8620d53391fec4",
    "aliases": ["ankush", "ankush mangave"],
}


def developers() -> list[dict]:
    try:
        from app.services.workspace import team_overlay

        overlay = team_overlay().get("developers")
        if isinstance(overlay, list) and overlay:
            return overlay
    except Exception:
        pass
    return DEVELOPERS


def qa_person() -> dict:
    try:
        from app.services.workspace import team_overlay

        overlay = team_overlay().get("qa")
        if isinstance(overlay, dict) and overlay:
            return overlay
    except Exception:
        pass
    return QA


def _needles(person: dict) -> list[str]:
    names = [person.get("short") or "", person.get("name") or "", *(person.get("aliases") or [])]
    return [n.strip().lower() for n in names if n and n.strip()]


def match_person(person: dict, name: str = "", account_id: str = "") -> bool:
    aid = (account_id or "").strip()
    if aid and aid == (person.get("account_id") or ""):
        return True
    haystack = (name or "").strip().lower()
    if not haystack:
        return False
    return any(needle in haystack for needle in _needles(person))


def match_developer(name: str = "", account_id: str = "") -> dict | None:
    for person in developers():
        if match_person(person, name=name, account_id=account_id):
            return person
    return None


def match_qa(name: str = "", account_id: str = "") -> bool:
    return match_person(qa_person(), name=name, account_id=account_id)


def developer_account_ids() -> list[str]:
    return [p["account_id"] for p in developers() if p.get("account_id")]


def jql_account_list(ids: list[str]) -> str:
    return ", ".join(f'"{item}"' for item in ids if item)


def pm_person() -> dict:
    from app.services.profile import load_profile

    profile = load_profile()
    name = (profile.get("pm_display_name") or "").strip() or "PM"
    aliases = ["pm"]
    first = name.split()[0].lower()
    if first and first not in aliases:
        aliases.append(first)
    return {
        "short": name.split()[0],
        "name": name,
        "account_id": "",
        "aliases": aliases,
        "role": "pm",
    }


def roster() -> list[dict]:
    people = [{**person, "role": "developer"} for person in developers()]
    people.append({**qa_person(), "role": "qa"})
    people.append(pm_person())
    return people


def public_roster() -> list[dict]:
    return [
        {
            "short": person.get("short") or "",
            "name": person.get("name") or "",
            "aliases": person.get("aliases") or [],
            "role": person.get("role") or "",
        }
        for person in roster()
    ]


NAME_ALIASES = {
    "nischal": "Nishchal",
}

# Named in chat / Cliq but not Sense Jira assignees.
OTHERS = [
    {"short": "Lalit", "name": "Lalit", "aliases": ["lalit"], "role": "other"},
    {"short": "Vidhya", "name": "Vidhya", "aliases": ["vidhya", "vidya"], "role": "other"},
    {"short": "Naveen", "name": "Naveen", "aliases": ["naveen"], "role": "other"},
    {"short": "Arnab", "name": "Arnab", "aliases": ["arnab"], "role": "other"},
    {"short": "Mahen", "name": "Mahen", "aliases": ["mahen"], "role": "other"},
]

# PMs who owe CSM release notes after AC Task → Released.
NOTES_PMS = [
    {
        "short": "Lalit",
        "name": "Lalit",
        "aliases": ["lalit"],
        "email": "lalit@convin.ai",
        "cliq_user_id": "60031811711",
        "cliq_chat_id": "1248148238389711452",
    },
    {
        "short": "Vidhya",
        "name": "Vidhya",
        "aliases": ["vidhya", "vidya"],
        "email": "vidhya.sriram@convin.ai",
        "cliq_user_id": "60037154911",
        "cliq_chat_id": "1207194750863251476",
    },
]


def match_notes_pm(name: str) -> dict | None:
    hay = (name or "").strip().lower()
    if not hay:
        return None
    for person in NOTES_PMS:
        needles = [person.get("short") or "", person.get("name") or "", *(person.get("aliases") or [])]
        for needle in needles:
            token = (needle or "").strip().lower()
            if token and re.search(rf"\b{re.escape(token)}\b", hay):
                return person
    return None


def canonical_name(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    mapped = NAME_ALIASES.get(text.lower())
    if mapped:
        return mapped
    person = match_teammate(text)
    if person:
        return person.get("short") or person.get("name") or text
    for extra in OTHERS:
        if match_person(extra, name=text):
            return extra.get("short") or text
    return text


def developer_handoff_names() -> list[str]:
    return [person["short"] for person in developers() if person.get("short")]


def display_roster_names() -> list[str]:
    names: list[str] = []
    qa = qa_person()
    for person in [*developers(), qa, pm_person(), *OTHERS]:
        short = person.get("short") or ""
        if person is qa:
            short = person.get("name") or short
        if short and short not in names:
            names.append(short)
    return names


def roster_prompt_block() -> str:
    handoff = ", ".join(developer_handoff_names())
    people = ", ".join(display_roster_names())
    return (
        "TEAM ROSTER (canonical spelling):\n"
        f"{people}\n"
        '- Always normalize "Nischal" → "Nishchal". Never write Nischal.\n'
        f"Developers for Done-on-PM handoff: {handoff}."
    )


def match_teammate(name: str = "", account_id: str = "") -> dict | None:
    for person in roster():
        if match_person(person, name=name, account_id=account_id):
            return person
    return None

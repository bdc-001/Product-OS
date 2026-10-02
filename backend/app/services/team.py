"""PM process people from the workspace's People list: developers for handoff, QA, notes PMs, others."""

from __future__ import annotations

import re

PRODUCT_INTERNAL_UNIQUE = "productinternal"
PRODUCT_INTERNAL_NAME = "#product-internal"


def product_internal_chat_id() -> str:
    """The Cliq channel where the weekly plan is posted (Cliq connection → product-internal chat)."""
    try:
        from app.services.workspace import overlay_value

        return overlay_value("product_internal_chat_id")
    except Exception:
        return ""


def _people(role: str) -> list[dict]:
    try:
        from app.services.workspace import people_with_role

        return people_with_role(role)
    except Exception:
        return []


def developers() -> list[dict]:
    return _people("dev")


def qa_person() -> dict:
    found = _people("qa")
    return found[0] if found else {}


def notes_pms() -> list[dict]:
    """PMs who owe CSM release notes after a product Task moves to Released."""
    return _people("notes_pm")


def others() -> list[dict]:
    """Named in chat but not Jira assignees; notes PMs count here for name matching."""
    return [{**person, "role": "other"} for person in (*_people("other"), *notes_pms())]


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
    qa = qa_person()
    return bool(qa) and match_person(qa, name=name, account_id=account_id)


def developer_account_ids() -> list[str]:
    return [p["account_id"] for p in developers() if p.get("account_id")]


def jql_account_list(ids: list[str]) -> str:
    return ", ".join(f'"{item}"' for item in ids if item)


def pm_person() -> dict:
    from app.services.profile import load_profile

    profile = load_profile()
    name = (profile.get("pm_display_name") or "").strip() or "PM"
    listed = next((p for p in _people("pm") if match_person(p, name=name)), None) or {}
    aliases = ["pm"]
    for alias in [name.split()[0].lower(), *(listed.get("aliases") or [])]:
        if alias and alias not in aliases:
            aliases.append(alias)
    return {
        "short": listed.get("short") or name.split()[0],
        "name": listed.get("name") or name,
        "account_id": listed.get("account_id") or "",
        "email": listed.get("email") or "",
        "cliq_user_id": listed.get("cliq_user_id") or "",
        "aliases": aliases,
        "role": "pm",
    }


def roster() -> list[dict]:
    people = [{**person, "role": "developer"} for person in developers()]
    qa = qa_person()
    if qa:
        people.append({**qa, "role": "qa"})
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


def match_notes_pm(name: str) -> dict | None:
    hay = (name or "").strip().lower()
    if not hay:
        return None
    for person in notes_pms():
        for needle in _needles(person):
            if re.search(rf"\b{re.escape(needle)}\b", hay):
                return person
    return None


def canonical_name(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    person = match_teammate(text)
    if person:
        return person.get("short") or person.get("name") or text
    for extra in others():
        if match_person(extra, name=text):
            return extra.get("short") or text
    return text


def developer_handoff_names() -> list[str]:
    return [person["short"] for person in developers() if person.get("short")]


def display_roster_names() -> list[str]:
    names: list[str] = []
    qa = qa_person()
    for person in [*developers(), qa, pm_person(), *others()]:
        if not person:
            continue
        short = (person.get("name") if person is qa else person.get("short")) or person.get("short") or ""
        if short and short not in names:
            names.append(short)
    return names


def _misspellings() -> list[tuple[str, str]]:
    """Aliases that are not part of the canonical name, e.g. "Jon" for Jonathan."""
    pairs: list[tuple[str, str]] = []
    for person in [*developers(), qa_person(), *others()]:
        short = (person or {}).get("short") or ""
        full = ((person or {}).get("name") or "").lower()
        for alias in (person or {}).get("aliases") or []:
            token = (alias or "").strip()
            if token and " " not in token and token.lower() not in full and token.lower() != short.lower():
                pairs.append((token.title(), short))
    return pairs


def roster_prompt_block() -> str:
    people = ", ".join(display_roster_names())
    if not people:
        return "TEAM ROSTER: none configured. Use names exactly as they appear in the payload."
    lines = ["TEAM ROSTER (canonical spelling):", people]
    for wrong, right in _misspellings():
        lines.append(f'- Always normalize "{wrong}" → "{right}". Never write {wrong}.')
    handoff = ", ".join(developer_handoff_names())
    if handoff:
        lines.append(f"Developers for Done-on-PM handoff: {handoff}.")
    return "\n".join(lines)


def match_teammate(name: str = "", account_id: str = "") -> dict | None:
    for person in roster():
        if match_person(person, name=name, account_id=account_id):
            return person
    return None

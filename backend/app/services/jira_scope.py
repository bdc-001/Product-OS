"""Who the signed-in PM is on a Jira ticket, and statuses we never ingest."""

from __future__ import annotations

from typing import Any

from app.config import settings

ABORTED_TOKENS = ("aborted", "cancelled", "canceled", "won't do", "wont do")


def is_aborted_status(status: str | None) -> bool:
    text = (status or "").lower()
    return any(token in text for token in ABORTED_TOKENS)


def not_aborted_jql() -> str:
    return (
        "(status != ABORTED AND status != Aborted "
        'AND status not in ("Cancelled", "Canceled", "Won\'t Do"))'
    )


def involvement_jql() -> str:
    """Assignee, Product Manager, Developer, or mentioned in comments."""
    return (
        "("
        "assignee = currentUser() "
        'OR "Product Manager" = currentUser() '
        'OR "Developer" = currentUser() '
        "OR comment ~ currentUser()"
        ")"
    )


def pm_needles() -> list[str]:
    from app.services.profile import load_profile
    profile = load_profile()
    needles = []
    name = (profile.get("pm_display_name") or settings.pm_display_name or "").strip().lower()
    if name:
        needles.append(name)
    email = (settings.jira_email or "").strip().lower()
    if email:
        needles.append(email)
        needles.append(email.split("@")[0])
    return [n for n in needles if n]


def matches_pm(text: str | None) -> bool:
    haystack = (text or "").lower()
    if not haystack:
        return False
    return any(needle in haystack for needle in pm_needles())


def _walk_mentions(node: Any, found: list[str]) -> None:
    if isinstance(node, list):
        for child in node:
            _walk_mentions(child, found)
        return
    if not isinstance(node, dict):
        return
    if node.get("type") == "mention":
        attrs = node.get("attrs") or {}
        found.append(str(attrs.get("text") or attrs.get("id") or ""))
    for key in ("content", "body"):
        if key in node:
            _walk_mentions(node[key], found)


def comments_tag_pm(comments: list | None) -> bool:
    for comment in comments or []:
        if not isinstance(comment, dict):
            continue
        if matches_pm(comment.get("body") or "") or matches_pm(comment.get("author") or ""):
            return True
        mentions: list[str] = []
        _walk_mentions(comment.get("body_adf") or comment.get("body"), mentions)
        if any(matches_pm(item) for item in mentions):
            return True
    return False


def stored_involves_pm(issue) -> bool:
    extras = getattr(issue, "extra_json", None) or {}
    if matches_pm(getattr(issue, "assignee", "") or ""):
        return True
    if matches_pm(extras.get("product_manager") or ""):
        return True
    if matches_pm(extras.get("developer") or ""):
        return True
    return comments_tag_pm(getattr(issue, "comments_json", None) or [])

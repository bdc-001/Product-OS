"""Sense (AC) and Product Support (PS) field schemas.

Bug tickets follow the AC-3955-style form. Task/roadmap tickets follow AC-3541.
"""

from __future__ import annotations

from datetime import datetime

EMPTY = {"", "none", "na", "n/a", "null", "unknown", "-"}

BUG_FIELDS = [
    ("summary", "Summary", True),
    ("description", "Description", True),
    ("status", "Status", True),
    ("priority", "Priority / Priority Level", True),
    ("assignee", "Assignee", True),
    ("reporter", "Reporter", True),
    ("product_area", "Product Area", True),
    ("product_manager", "Product Manager", True),
    ("steps_to_reproduce", "Steps to Reproduce", True),
    ("customer", "Customer", True),
    ("developer", "Developer", False),
    ("due_date", "Due date", False),
    ("labels", "Labels", False),
    ("freshdesk", "Freshdesk Support", False),
    ("gist", "Linked Gist Conversations", False),
]

REPORT_FIELDS = [
    ("summary", "Summary", True),
    ("description", "Description", True),
    ("status", "Status", True),
    ("issue_type", "Issue type", True),
    ("product_requirement_type", "Product Requirement Type", False),
    ("report_requirement_type", "Report Requirement Type", False),
    ("priority", "Priority / Priority Level", True),
    ("assignee", "Assignee", True),
    ("reporter", "Reporter", True),
    ("product_area", "Product Area", True),
    ("product_manager", "Product Manager", True),
    ("customer", "Customer", False),
    ("developer", "Developer", False),
    ("due_date", "Due date", False),
    ("labels", "Labels", False),
]

TASK_FIELDS = [
    ("summary", "Summary", True),
    ("description", "Description", True),
    ("status", "Status", True),
    ("request_type", "Request Type", True),
    ("product_area", "Product Area", True),
    ("product_manager", "Product Manager", True),
    ("prd_link", "PRD / Prototype Link", True),
    ("priority", "Priority / Priority Level", True),
    ("assignee", "Assignee", True),
    ("reporter", "Reporter", True),
    ("due_date", "Due date", False),
    ("labels", "Labels", False),
    ("linked_issues", "Linked work items", False),
    ("post_release_action", "Post Release Action", False),
    ("release_note", "Release Note", False),
    ("product_video", "Product Video", False),
]

FIELD_NAME_EXACT = {
    "product area": "product_area",
    "product manager": "product_manager",
    "steps to reproduce the issue": "steps_to_reproduce",
    "steps to reproduce": "steps_to_reproduce",
    "customer": "customer",
    "developer": "developer",
    "request type": "request_type",
    "prd/prototype link": "prd_link",
    "priority level": "priority_level",
    "freshdesk support": "freshdesk",
    "getgist chat ticket link": "gist",
    "post release action": "post_release_action",
    "release note": "release_note",
    "product video": "product_video",
    "product requirement type": "product_requirement_type",
    "report requirement type": "report_requirement_type",
    "epic link": "epic_link",
    "epic name": "epic_name",
}

FIELD_NAME_MATCH = {
    "product_area": ("product area",),
    "product_manager": ("product manager",),
    "steps_to_reproduce": ("steps to reproduce",),
    "developer": ("developer",),
    "request_type": ("request type",),
    "prd_link": ("prd/prototype", "prototype link"),
    "priority_level": ("priority level",),
    "freshdesk": ("freshdesk",),
    "gist": ("getgist", "gist conversation"),
    "post_release_action": ("post release",),
    "release_note": ("release note",),
    "product_video": ("product video",),
    "product_requirement_type": ("product requirement type",),
    "report_requirement_type": ("report requirement type",),
    "epic_link": ("epic link",),
    "epic_name": ("epic name",),
}


def schema_for(issue_type: str, issue_key: str = "") -> list[tuple[str, str, bool]]:
    from app.services.filter import classify_issue

    kind = classify_issue(issue_type, issue_key)
    if kind == "report":
        return REPORT_FIELDS
    if kind == "bug":
        return BUG_FIELDS
    return TASK_FIELDS


def is_empty(value) -> bool:
    if value is None:
        return True
    if isinstance(value, (list, dict)) and not value:
        return True
    text = str(value).strip().lower()
    return text in EMPTY


def missing_fields(issue: dict, extras: dict | None = None) -> dict:
    extras = extras or {}
    schema = schema_for(issue.get("issue_type") or "", issue.get("issue_key") or "")
    values = {**{k: issue.get(k) for k, _, _ in schema}, **extras}
    if extras.get("priority_level") and is_empty(values.get("priority")):
        values["priority"] = extras["priority_level"]
    missing = []
    filled = []
    for key, label, required in schema:
        empty = is_empty(values.get(key))
        if empty and required:
            missing.append(label)
        else:
            filled.append({"label": label, "value": "" if empty else _short(values.get(key)), "required": required, "empty": empty})
    return {
        "kind": "report" if schema is REPORT_FIELDS else "bug" if schema is BUG_FIELDS else "task",
        "missing": missing,
        "filled": filled,
        "schema": [{"key": k, "label": l, "required": r} for k, l, r in schema],
    }


def _short(value) -> str:
    if isinstance(value, list):
        return ", ".join(str(v) for v in value[:8])
    text = str(value)
    return text[:180]


def age_days(created: datetime | None, now: datetime) -> int | None:
    if not created:
        return None
    return max(0, (now - created).days)


def stale_days(updated: datetime | None, now: datetime) -> int | None:
    if not updated:
        return None
    return max(0, (now - updated).days)

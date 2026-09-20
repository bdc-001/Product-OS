"""Structural Copilot write allowlist. Prompt text is not the security boundary."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

ALLOWED_FIELD_KEYS = {
    "summary",
    "description",
    "priority",
    "assignee",
    "labels",
    "due_date",
    "product_area",
    "product_manager",
    "steps_to_reproduce",
    "customer",
    "developer",
    "request_type",
    "prd_link",
    "freshdesk",
    "gist",
    "post_release_action",
    "release_note",
    "product_video",
    "product_requirement_type",
    "report_requirement_type",
}

DENIED_KIND_HINTS = (
    "delete",
    "destroy",
    "archive",
    "bulk",
    "watcher",
    "worklog",
    "admin",
    "clone_epic",
    "create_epic",
    "remove",
    "drop",
)

KIND_ALIASES = {
    "update_fields": "set_fields",
    "set_field": "set_fields",
    "fields": "set_fields",
    "move": "transition",
    "status": "transition",
    "parent": "set_parent",
}

MAX_ACTIONS = 8


class ActionKind(str, Enum):
    create = "create"
    comment = "comment"
    assign = "assign"
    transition = "transition"
    set_fields = "set_fields"
    attach = "attach"
    set_parent = "set_parent"


ALLOWED_KINDS = {item.value for item in ActionKind}
RUN_ORDER = ("create", "set_parent", "set_fields", "assign", "transition", "comment", "attach")


class CopilotActionModel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = ""
    kind: ActionKind
    project: str = "AC"
    issue_type: str = "Task"
    summary: str = ""
    description: str = ""
    fields: dict[str, Any] = Field(default_factory=dict)
    assignee: str = ""
    parent_epic: str = ""
    needs_epic: bool = False
    issue_key: str = ""
    body: str = ""
    transition: str = ""
    image_ids: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    preview: str = ""
    parent: str = ""
    status: str = ""
    ref: str = ""

    @field_validator("kind", mode="before")
    @classmethod
    def _alias_kind(cls, value: Any) -> Any:
        text = str(value or "").strip().lower()
        return KIND_ALIASES.get(text, text)

    @field_validator("project", mode="before")
    @classmethod
    def _project(cls, value: Any) -> str:
        return str(value or "AC").strip().upper() or "AC"

    @field_validator("issue_key", "parent_epic", "parent", mode="before")
    @classmethod
    def _ticket(cls, value: Any) -> str:
        return str(value or "").strip().upper()

    @field_validator("fields", mode="before")
    @classmethod
    def _fields(cls, value: Any) -> dict:
        return value if isinstance(value, dict) else {}

    @field_validator("image_ids", "missing", mode="before")
    @classmethod
    def _str_list(cls, value: Any) -> list:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if str(item).strip()]


class CopilotPlanDocument(BaseModel):
    model_config = ConfigDict(extra="ignore")

    mode: str = "explain"
    answer: str = ""
    questions: list[str] = Field(default_factory=list)
    actions: list[Any] = Field(default_factory=list)

    @field_validator("questions", mode="before")
    @classmethod
    def _questions(cls, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]


class PlanParseResult(BaseModel):
    document: CopilotPlanDocument
    actions: list[dict]
    rejected: list[str] = Field(default_factory=list)


def canonical_kind(raw: str) -> str:
    text = str(raw or "").strip().lower()
    return KIND_ALIASES.get(text, text)


def is_denied_kind(raw: str) -> bool:
    text = canonical_kind(raw)
    if text in ALLOWED_KINDS:
        return False
    return any(token in text for token in DENIED_KIND_HINTS) or text not in ALLOWED_KINDS


def parse_plan_document(generated: Any) -> PlanParseResult:
    if not isinstance(generated, dict):
        generated = {}
    document = CopilotPlanDocument.model_validate(generated)
    actions: list[dict] = []
    rejected: list[str] = []
    raw_actions = document.actions if isinstance(document.actions, list) else []
    if len(raw_actions) > MAX_ACTIONS:
        rejected.append(f"Dropped {len(raw_actions) - MAX_ACTIONS} extra ops (cap {MAX_ACTIONS}).")
    for index, raw in enumerate(raw_actions[:MAX_ACTIONS]):
        if not isinstance(raw, dict):
            rejected.append(f"Op {index + 1} is not an object.")
            continue
        kind = canonical_kind(str(raw.get("kind") or ""))
        if not kind:
            rejected.append(f"Op {index + 1} has no kind.")
            continue
        if kind not in ALLOWED_KINDS or is_denied_kind(kind):
            rejected.append(f"Rejected {kind or 'unknown'} — not an allowed write.")
            continue
        try:
            parsed = CopilotActionModel.model_validate({**raw, "kind": kind})
        except Exception:
            rejected.append(f"Rejected {kind} — failed schema validation.")
            continue
        payload = parsed.model_dump()
        if parsed.parent and not parsed.parent_epic:
            payload["parent_epic"] = parsed.parent
        if parsed.status and not parsed.transition:
            payload["transition"] = parsed.status
        payload["kind"] = parsed.kind.value
        actions.append(payload)
    return PlanParseResult(document=document, actions=actions, rejected=rejected)


def canonical_actions(actions: list[dict] | None) -> list[dict]:
    rows = []
    for item in actions or []:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "id": item.get("id"),
                "kind": canonical_kind(str(item.get("kind") or "")),
                "project": item.get("project"),
                "issue_type": item.get("issue_type"),
                "summary": item.get("summary"),
                "description": item.get("description"),
                "fields": item.get("fields") or {},
                "assignee": item.get("assignee"),
                "parent_epic": item.get("parent_epic"),
                "issue_key": item.get("issue_key"),
                "body": item.get("body"),
                "transition": item.get("transition"),
                "image_ids": item.get("image_ids") or [],
            }
        )
    return rows


def plan_hash(actions: list[dict] | None) -> str:
    blob = json.dumps(canonical_actions(actions), sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def fingerprint_from_issues(rows: list[Any]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in rows:
        key = getattr(row, "issue_key", "") or ""
        if not key:
            continue
        updated = getattr(row, "updated_at", None)
        out[key] = {
            "status": getattr(row, "status", "") or "",
            "updated_at": updated.isoformat() if isinstance(updated, datetime) else str(updated or ""),
            "archived": bool(getattr(row, "archived_at", None)),
        }
    return out


def fingerprints_match(expected: dict | None, actual: dict | None) -> bool:
    left = expected or {}
    right = actual or {}
    if set(left) != set(right):
        return False
    for key, value in left.items():
        other = right.get(key) or {}
        if (value or {}).get("status") != (other or {}).get("status"):
            return False
        if (value or {}).get("updated_at") != (other or {}).get("updated_at"):
            return False
        if bool((value or {}).get("archived")) != bool((other or {}).get("archived")):
            return False
    return True

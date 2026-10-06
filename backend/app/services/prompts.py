"""Shared prompt preamble, JSON parse, and standup item schema.

One edit site for roster, grounding rules, and temperature. Prompts are module constants, so
workspace values are `[[name]]` placeholders that `render_prompt` fills at call time.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.team import developer_handoff_names, roster_prompt_block

log = logging.getLogger(__name__)

PLACEHOLDER = re.compile(r"\[\[([a-z_]+)\]\]")


def _profile() -> dict:
    from app.services.profile import load_profile

    return load_profile()


def _projects(kind: str) -> str:
    from app.clients import jira

    if kind == "writable":
        return ", ".join(sorted(jira.allowed_projects())) or "none configured"
    if kind == "primary":
        return jira.primary_project() or "PROJ"
    if kind == "support":
        return jira.support_project() or "PROJ"
    return ", ".join(jira.project_keys()) or "all projects the Jira token can see"


def _modules() -> list[str]:
    from app.services.profile import product_modules

    return product_modules()


def _main_module() -> str:
    return _modules()[0]


def newsletter_sender() -> str:
    profile = _profile()
    return (profile.get("newsletter_sender") or profile.get("pm_display_name") or "the team").split(" ")[0]


PROMPT_VARS: dict[str, Callable[[], str]] = {
    "pm": lambda: _profile().get("pm_display_name") or "the PM",
    "product": lambda: _profile().get("product_name") or _profile().get("workspace") or "the product",
    "company": lambda: _profile().get("company_name") or _profile().get("workspace") or "the company",
    "personas": lambda: _profile().get("pm_personas") or "the product's operators and buyers",
    "product_description": lambda: _profile().get("product_description") or "a software product",
    "competitor_focus": lambda: _profile().get("competitor_focus") or "",
    "module": lambda: _main_module(),
    "modules": lambda: ", ".join(_modules()),
    "brand_rules": lambda: _profile().get("brand_rules") or "Use the product name exactly as given. Do not invent sub-brands.",
    "support_email": lambda: _profile().get("support_email") or "",
    "newsletter_sender": lambda: newsletter_sender(),
    "scope_rules": lambda: _profile().get("jira_scope_rules") or "",
    "projects": lambda: _projects("synced"),
    "writable_projects": lambda: _projects("writable"),
    "product_project": lambda: _projects("primary"),
    "support_project": lambda: _projects("support"),
    "roster": lambda: roster_prompt_block(),
}


def render_prompt(text: str) -> str:
    """Fill `[[pm]]`, `[[product]]`, `[[roster]]`… from the active workspace. Unknown names stay as written."""
    if not text or "[[" not in text:
        return text
    cache: dict[str, str] = {}

    def fill(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in PROMPT_VARS:
            return match.group(0)
        if name not in cache:
            try:
                cache[name] = str(PROMPT_VARS[name]() or "")
            except Exception:
                log.exception("prompt variable %s failed", name)
                cache[name] = ""
        return cache[name]

    return PLACEHOLDER.sub(fill, text)

ACTION_TYPES = ("follow_up", "investigate", "review", "confirm", "escalate", "decide", "monitor")
SOURCE_TYPES = ("cliq", "jira")
CONFIDENCE = ("HIGH", "MEDIUM", "LOW")

SURFACE_TEMPERATURE = {
    "standup": 0.1,
    "standup_briefing": 0.1,
    "standup_analytics": 0.0,
    "week_actions": 0.0,
    "copilot": 0.1,
    "roadmap": 0.1,
    "codebase": 0.1,
    "codebase_ask": 0.1,
    "codebase_live": 0.1,
    "prototype": 0.4,
    "prd": 0.5,
    "comms": 0.5,
    "comms_doc": 0.5,
    "artifact": 0.4,
    "artifact_content": 0.5,
    # artifact_brief / artifact_polish are Anthropic (temperature omitted).
    "cliq": 0.2,
    "feature_extract": 0.2,
}

COMMS_LEAK_TOKENS = (
    "Billing Dashboard",
    "All Tenants View",
    "Tenant Wise Usage Charges",
    "VoiceAI Operations Tracking",
    "Wallet Balance Alerts",
    "Custom CRM",
    "AI Website Widget",
    "Channel Connectivity",
)

NARRATIVE_SECTIONS = (
    "needs_attention",
    "at_risk",
    "bugs",
    "tasks",
    "wallet_requests",
    "completed",
    "team_signals",
    "todays_actions",
)


def prompt_preamble() -> str:
    return """You are an AI Product Manager agent for [[pm]] ([[product]] at [[company]]).

Jira projects in scope: [[projects]]. [[scope_rules]]

[[roster]]

Hard rules for every surface:
- Never invent tickets, people, files, APIs, statuses, owners, dates, or product names.
- Never show raw numeric user IDs. Use canonical names from the roster.
- Never put a Jira browse URL in a title or body. The ticket key is enough.
- Evidence only. If the payload does not support a claim, omit it.
- If you cannot ground a section, set not_enough_evidence to one sentence and leave that section empty or sparse. Do not pad.
"""


def with_preamble(body: str) -> str:
    return prompt_preamble().rstrip() + "\n\n" + (body or "").strip()


def temperature_for(surface: str) -> float:
    return SURFACE_TEMPERATURE.get(surface or "", 0.1)


def _json_slice(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return ""
    return text[start : end + 1]


def _loose_json(text: str) -> dict:
    cleaned = re.sub(r",\s*([}\]])", r"\1", text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def parse_json_object(raw: Any) -> dict:
    if isinstance(raw, dict):
        return raw
    text = str(raw or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    if not text:
        return {}
    for candidate in (text, _json_slice(text)):
        if not candidate:
            continue
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            salvaged = _loose_json(candidate)
            if salvaged:
                return salvaged
    return {}


class StandupSource(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: str = ""
    ref: str = ""
    chat_id: str = ""
    url: str = ""

    @field_validator("type", mode="before")
    @classmethod
    def _type(cls, value: Any) -> str:
        text = str(value or "").strip().lower()
        return text if text in SOURCE_TYPES else ""


class StandupItemModel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str = ""
    body: str = ""
    action: str = ""
    action_type: str = "follow_up"
    confidence: str = "MEDIUM"
    issue_key: str = ""
    flag: str = ""
    why: str = ""
    sources: list[StandupSource] = Field(default_factory=list)
    not_enough_evidence: str = ""

    @field_validator("action_type", mode="before")
    @classmethod
    def _action_type(cls, value: Any) -> str:
        text = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {"followup": "follow_up", "ua": "review", "uat": "review"}
        text = aliases.get(text, text)
        return text if text in ACTION_TYPES else "follow_up"

    @field_validator("confidence", mode="before")
    @classmethod
    def _confidence(cls, value: Any) -> str:
        text = str(value or "").strip().upper()
        return text if text in CONFIDENCE else "MEDIUM"

    @field_validator("issue_key", mode="before")
    @classmethod
    def _key(cls, value: Any) -> str:
        return str(value or "").strip().upper()

    @field_validator("sources", mode="before")
    @classmethod
    def _sources(cls, value: Any) -> list:
        if not isinstance(value, list):
            return []
        return value[:3]


def repair_standup_item(raw: Any) -> dict | None:
    if not isinstance(raw, dict):
        return None
    try:
        item = StandupItemModel.model_validate(raw)
    except Exception:
        return None
    if not (item.title or item.body or item.issue_key):
        return None
    sources = []
    for source in item.sources:
        if source.type not in SOURCE_TYPES:
            continue
        row = {"type": source.type, "ref": source.ref}
        if source.chat_id:
            row["chat_id"] = source.chat_id
        sources.append(row)
        if len(sources) >= 3:
            break
    if not sources and item.issue_key:
        sources = [{"type": "jira", "ref": item.issue_key}]
    return {
        "title": item.title[:240],
        "body": item.body[:2000],
        "action": item.action[:400],
        "action_type": item.action_type,
        "confidence": item.confidence,
        "issue_key": item.issue_key,
        "flag": item.flag[:40],
        "why": item.why[:800],
        "sources": sources,
    }


def parse_standup_items(raw: Any, *, limit: int = 12) -> list[dict]:
    if not isinstance(raw, list):
        return []
    out = []
    for row in raw:
        item = repair_standup_item(row)
        if item:
            out.append(item)
        if len(out) >= limit:
            break
    return out


def parse_standup_sections(generated: Any, *, limits: dict[str, int] | None = None) -> dict[str, list[dict]]:
    data = parse_json_object(generated) if not isinstance(generated, dict) else generated
    limits = limits or {}
    out: dict[str, list[dict]] = {}
    for key in (*NARRATIVE_SECTIONS, "long_pending", "conflicts"):
        cap = limits.get(key, 8)
        out[key] = parse_standup_items(data.get(key), limit=cap)
    return out


def evidence_not_enough(generated: Any) -> str:
    data = generated if isinstance(generated, dict) else parse_json_object(generated)
    return str((data or {}).get("not_enough_evidence") or "").strip()[:400]


def labeled_evidence(payload: dict) -> str:
    """Labeled blocks raise grounding vs a raw JSON blob."""
    lines = []
    lines.append(f"=== WINDOW ===\nperiod={payload.get('period')} now={payload.get('now')} focus={payload.get('focus')}")
    lines.append(f"jira_connected={payload.get('jira_connected')}")
    lines.append(roster_prompt_block())
    lines.append("=== JIRA TICKETS (open, window) ===")
    for row in (payload.get("combined_tickets") or [])[:40]:
        jira = row.get("jira") or {}
        lines.append(
            f"{row.get('issue_key')} | {jira.get('issue_type') or ''} | {jira.get('status') or ''} | "
            f"assignee: {jira.get('assignee') or ''} | {jira.get('summary') or ''}"
        )
    if not payload.get("combined_tickets"):
        for row in (payload.get("board_snapshot") or [])[:40]:
            lines.append(
                f"{row.get('issue_key')} | {row.get('issue_type') or ''} | {row.get('status') or ''} | "
                f"assignee: {row.get('assignee') or ''} | age_days={row.get('age_days')} stale_days={row.get('stale_days')} | "
                f"{row.get('summary') or ''}"
            )
    lines.append("=== CLIQ (pm_tagged, window) ===")
    for row in (payload.get("pm_tagged_open_points") or [])[:30]:
        stamp = row.get("chat") or ""
        sender = row.get("sender") or ""
        msg = re.sub(r"\s+", " ", str(row.get("message") or ""))[:220]
        lines.append(f"{stamp} {sender} → [[pm]]: \"{msg}\"")
    for group in (payload.get("combined_tickets") or [])[:20]:
        for msg in (group.get("cliq_thread") or [])[:3]:
            if not msg.get("pm_tagged") and not msg.get("ticket_keys"):
                continue
            stamp = msg.get("chat") or ""
            sender = msg.get("sender") or ""
            text = re.sub(r"\s+", " ", str(msg.get("message") or ""))[:220]
            keys = ",".join(msg.get("ticket_keys") or [])
            lines.append(f"{stamp} {sender}: \"{text}\" [{keys}]")
    plan = payload.get("monday_plan") or {}
    if plan:
        lines.append("=== MONDAY PLAN (#product-internal) ===")
        lines.append(str(plan.get("excerpt") or plan.get("message") or "")[:1200])
    lines.append(f"=== HANDOFF DEVELOPERS ===\n{', '.join(developer_handoff_names())}")
    return "\n".join(lines)[:18000]


def payload_mentions_token(payload: dict | None, token: str) -> bool:
    if not payload or not token:
        return False
    blob = json.dumps(payload, default=str).lower()
    return token.lower() in blob


def strip_example_leaks(text: str, payload: dict | None) -> str:
    out = text or ""
    for token in COMMS_LEAK_TOKENS:
        if token.lower() in out.lower() and not payload_mentions_token(payload, token):
            out = re.sub(re.escape(token), "[removed]", out, flags=re.I)
    return out


def log_not_enough(surface: str, note: str) -> None:
    if note:
        log.info("not_enough_evidence surface=%s %s", surface, note)

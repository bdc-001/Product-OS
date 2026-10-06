"""Workspace helpers for services: LLM routing, Cliq token storage and the people roster.

Credentials live in the workspace's encrypted connections and reach services through the
active `WorkspaceContext` (see `app.workspaces.build_context`). Nothing here reads or writes
files or `.env`.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app import context
from app.config import settings

log = logging.getLogger(__name__)

ROUTE_KEYS = ("default", "prototype", "copilot", "docs", "marketing")
ROUTE_LABELS = {
    "default": "Everything else",
    "prototype": "Prototypes",
    "copilot": "Copilot",
    "docs": "Docs and comms",
    "marketing": "Product marketing",
}
DOCS_SURFACES = {
    "comms_doc",
    "release_notes",
    "release_shots",
    "release_evidence",
    "newsletter",
    "artifact",
    "artifact_content",
    "artifact_brief",
    "artifact_polish",
}


def _is_claude(model: str) -> bool:
    return "claude" in (model or "").lower()


def env_llm() -> dict[str, Any]:
    """LLM bundle from plain settings, used outside a workspace and when no AI connection exists."""
    default_model = (settings.llm_model or "gpt-4o-mini").strip() or "gpt-4o-mini"
    docs_model = (settings.llm_docs_model or settings.marketing_model or "").strip()
    providers = {
        "openai": {"label": "OpenAI", "protocol": "openai", "base_url": (settings.llm_base_url or "https://api.openai.com/v1").rstrip("/"), "project": ""},
        "docs": {
            "label": "Docs / Claude",
            "protocol": "anthropic" if _is_claude(docs_model) else "openai",
            "base_url": (settings.llm_docs_base_url or settings.llm_base_url or "").rstrip("/"),
            "project": (settings.llm_docs_project or "").strip(),
        },
    }
    openai_key = (settings.llm_api_key or "").strip()
    keys = {"openai": openai_key, "docs": (settings.llm_docs_api_key or openai_key).strip()}
    docs_provider = "docs" if (settings.llm_docs_model or settings.llm_docs_api_key) else "openai"
    routes = {
        "default": {"provider": "openai", "model": default_model},
        "prototype": {"provider": "openai", "model": default_model},
        "copilot": {"provider": "openai", "model": (settings.llm_copilot_model or default_model).strip() or default_model},
        "docs": {"provider": docs_provider, "model": (settings.llm_docs_model or default_model).strip() or default_model},
        "marketing": {"provider": docs_provider, "model": (settings.marketing_model or settings.llm_docs_model or default_model).strip() or default_model},
    }
    return {"providers": providers, "provider_keys": keys, "routes": routes}


def effective_llm() -> dict[str, Any]:
    ctx = context.current()
    bundle = ctx.llm if ctx is not None else None
    if bundle and bundle.get("providers"):
        return bundle
    return env_llm()


def route_key_for(surface: str) -> str:
    name = surface or ""
    if name.startswith("marketing_"):
        return "marketing"
    if name in DOCS_SURFACES:
        return "docs"
    if name == "copilot":
        return "copilot"
    if name == "prototype":
        return "prototype"
    return "default"


def resolve_llm(surface: str = "unknown", model: str | None = None) -> dict[str, str]:
    bundle = effective_llm()
    routes = bundle.get("routes") or {}
    route = routes.get(route_key_for(surface)) or routes.get("default") or {}
    provider_id = str(route.get("provider") or next(iter(bundle.get("providers") or {}), "openai"))
    provider = (bundle.get("providers") or {}).get(provider_id) or {}
    chosen = (model or route.get("model") or settings.llm_model or "gpt-4o-mini").strip()
    protocol = str(provider.get("protocol") or "openai").strip().lower() or "openai"
    if _is_claude(chosen):
        protocol = "anthropic"
    api_key = str((bundle.get("provider_keys") or {}).get(provider_id) or "").strip()
    if not api_key:
        api_key = ((settings.llm_docs_api_key if protocol == "anthropic" else settings.llm_api_key) or "").strip()
    base_url = str(provider.get("base_url") or "").rstrip("/")
    if not base_url:
        base_url = ((settings.llm_docs_base_url if protocol == "anthropic" else settings.llm_base_url) or "").rstrip("/")
    return {
        "surface": surface or "unknown",
        "route": route_key_for(surface),
        "provider": provider_id,
        "model": chosen,
        "api_key": api_key,
        "base_url": base_url,
        "protocol": protocol,
        "project": str(provider.get("project") or ""),
    }


def store_cliq_tokens(access: str, refresh: str) -> None:
    """Persist refreshed Cliq tokens to the active workspace's connection and update the live context."""
    ctx = context.current()
    if ctx is None:
        return
    tokens = {key: value for key, value in (("access_token", access), ("refresh_token", refresh)) if value}
    if not tokens:
        return
    if access:
        ctx.values["cliq_access_token"] = access
    if refresh:
        ctx.values["cliq_refresh_token"] = refresh
    from app.connections.store import store_tokens
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        store_tokens(db, "cliq", tokens)
    finally:
        db.close()


def save_connection_settings(provider: str, values: dict) -> None:
    """Save non-secret connection fields (a default voice, a folder) without resetting its status."""
    from app.connections.registry import get_provider
    from app.connections.store import get_connection, save_connection
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        row = get_connection(db, provider)
        save_connection(db, provider, values, status=row.status if row is not None else None)
    finally:
        db.close()
    ctx = context.current()
    if ctx is not None:
        for spec in get_provider(provider).fields:
            if spec.key in values and spec.setting:
                ctx.values[spec.setting] = values[spec.key]


def people() -> list[dict]:
    ctx = context.current()
    rows = (ctx.profile.get("people") if ctx is not None else None) or []
    return [row for row in rows if isinstance(row, dict)]


def people_map() -> dict[str, str]:
    """Cliq user ID → display name, from the workspace's people."""
    out: dict[str, str] = {}
    for person in people():
        uid = str(person.get("cliq_user_id") or "").strip()
        if uid:
            out[uid] = person.get("short") or person.get("name") or uid
    extra = (settings.cliq_people_json or "").strip()
    if extra:
        try:
            parsed = json.loads(extra)
            if isinstance(parsed, dict):
                for key, value in parsed.items():
                    out.setdefault(str(key), str(value))
        except json.JSONDecodeError:
            pass
    return out


def team_overlay() -> dict:
    rows = people()
    developers = [_person(row) for row in rows if row.get("role") == "dev"]
    qa = next((_person(row) for row in rows if row.get("role") == "qa"), {})
    return {"developers": developers, "qa": qa}


def _person(row: dict) -> dict:
    return {
        "short": row.get("short") or (row.get("name") or "").split(" ")[0],
        "name": row.get("name") or "",
        "account_id": row.get("account_id") or "",
        "email": row.get("email") or "",
        "cliq_user_id": row.get("cliq_user_id") or "",
        "cliq_chat_id": row.get("cliq_chat_id") or "",
        "aliases": list(row.get("aliases") or []),
        "role": row.get("role") or "",
    }


def people_with_role(role: str) -> list[dict]:
    return [_person(row) for row in people() if row.get("role") == role]


OVERLAY_SETTINGS = {
    "product_internal_chat_id": "cliq_product_internal_chat_id",
    "wallet_chat_id": "cliq_wallet_chat_id",
}


def overlay_value(key: str) -> str:
    setting = OVERLAY_SETTINGS.get(key)
    if setting:
        return str(getattr(settings, setting, "") or "").strip()
    ctx = context.current()
    if ctx is not None and key in ctx.profile:
        return str(ctx.profile.get(key) or "").strip()
    return ""

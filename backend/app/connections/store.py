"""Per-workspace connections: encrypted storage, public views, verification and settings mapping."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app import context
from app.connections import crypto
from app.connections.registry import PROVIDERS, Provider, TestResult, get_provider
from app.models import AuditEvent, Connection, Workspace

log = logging.getLogger(__name__)

LLM_ROUTE_KEYS = ("default", "prototype", "copilot", "docs", "marketing")
LLM_ROUTE_LABELS = {
    "default": "Everything else",
    "prototype": "Prototypes",
    "copilot": "Copilot",
    "docs": "Docs and comms",
    "marketing": "Product marketing",
}


def secret_hint(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    if text.startswith("{"):
        return "JSON key saved"
    if "PRIVATE KEY" in text:
        return "SSH key saved"
    if len(text) <= 8:
        return "••••"
    return f"{text[:2]}…{text[-4:]}"


def is_placeholder(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    if set(text) <= {"*", "•"}:
        return True
    return "…" in text or text.startswith("•") or text.startswith("****")


def _slug(value: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    return slug or fallback


def workspace_row(db: Session, workspace_id: int | None = None) -> Workspace:
    wid = workspace_id or context.require().id
    row = db.get(Workspace, wid)
    if row is None:
        raise context.NoWorkspaceError(f"Workspace {wid} not found")
    return row


def data_key(db: Session, workspace: Workspace) -> str:
    if not workspace.data_key:
        workspace.data_key = crypto.new_data_key()
        db.add(workspace)
        db.flush()
    return workspace.data_key


def bump_version(db: Session, workspace_id: int | None = None) -> None:
    ws = workspace_row(db, workspace_id)
    ws.config_version = int(ws.config_version or 0) + 1
    ws.updated_at = datetime.utcnow()
    db.add(ws)


def audit(db: Session, action: str, target: str = "", detail: dict | None = None, actor: str = "") -> None:
    ctx = context.current()
    db.add(
        AuditEvent(
            actor=actor or (ctx.user_email if ctx else "") or "system",
            action=action,
            target=target,
            detail=detail or {},
        )
    )


def get_connection(db: Session, provider: str, name: str = "default") -> Connection | None:
    return db.query(Connection).filter(Connection.provider == provider, Connection.name == name).one_or_none()


def list_connections(db: Session) -> list[Connection]:
    return db.query(Connection).order_by(Connection.provider, Connection.name).all()


def read_secrets(db: Session, row: Connection) -> dict:
    if not row.secrets:
        return {}
    return crypto.decrypt_json(data_key(db, workspace_row(db, row.workspace_id)), row.secrets)


def connection_values(db: Session, row: Connection) -> dict:
    return {**(row.config or {}), **read_secrets(db, row)}


def _normalize_llm(config: dict, secrets: dict, previous_keys: dict) -> tuple[dict, dict]:
    providers_in = config.get("providers")
    providers: dict[str, dict] = {}
    keys: dict[str, str] = {}
    items = providers_in.items() if isinstance(providers_in, dict) else enumerate(providers_in or [])
    incoming_keys = secrets.get("provider_keys") if isinstance(secrets.get("provider_keys"), dict) else {}
    for index, raw in items:
        if not isinstance(raw, dict):
            continue
        pid = _slug(str(raw.get("id") or (index if isinstance(index, str) else "") or raw.get("label") or ""), f"provider-{len(providers) + 1}")
        providers[pid] = {
            "label": str(raw.get("label") or pid),
            "protocol": str(raw.get("protocol") or "openai").strip().lower() or "openai",
            "base_url": str(raw.get("base_url") or "").rstrip("/"),
            "project": str(raw.get("project") or "").strip(),
        }
        candidate = raw.get("api_key", incoming_keys.get(pid))
        if raw.get("clear_api_key"):
            keys[pid] = ""
        elif candidate is None or is_placeholder(candidate):
            keys[pid] = str(previous_keys.get(pid) or "")
        else:
            keys[pid] = str(candidate).strip()
    routes_in = config.get("routes") if isinstance(config.get("routes"), dict) else {}
    first = next(iter(providers), "")
    routes: dict[str, dict] = {}
    for key in LLM_ROUTE_KEYS:
        item = routes_in.get(key) if isinstance(routes_in.get(key), dict) else {}
        provider = _slug(str(item.get("provider") or ""), "") or first
        if provider not in providers:
            provider = first
        routes[key] = {"provider": provider, "model": str(item.get("model") or "").strip()}
    return {"providers": providers, "routes": routes}, {"provider_keys": {k: v for k, v in keys.items() if v}}


def save_connection(
    db: Session,
    provider_id: str,
    values: dict | None = None,
    *,
    name: str = "default",
    clear: list[str] | tuple[str, ...] = (),
    actor: str = "",
    status: str | None = None,
) -> Connection:
    provider = get_provider(provider_id)
    workspace = workspace_row(db)
    row = get_connection(db, provider_id, name)
    if row is None:
        row = Connection(provider=provider_id, name=name, config={}, secrets="", secret_hints={}, status="untested")
        db.add(row)
        db.flush()
    previous = read_secrets(db, row)
    incoming = dict(values or {})
    if provider.id == "llm":
        config, secrets = _normalize_llm(incoming, incoming, previous.get("provider_keys") or {})
        hints = {"provider_keys": {pid: secret_hint(key) for pid, key in secrets["provider_keys"].items()}}
    else:
        config = dict(row.config or {})
        secrets = dict(previous)
        for spec in provider.fields:
            if spec.key in clear:
                config.pop(spec.key, None)
                secrets.pop(spec.key, None)
                continue
            if spec.key not in incoming:
                continue
            value = incoming[spec.key]
            if spec.secret:
                if value is None or is_placeholder(value):
                    continue
                secrets[spec.key] = str(value).strip()
            else:
                if spec.kind == "number":
                    try:
                        value = int(value)
                    except (TypeError, ValueError):
                        continue
                elif spec.kind == "bool":
                    value = value if isinstance(value, bool) else str(value).strip().lower() in {"1", "true", "yes", "on"}
                elif isinstance(value, str):
                    value = value.strip()
                    if spec.kind == "url":
                        value = value.rstrip("/")
                config[spec.key] = value
        hints = {key: secret_hint(str(val)) for key, val in secrets.items() if val}
    if status is None and provider.fields and provider.missing({**config, **secrets}):
        status = "incomplete"
    row.config = config
    row.secrets = crypto.encrypt_json(data_key(db, workspace), secrets) if any(secrets.values()) else ""
    row.secret_hints = hints
    row.status = status or "untested"
    row.last_error = "" if status != "error" else row.last_error
    row.updated_by = actor or (context.current().user_email if context.current() else "")
    row.updated_at = datetime.utcnow()
    db.add(row)
    bump_version(db, workspace.id)
    audit(db, "connection.saved", f"{provider_id}:{name}", {"fields": sorted(k for k in incoming if k not in {"providers", "routes"})}, actor)
    db.commit()
    db.refresh(row)
    return row


def store_tokens(db: Session, provider_id: str, tokens: dict, name: str = "default") -> None:
    """Persist refreshed OAuth tokens back to the connection (never to files or .env)."""
    row = get_connection(db, provider_id, name)
    if row is None:
        return
    secrets = read_secrets(db, row)
    changed = False
    for key, value in tokens.items():
        if value and secrets.get(key) != value:
            secrets[key] = value
            changed = True
    if not changed:
        return
    workspace = workspace_row(db, row.workspace_id)
    row.secrets = crypto.encrypt_json(data_key(db, workspace), secrets)
    row.secret_hints = {key: secret_hint(str(val)) for key, val in secrets.items() if val}
    row.updated_at = datetime.utcnow()
    db.add(row)
    bump_version(db, workspace.id)
    db.commit()


def disconnect(db: Session, provider_id: str, name: str = "default", actor: str = "") -> bool:
    row = get_connection(db, provider_id, name)
    if row is None:
        return False
    db.delete(row)
    bump_version(db)
    audit(db, "connection.removed", f"{provider_id}:{name}", {}, actor)
    db.commit()
    return True


def test_connection(db: Session, provider_id: str, name: str = "default") -> TestResult:
    provider = get_provider(provider_id)
    row = get_connection(db, provider_id, name)
    if row is None:
        return TestResult(False, "Not connected")
    values = connection_values(db, row)
    missing = provider.missing(values)
    if missing:
        result = TestResult(False, "Missing: " + ", ".join(missing))
    else:
        result = provider.test(values)
    refreshed = (result.details or {}).pop("refreshed", None) if result.details else None
    if refreshed:
        store_tokens(db, provider_id, refreshed, name)
        row = get_connection(db, provider_id, name)
    row.status = "connected" if result.ok else "error"
    row.last_verified_at = datetime.utcnow()
    row.last_error = "" if result.ok else result.message[:800]
    if result.ok and result.details:
        config = dict(row.config or {})
        config["_verified"] = {k: v for k, v in result.details.items() if isinstance(v, (str, int, float, bool)) or v is None}
        row.config = config
    db.add(row)
    bump_version(db, row.workspace_id)
    db.commit()
    return result


def public_view(db: Session, row: Connection | None, provider: Provider) -> dict:
    base = {
        "provider": provider.id,
        "name": row.name if row else "default",
        "connected": bool(row),
        "status": row.status if row else "disconnected",
        "last_verified_at": row.last_verified_at.isoformat() if row and row.last_verified_at else None,
        "last_error": (row.last_error if row else "") or "",
        "updated_at": row.updated_at.isoformat() if row and row.updated_at else None,
        "updated_by": (row.updated_by if row else "") or "",
        "config": {},
        "secrets": {},
        "verified": {},
    }
    if not row:
        return base
    config = dict(row.config or {})
    base["verified"] = config.pop("_verified", {}) or {}
    base["config"] = config
    hints = row.secret_hints or {}
    if provider.id == "llm":
        base["secrets"] = hints
    else:
        base["secrets"] = {spec.key: {"set": bool(hints.get(spec.key)), "hint": hints.get(spec.key) or ""} for spec in provider.fields if spec.secret}
    return base


def llm_bundle(values: dict) -> dict:
    providers = values.get("providers") if isinstance(values.get("providers"), dict) else {}
    routes = values.get("routes") if isinstance(values.get("routes"), dict) else {}
    keys = values.get("provider_keys") if isinstance(values.get("provider_keys"), dict) else {}
    first = next(iter(providers), "")
    full_routes = {}
    for key in LLM_ROUTE_KEYS:
        item = routes.get(key) if isinstance(routes.get(key), dict) else {}
        provider = item.get("provider") if item.get("provider") in providers else first
        full_routes[key] = {"provider": provider, "model": str(item.get("model") or "")}
    return {"providers": providers, "routes": full_routes, "provider_keys": keys}


def _llm_settings(bundle: dict) -> dict:
    out: dict[str, Any] = {}
    providers, keys, routes = bundle["providers"], bundle["provider_keys"], bundle["routes"]

    def route(name: str) -> tuple[dict, str, str]:
        item = routes.get(name) or {}
        pid = item.get("provider") or ""
        return providers.get(pid) or {}, str(keys.get(pid) or ""), str(item.get("model") or "")

    meta, key, model = route("default")
    if model:
        out["llm_model"] = model
    if key:
        out["llm_api_key"] = key
    if meta.get("base_url"):
        out["llm_base_url"] = meta["base_url"]
    _, _, copilot_model = route("copilot")
    if copilot_model:
        out["llm_copilot_model"] = copilot_model
    meta, key, model = route("docs")
    if model:
        out["llm_docs_model"] = model
    if key:
        out["llm_docs_api_key"] = key
    if meta.get("base_url"):
        out["llm_docs_base_url"] = meta["base_url"]
    if meta.get("project"):
        out["llm_docs_project"] = meta["project"]
    _, _, marketing_model = route("marketing")
    if marketing_model:
        out["marketing_model"] = marketing_model
    return out


def settings_values(db: Session, workspace: Workspace) -> tuple[dict, dict]:
    """Map a workspace's connections onto settings names. Returns (values, llm_bundle)."""
    values: dict[str, Any] = {}
    bundle: dict = {"providers": {}, "routes": {}, "provider_keys": {}}
    rows = db.query(Connection).filter(Connection.workspace_id == workspace.id).all()
    for row in rows:
        provider = PROVIDERS.get(row.provider)
        if provider is None or row.name != "default":
            continue
        merged = {**(row.config or {}), **(crypto.decrypt_json(data_key(db, workspace), row.secrets) if row.secrets else {})}
        if provider.id == "llm":
            bundle = llm_bundle(merged)
            values.update(_llm_settings(bundle))
            continue
        for spec in provider.fields:
            if not spec.setting:
                continue
            value = merged.get(spec.key, spec.default)
            if value in (None, ""):
                continue
            values[spec.setting] = value
    return values, bundle

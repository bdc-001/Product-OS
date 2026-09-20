"""Per-install Settings overlay. Public values in workspace.json, secrets in workspace.secrets.json.

.env remains the machine fallback. Saving from Settings never rewrites .env.
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from app.config import ROOT, settings

log = logging.getLogger(__name__)

PUBLIC_PATH = ROOT / "data" / "workspace.json"
SECRETS_PATH = ROOT / "data" / "workspace.secrets.json"
KEY_PATH = ROOT / "data" / "workspace.key"
CLIQ_TOKEN_PATH = ROOT / "data" / "cliq_token.json"
GDRIVE_KEY_PATH = ROOT / "data" / "workspace.gdrive.json"

SECRET_SEGMENTS = ("jira", "cliq", "llm", "mail", "marketing")
SEGMENT_FIELDS = {
    "jira": ("jira_api_token",),
    "cliq": ("cliq_client_secret", "cliq_refresh_token", "cliq_access_token"),
    "mail": ("smtp_password", "release_notes_cron_token"),
    "marketing": ("cartesia_api_key", "gdrive_key_json"),
}

ROUTE_KEYS = ("default", "prototype", "copilot", "docs", "marketing")
ROUTE_LABELS = {
    "default": "Everything else",
    "prototype": "Prototype",
    "copilot": "Copilot",
    "docs": "Docs and comms",
    "marketing": "Product marketing",
}

DOCS_SURFACES = {
    "comms_doc",
    "release_notes",
    "newsletter",
    "artifact",
    "artifact_content",
    "artifact_brief",
    "artifact_polish",
}

PUBLIC_SETTING_KEYS = (
    "timezone",
    "jira_base_url",
    "jira_email",
    "jira_projects",
    "cliq_client_id",
    "cliq_api_domain",
    "cliq_accounts_url",
    "cliq_redirect_uri",
    "cliq_pm_email",
    "cliq_pm_chat_id",
    "pm_display_name",
    "pm_cliq_user_id",
    "pm_cliq_mentions",
    "codebase_path",
    "release_notes_email",
    "smtp_host",
    "smtp_port",
    "smtp_user",
    "smtp_from",
    "smtp_use_tls",
    "gdrive_folder_id",
    "gdrive_assets_folder_id",
    "gdrive_domain",
    "marketing_sheet_id",
    "marketing_sheet_tab",
    "cartesia_voice_id",
    "cartesia_model",
)

SECRET_SETTING_KEYS = (
    "jira_api_token",
    "cliq_client_secret",
    "cliq_refresh_token",
    "cliq_access_token",
    "smtp_password",
    "cartesia_api_key",
    "release_notes_cron_token",
    "gdrive_key_json",
)

PROFILE_KEYS = ("pm_display_name", "pm_cliq_user_id", "pm_cliq_mentions", "timezone", "data_branch")


def _read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, data: dict, *, private: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")
    if private:
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass


def _fernet():
    from cryptography.fernet import Fernet

    KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not KEY_PATH.is_file():
        KEY_PATH.write_bytes(Fernet.generate_key())
        try:
            os.chmod(KEY_PATH, 0o600)
        except OSError:
            pass
    return Fernet(KEY_PATH.read_bytes().strip())


def _encrypt_segment(payload: dict) -> str:
    return _fernet().encrypt(json.dumps(payload, default=str).encode("utf-8")).decode("utf-8")


def _decrypt_segment(token: str) -> dict:
    if not token:
        return {}
    try:
        raw = _fernet().decrypt(str(token).encode("utf-8"))
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        log.exception("could not decrypt settings segment")
        return {}
    return data if isinstance(data, dict) else {}


def _flatten_segments(segments: dict) -> dict:
    flat: dict[str, Any] = {}
    for name, blob in (segments or {}).items():
        payload = _decrypt_segment(blob) if isinstance(blob, str) else (blob if isinstance(blob, dict) else {})
        if name == "llm":
            keys = payload.get("provider_keys") if isinstance(payload.get("provider_keys"), dict) else {}
            flat["provider_keys"] = {str(k): str(v or "") for k, v in keys.items()}
            continue
        for key, value in payload.items():
            flat[str(key)] = value
    return flat


def _read_secrets() -> dict:
    raw = _read_json(SECRETS_PATH)
    if not raw:
        return {}
    if raw.get("encrypted") and isinstance(raw.get("segments"), dict):
        return _flatten_segments(raw["segments"])
    return {str(k): v for k, v in raw.items() if k not in {"encrypted", "version", "segments"}}


def _pack_segments(flat: dict) -> dict[str, str]:
    packed: dict[str, str] = {}
    for name, fields in SEGMENT_FIELDS.items():
        packed[name] = _encrypt_segment({key: flat.get(key) or "" for key in fields})
    keys = flat.get("provider_keys") if isinstance(flat.get("provider_keys"), dict) else {}
    packed["llm"] = _encrypt_segment({"provider_keys": {str(k): str(v or "") for k, v in keys.items()}})
    return packed


def _write_secrets(flat: dict) -> None:
    payload = {
        "version": 1,
        "encrypted": True,
        "segments": _pack_segments(flat or {}),
    }
    _write_json(SECRETS_PATH, payload, private=True)


def secrets_are_encrypted() -> bool:
    raw = _read_json(SECRETS_PATH)
    return bool(raw.get("encrypted") and isinstance(raw.get("segments"), dict))


def segment_status(flat: dict | None = None) -> dict[str, dict]:
    secrets = flat if flat is not None else _read_secrets()
    keys = secrets.get("provider_keys") if isinstance(secrets.get("provider_keys"), dict) else {}
    return {
        "jira": {"encrypted": secrets_are_encrypted(), "set": bool(str(secrets.get("jira_api_token") or "").strip())},
        "cliq": {
            "encrypted": secrets_are_encrypted(),
            "set": bool(
                str(secrets.get("cliq_client_secret") or "").strip()
                or str(secrets.get("cliq_refresh_token") or "").strip()
                or str(secrets.get("cliq_access_token") or "").strip()
            ),
        },
        "llm": {"encrypted": secrets_are_encrypted(), "set": any(str(v or "").strip() for v in keys.values())},
        "mail": {"encrypted": secrets_are_encrypted(), "set": bool(str(secrets.get("smtp_password") or "").strip())},
        "marketing": {
            "encrypted": secrets_are_encrypted(),
            "set": bool(str(secrets.get("cartesia_api_key") or "").strip() or str(secrets.get("gdrive_key_json") or "").strip()),
        },
    }


def secret_hint(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    if len(text) <= 8:
        return "••••"
    return f"{text[:2]}…{text[-4:]}"


def is_secret_placeholder(value: str | None) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    if set(text) <= {"*", "•"}:
        return True
    return "…" in text or text.startswith("•") or text.startswith("****")


def merge_secret(old: str, incoming: str | None, clear: bool = False) -> str:
    if clear:
        return ""
    if incoming is None or is_secret_placeholder(incoming):
        return old
    return str(incoming).strip()


def _is_claude(model: str) -> bool:
    return "claude" in (model or "").lower()


def _slug(value: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    return slug or fallback


def env_providers() -> dict[str, dict[str, str]]:
    docs_model = (settings.llm_docs_model or settings.marketing_model or "").strip()
    docs_protocol = "anthropic" if _is_claude(docs_model) else "openai"
    return {
        "openai": {
            "label": "OpenAI",
            "protocol": "openai",
            "base_url": (settings.llm_base_url or "https://api.openai.com/v1").rstrip("/"),
            "project": "",
        },
        "docs": {
            "label": "Docs / Claude",
            "protocol": docs_protocol,
            "base_url": (settings.llm_docs_base_url or settings.llm_base_url or "").rstrip("/"),
            "project": (settings.llm_docs_project or "").strip(),
        },
    }


def env_provider_keys() -> dict[str, str]:
    openai_key = (settings.llm_api_key or "").strip()
    docs_key = (settings.llm_docs_api_key or openai_key).strip()
    return {"openai": openai_key, "docs": docs_key}


def env_routes() -> dict[str, dict[str, str]]:
    default_model = (settings.llm_model or "gpt-4o-mini").strip() or "gpt-4o-mini"
    has_docs = bool((settings.llm_docs_model or settings.llm_docs_api_key or "").strip())
    docs_provider = "docs" if has_docs else "openai"
    return {
        "default": {"provider": "openai", "model": default_model},
        "prototype": {"provider": "openai", "model": default_model},
        "copilot": {"provider": "openai", "model": (settings.llm_copilot_model or default_model).strip() or default_model},
        "docs": {"provider": docs_provider, "model": (settings.llm_docs_model or default_model).strip() or default_model},
        "marketing": {
            "provider": docs_provider,
            "model": (settings.marketing_model or settings.llm_docs_model or default_model).strip() or default_model,
        },
    }


def _file_llm(public: dict) -> tuple[dict[str, dict], dict[str, dict[str, str]]]:
    block = public.get("llm") if isinstance(public.get("llm"), dict) else {}
    raw_providers = block.get("providers") if isinstance(block, dict) else {}
    providers: dict[str, dict] = {}
    if isinstance(raw_providers, list):
        for item in raw_providers:
            if not isinstance(item, dict):
                continue
            pid = _slug(str(item.get("id") or item.get("label") or ""), "")
            if not pid:
                continue
            providers[pid] = {
                "label": str(item.get("label") or pid),
                "protocol": str(item.get("protocol") or "openai").strip().lower() or "openai",
                "base_url": str(item.get("base_url") or "").rstrip("/"),
                "project": str(item.get("project") or "").strip(),
            }
    elif isinstance(raw_providers, dict):
        for pid, item in raw_providers.items():
            if not isinstance(item, dict):
                continue
            key = _slug(str(pid), "provider")
            providers[key] = {
                "label": str(item.get("label") or key),
                "protocol": str(item.get("protocol") or "openai").strip().lower() or "openai",
                "base_url": str(item.get("base_url") or "").rstrip("/"),
                "project": str(item.get("project") or "").strip(),
            }
    raw_routes = block.get("routes") if isinstance(block, dict) else {}
    routes: dict[str, dict[str, str]] = {}
    if isinstance(raw_routes, dict):
        for key in ROUTE_KEYS:
            item = raw_routes.get(key)
            if not isinstance(item, dict):
                continue
            provider = _slug(str(item.get("provider") or ""), "")
            model = str(item.get("model") or "").strip()
            if provider or model:
                routes[key] = {"provider": provider, "model": model}
    return providers, routes


def effective_llm() -> dict[str, Any]:
    public = _read_json(PUBLIC_PATH)
    secrets = _read_secrets()
    providers = env_providers()
    file_providers, file_routes = _file_llm(public)
    if file_providers:
        providers = file_providers
    else:
        providers.update(file_providers)
    keys = env_provider_keys()
    stored_keys = secrets.get("provider_keys") if isinstance(secrets.get("provider_keys"), dict) else {}
    for pid, value in stored_keys.items():
        keys[str(pid)] = str(value or "")
    routes = env_routes()
    for key, item in file_routes.items():
        current = dict(routes.get(key) or {})
        if item.get("provider"):
            current["provider"] = item["provider"]
        if item.get("model"):
            current["model"] = item["model"]
        if current.get("provider") not in providers and providers:
            current["provider"] = next(iter(providers))
        routes[key] = current
    for key, item in list(routes.items()):
        if item.get("provider") not in providers and providers:
            item["provider"] = next(iter(providers))
            routes[key] = item
    return {"providers": providers, "provider_keys": keys, "routes": routes}


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
    route = bundle["routes"].get(route_key_for(surface)) or bundle["routes"]["default"]
    provider_id = str(route.get("provider") or "openai")
    provider = bundle["providers"].get(provider_id) or {}
    chosen = (model or route.get("model") or settings.llm_model or "gpt-4o-mini").strip()
    protocol = str(provider.get("protocol") or "openai").strip().lower() or "openai"
    if _is_claude(chosen):
        protocol = "anthropic"
    api_key = str(bundle["provider_keys"].get(provider_id) or "").strip()
    if not api_key:
        api_key = (settings.llm_docs_api_key if protocol == "anthropic" else settings.llm_api_key) or ""
        api_key = api_key.strip()
    base_url = str(provider.get("base_url") or "").rstrip("/")
    if not base_url:
        base_url = (settings.llm_docs_base_url if protocol == "anthropic" else settings.llm_base_url) or ""
        base_url = base_url.rstrip("/")
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


def people_map() -> dict[str, str]:
    public = _read_json(PUBLIC_PATH)
    raw = public.get("people")
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items() if str(k).strip() and str(v).strip()}
    extra = (settings.cliq_people_json or "").strip()
    if extra:
        try:
            parsed = json.loads(extra)
            if isinstance(parsed, dict):
                return {str(k): str(v) for k, v in parsed.items() if str(k).strip()}
        except json.JSONDecodeError:
            pass
    return {}


def team_overlay() -> dict:
    public = _read_json(PUBLIC_PATH)
    raw = public.get("team")
    return raw if isinstance(raw, dict) else {}


def overlay_value(key: str) -> str:
    public = _read_json(PUBLIC_PATH)
    value = public.get(key)
    if value is None:
        return ""
    return str(value).strip()


def _sync_cliq_token_file(access: str, refresh: str) -> None:
    if not access and not refresh:
        return
    existing = _read_json(CLIQ_TOKEN_PATH)
    payload = {
        "access_token": access or existing.get("access_token") or "",
        "refresh_token": refresh or existing.get("refresh_token") or "",
    }
    if not payload["access_token"] and not payload["refresh_token"]:
        return
    _write_json(CLIQ_TOKEN_PATH, payload, private=True)


def apply_workspace() -> None:
    public = _read_json(PUBLIC_PATH)
    secrets = _read_secrets()
    for key in PUBLIC_SETTING_KEYS:
        if key not in public or public[key] is None:
            continue
        if not hasattr(settings, key):
            continue
        value = public[key]
        if key == "smtp_port":
            try:
                value = int(value)
            except (TypeError, ValueError):
                continue
        if key == "smtp_use_tls":
            value = bool(value)
        setattr(settings, key, value)
    for key in SECRET_SETTING_KEYS:
        if key in secrets and secrets[key] is not None and key != "gdrive_key_json":
            if hasattr(settings, key):
                setattr(settings, key, str(secrets[key] or ""))
    gdrive_json = str(secrets.get("gdrive_key_json") or "").strip()
    if gdrive_json:
        GDRIVE_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
        GDRIVE_KEY_PATH.write_text(gdrive_json, encoding="utf-8")
        try:
            os.chmod(GDRIVE_KEY_PATH, 0o600)
        except OSError:
            pass
        settings.gdrive_key_file = str(GDRIVE_KEY_PATH)
    people = people_map()
    if people:
        settings.cliq_people_json = json.dumps(people)
    bundle = effective_llm()
    default = bundle["routes"]["default"]
    default_provider = bundle["providers"].get(default.get("provider") or "", {})
    default_key = bundle["provider_keys"].get(default.get("provider") or "") or ""
    if default.get("model"):
        settings.llm_model = default["model"]
    if default_key:
        settings.llm_api_key = default_key
    if default_provider.get("base_url"):
        settings.llm_base_url = default_provider["base_url"]
    copilot = bundle["routes"]["copilot"]
    if copilot.get("model"):
        settings.llm_copilot_model = copilot["model"]
    docs = bundle["routes"]["docs"]
    docs_provider = bundle["providers"].get(docs.get("provider") or "", {})
    docs_key = bundle["provider_keys"].get(docs.get("provider") or "") or ""
    if docs.get("model"):
        settings.llm_docs_model = docs["model"]
    if docs_key:
        settings.llm_docs_api_key = docs_key
    if docs_provider.get("base_url"):
        settings.llm_docs_base_url = docs_provider["base_url"]
    if docs_provider.get("project"):
        settings.llm_docs_project = docs_provider["project"]
    marketing = bundle["routes"]["marketing"]
    if marketing.get("model"):
        settings.marketing_model = marketing["model"]
    access = str(secrets.get("cliq_access_token") or settings.cliq_access_token or "")
    refresh = str(secrets.get("cliq_refresh_token") or settings.cliq_refresh_token or "")
    if access or refresh:
        _sync_cliq_token_file(access, refresh)


def _providers_public(bundle: dict) -> list[dict]:
    rows = []
    for pid, meta in bundle["providers"].items():
        key = str(bundle["provider_keys"].get(pid) or "")
        rows.append(
            {
                "id": pid,
                "label": meta.get("label") or pid,
                "protocol": meta.get("protocol") or "openai",
                "base_url": meta.get("base_url") or "",
                "project": meta.get("project") or "",
                "api_key_set": bool(key),
                "api_key_hint": secret_hint(key),
            }
        )
    return rows


def public_settings() -> dict:
    from app.clients.cliq import CliqClient
    from app.clients.jira import JiraClient
    from app.clients.llm import LLMClient
    from app.services.profile import load_profile
    from app.services.team import product_internal_chat_id

    apply_workspace()
    profile = load_profile()
    public = _read_json(PUBLIC_PATH)
    secrets = _read_secrets()
    bundle = effective_llm()
    jira = JiraClient()
    cliq = CliqClient()
    llm = LLMClient()
    people = people_map()
    team = team_overlay()
    return {
        "pm_display_name": profile.get("pm_display_name") or "",
        "pm_cliq_user_id": profile.get("pm_cliq_user_id") or "",
        "pm_cliq_mentions": profile.get("pm_cliq_mentions") or "",
        "timezone": profile.get("timezone") or settings.timezone or "Asia/Kolkata",
        "data_branch": profile.get("data_branch") or "",
        "you": {
            "pm_display_name": profile.get("pm_display_name") or "",
            "pm_cliq_user_id": profile.get("pm_cliq_user_id") or "",
            "pm_cliq_mentions": profile.get("pm_cliq_mentions") or "",
            "timezone": profile.get("timezone") or settings.timezone or "Asia/Kolkata",
        },
        "jira": {
            "base_url": settings.jira_base_url or "",
            "email": settings.jira_email or "",
            "projects": settings.jira_projects or "",
            "token_set": bool((settings.jira_api_token or "").strip()),
            "token_hint": secret_hint(settings.jira_api_token),
            "configured": jira.configured,
        },
        "cliq": {
            "client_id": settings.cliq_client_id or "",
            "api_domain": settings.cliq_api_domain or "https://cliq.zoho.in",
            "accounts_url": settings.cliq_accounts_url or "https://accounts.zoho.in",
            "redirect_uri": settings.cliq_redirect_uri or "",
            "pm_email": settings.cliq_pm_email or "",
            "pm_chat_id": settings.cliq_pm_chat_id or "",
            "client_secret_set": bool((settings.cliq_client_secret or secrets.get("cliq_client_secret") or "").strip()),
            "refresh_token_set": bool((settings.cliq_refresh_token or secrets.get("cliq_refresh_token") or "").strip()),
            "access_token_set": bool((settings.cliq_access_token or secrets.get("cliq_access_token") or "").strip()),
            "client_secret_hint": secret_hint(settings.cliq_client_secret),
            "refresh_token_hint": secret_hint(settings.cliq_refresh_token),
            "access_token_hint": secret_hint(settings.cliq_access_token),
            "configured": cliq.configured,
        },
        "llm": {
            "providers": _providers_public(bundle),
            "routes": {key: dict(bundle["routes"].get(key) or {}) for key in ROUTE_KEYS},
            "route_labels": dict(ROUTE_LABELS),
            "configured": llm.configured,
        },
        "mail": {
            "release_notes_email": settings.release_notes_email or "",
            "smtp_host": settings.smtp_host or "",
            "smtp_port": settings.smtp_port,
            "smtp_user": settings.smtp_user or "",
            "smtp_from": settings.smtp_from or "",
            "smtp_use_tls": bool(settings.smtp_use_tls),
            "password_set": bool((settings.smtp_password or "").strip()),
            "password_hint": secret_hint(settings.smtp_password),
            "cron_token_set": bool((settings.release_notes_cron_token or "").strip()),
            "cron_token_hint": secret_hint(settings.release_notes_cron_token),
        },
        "workspace": {
            "codebase_path": settings.codebase_path or "",
            "data_branch": profile.get("data_branch") or "",
            "product_internal_chat_id": overlay_value("product_internal_chat_id") or product_internal_chat_id(),
            "gdrive_folder_id": settings.gdrive_folder_id or "",
            "gdrive_assets_folder_id": settings.gdrive_assets_folder_id or "",
            "gdrive_domain": settings.gdrive_domain or "",
            "marketing_sheet_id": settings.marketing_sheet_id or "",
            "marketing_sheet_tab": settings.marketing_sheet_tab or "",
            "cartesia_voice_id": settings.cartesia_voice_id or "",
            "cartesia_model": settings.cartesia_model or "",
            "cartesia_key_set": bool((settings.cartesia_api_key or "").strip()),
            "cartesia_key_hint": secret_hint(settings.cartesia_api_key),
            "gdrive_key_set": bool(str(secrets.get("gdrive_key_json") or "").strip() or Path(settings.gdrive_key_file or "").is_file()),
            "gdrive_key_hint": "saved encrypted" if str(secrets.get("gdrive_key_json") or "").strip() else "",
        },
        "people": people,
        "team": {
            "developers": team.get("developers") if isinstance(team.get("developers"), list) else [],
            "qa": team.get("qa") if isinstance(team.get("qa"), dict) else {},
            "using_defaults": not bool(team.get("developers") or team.get("qa")),
        },
        "connections": {"jira": jira.configured, "cliq": cliq.configured, "llm": llm.configured},
        "security": {
            "encrypted": secrets_are_encrypted(),
            "segments": segment_status(secrets),
        },
        "has_overlay": PUBLIC_PATH.is_file() or SECRETS_PATH.is_file(),
        "source": "settings",
        "jira_email": settings.jira_email,
        "jira_base_url": settings.jira_base_url,
    }


def _save_llm(public: dict, secrets: dict, payload: dict) -> None:
    bundle = effective_llm()
    providers = dict(bundle["providers"])
    keys = dict(bundle["provider_keys"])
    routes = {key: dict(bundle["routes"].get(key) or {}) for key in ROUTE_KEYS}
    incoming_providers = payload.get("providers")
    if isinstance(incoming_providers, list):
        next_providers: dict[str, dict] = {}
        next_keys: dict[str, str] = {}
        for index, item in enumerate(incoming_providers):
            if not isinstance(item, dict):
                continue
            pid = _slug(str(item.get("id") or item.get("label") or f"provider-{index + 1}"), f"provider-{index + 1}")
            next_providers[pid] = {
                "label": str(item.get("label") or pid),
                "protocol": str(item.get("protocol") or "openai").strip().lower() or "openai",
                "base_url": str(item.get("base_url") or "").rstrip("/"),
                "project": str(item.get("project") or "").strip(),
            }
            next_keys[pid] = merge_secret(
                keys.get(pid) or "",
                item.get("api_key"),
                bool(item.get("clear_api_key")),
            )
        providers = next_providers or providers
        keys = next_keys
    incoming_routes = payload.get("routes")
    if isinstance(incoming_routes, dict):
        for key in ROUTE_KEYS:
            item = incoming_routes.get(key)
            if not isinstance(item, dict):
                continue
            current = dict(routes.get(key) or {})
            if item.get("provider"):
                current["provider"] = _slug(str(item["provider"]), current.get("provider") or "openai")
            if item.get("model") is not None:
                current["model"] = str(item.get("model") or "").strip()
            routes[key] = current
    public["llm"] = {
        "providers": {
            pid: {
                "label": meta.get("label") or pid,
                "protocol": meta.get("protocol") or "openai",
                "base_url": meta.get("base_url") or "",
                "project": meta.get("project") or "",
            }
            for pid, meta in providers.items()
        },
        "routes": routes,
    }
    secrets["provider_keys"] = keys


def save_workspace(payload: dict) -> dict:
    public = _read_json(PUBLIC_PATH)
    secrets = _read_secrets()
    body = payload or {}

    jira = body.get("jira") if isinstance(body.get("jira"), dict) else None
    if jira:
        if jira.get("base_url") is not None:
            public["jira_base_url"] = str(jira.get("base_url") or "").strip().rstrip("/")
        if jira.get("email") is not None:
            public["jira_email"] = str(jira.get("email") or "").strip()
        if jira.get("projects") is not None:
            public["jira_projects"] = str(jira.get("projects") or "").strip()
        if "api_token" in jira or jira.get("clear_api_token"):
            secrets["jira_api_token"] = merge_secret(
                str(secrets.get("jira_api_token") or settings.jira_api_token or ""),
                jira.get("api_token"),
                bool(jira.get("clear_api_token")),
            )

    cliq = body.get("cliq") if isinstance(body.get("cliq"), dict) else None
    if cliq:
        for public_key, field in (
            ("cliq_client_id", "client_id"),
            ("cliq_api_domain", "api_domain"),
            ("cliq_accounts_url", "accounts_url"),
            ("cliq_redirect_uri", "redirect_uri"),
            ("cliq_pm_email", "pm_email"),
            ("cliq_pm_chat_id", "pm_chat_id"),
        ):
            if cliq.get(field) is not None:
                public[public_key] = str(cliq.get(field) or "").strip()
        for secret_key, field, clear_field in (
            ("cliq_client_secret", "client_secret", "clear_client_secret"),
            ("cliq_refresh_token", "refresh_token", "clear_refresh_token"),
            ("cliq_access_token", "access_token", "clear_access_token"),
        ):
            if field in cliq or cliq.get(clear_field):
                secrets[secret_key] = merge_secret(
                    str(secrets.get(secret_key) or getattr(settings, secret_key, "") or ""),
                    cliq.get(field),
                    bool(cliq.get(clear_field)),
                )

    mail = body.get("mail") if isinstance(body.get("mail"), dict) else None
    if mail:
        for public_key, field in (
            ("release_notes_email", "release_notes_email"),
            ("smtp_host", "smtp_host"),
            ("smtp_user", "smtp_user"),
            ("smtp_from", "smtp_from"),
        ):
            if mail.get(field) is not None:
                public[public_key] = str(mail.get(field) or "").strip()
        if mail.get("smtp_port") is not None:
            try:
                public["smtp_port"] = int(mail.get("smtp_port"))
            except (TypeError, ValueError):
                pass
        if mail.get("smtp_use_tls") is not None:
            public["smtp_use_tls"] = bool(mail.get("smtp_use_tls"))
        if "smtp_password" in mail or mail.get("clear_password"):
            secrets["smtp_password"] = merge_secret(
                str(secrets.get("smtp_password") or settings.smtp_password or ""),
                mail.get("smtp_password"),
                bool(mail.get("clear_password")),
            )
        if "cron_token" in mail or mail.get("clear_cron_token"):
            secrets["release_notes_cron_token"] = merge_secret(
                str(secrets.get("release_notes_cron_token") or settings.release_notes_cron_token or ""),
                mail.get("cron_token"),
                bool(mail.get("clear_cron_token")),
            )

    workspace = body.get("workspace") if isinstance(body.get("workspace"), dict) else None
    if workspace:
        for public_key, field in (
            ("codebase_path", "codebase_path"),
            ("product_internal_chat_id", "product_internal_chat_id"),
            ("gdrive_folder_id", "gdrive_folder_id"),
            ("gdrive_assets_folder_id", "gdrive_assets_folder_id"),
            ("gdrive_domain", "gdrive_domain"),
            ("marketing_sheet_id", "marketing_sheet_id"),
            ("marketing_sheet_tab", "marketing_sheet_tab"),
            ("cartesia_voice_id", "cartesia_voice_id"),
            ("cartesia_model", "cartesia_model"),
        ):
            if workspace.get(field) is not None:
                public[public_key] = str(workspace.get(field) or "").strip()
        if "cartesia_api_key" in workspace or workspace.get("clear_cartesia_key"):
            secrets["cartesia_api_key"] = merge_secret(
                str(secrets.get("cartesia_api_key") or settings.cartesia_api_key or ""),
                workspace.get("cartesia_api_key"),
                bool(workspace.get("clear_cartesia_key")),
            )
        if "gdrive_key_json" in workspace or workspace.get("clear_gdrive_key"):
            secrets["gdrive_key_json"] = merge_secret(
                str(secrets.get("gdrive_key_json") or ""),
                workspace.get("gdrive_key_json"),
                bool(workspace.get("clear_gdrive_key")),
            )

    if isinstance(body.get("people"), dict):
        public["people"] = {str(k): str(v) for k, v in body["people"].items() if str(k).strip()}
    if isinstance(body.get("team"), dict):
        public["team"] = body["team"]
    if isinstance(body.get("llm"), dict):
        _save_llm(public, secrets, body["llm"])

    _write_json(PUBLIC_PATH, public)
    _write_secrets(secrets)
    apply_workspace()
    return public_settings()


def store_cliq_tokens(access: str, refresh: str) -> None:
    secrets = _read_secrets()
    if access:
        secrets["cliq_access_token"] = access
        settings.cliq_access_token = access
    if refresh:
        secrets["cliq_refresh_token"] = refresh
        settings.cliq_refresh_token = refresh
    _write_secrets(secrets)


def capture_runtime() -> dict:
    from app.services.profile import load_profile, save_profile
    from app.services.team import product_internal_chat_id

    cached = _read_json(CLIQ_TOKEN_PATH)
    existing = _read_secrets()
    gdrive_json = str(existing.get("gdrive_key_json") or "")
    key_file = Path(settings.gdrive_key_file).expanduser() if settings.gdrive_key_file else None
    if key_file and key_file.is_file():
        try:
            gdrive_json = key_file.read_text(encoding="utf-8")
        except OSError:
            pass
    bundle = effective_llm()
    providers = [
        {
            "id": pid,
            "label": meta.get("label") or pid,
            "protocol": meta.get("protocol") or "openai",
            "base_url": meta.get("base_url") or "",
            "project": meta.get("project") or "",
            "api_key": bundle["provider_keys"].get(pid) or "",
        }
        for pid, meta in bundle["providers"].items()
    ]
    profile = load_profile()
    save_profile(
        {
            "pm_display_name": profile.get("pm_display_name") or settings.pm_display_name or "",
            "pm_cliq_user_id": profile.get("pm_cliq_user_id") or settings.pm_cliq_user_id or "",
            "pm_cliq_mentions": profile.get("pm_cliq_mentions") or settings.pm_cliq_mentions or "",
            "timezone": profile.get("timezone") or settings.timezone or "Asia/Kolkata",
            "data_branch": profile.get("data_branch") or "",
        }
    )
    payload: dict[str, Any] = {
        "jira": {
            "base_url": settings.jira_base_url,
            "email": settings.jira_email,
            "projects": settings.jira_projects,
            "api_token": settings.jira_api_token or existing.get("jira_api_token") or "",
        },
        "cliq": {
            "client_id": settings.cliq_client_id,
            "api_domain": settings.cliq_api_domain,
            "accounts_url": settings.cliq_accounts_url,
            "redirect_uri": settings.cliq_redirect_uri,
            "pm_email": settings.cliq_pm_email,
            "pm_chat_id": settings.cliq_pm_chat_id,
            "client_secret": settings.cliq_client_secret or existing.get("cliq_client_secret") or "",
            "refresh_token": cached.get("refresh_token")
            or settings.cliq_refresh_token
            or existing.get("cliq_refresh_token")
            or "",
            "access_token": cached.get("access_token")
            or settings.cliq_access_token
            or existing.get("cliq_access_token")
            or "",
        },
        "llm": {"providers": providers, "routes": bundle["routes"]},
        "mail": {
            "release_notes_email": settings.release_notes_email,
            "smtp_host": settings.smtp_host,
            "smtp_port": settings.smtp_port,
            "smtp_user": settings.smtp_user,
            "smtp_from": settings.smtp_from,
            "smtp_use_tls": settings.smtp_use_tls,
            "smtp_password": settings.smtp_password or existing.get("smtp_password") or "",
            "cron_token": settings.release_notes_cron_token or existing.get("release_notes_cron_token") or "",
        },
        "workspace": {
            "codebase_path": settings.codebase_path,
            "product_internal_chat_id": overlay_value("product_internal_chat_id") or product_internal_chat_id(),
            "gdrive_folder_id": settings.gdrive_folder_id,
            "gdrive_assets_folder_id": settings.gdrive_assets_folder_id,
            "gdrive_domain": settings.gdrive_domain,
            "marketing_sheet_id": settings.marketing_sheet_id,
            "marketing_sheet_tab": settings.marketing_sheet_tab,
            "cartesia_voice_id": settings.cartesia_voice_id or settings.marketing_cartesia_voice_id,
            "cartesia_model": settings.cartesia_model,
            "cartesia_api_key": settings.cartesia_api_key or existing.get("cartesia_api_key") or "",
            "gdrive_key_json": gdrive_json,
        },
    }
    people = people_map()
    if people:
        payload["people"] = people
    return save_workspace(payload)

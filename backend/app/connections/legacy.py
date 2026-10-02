"""Read the single-tenant configuration (data/*.json overlays, the Fernet-encrypted secrets file,
the Cliq token cache, the Google key file and `.env`) into per-provider connection values.

Used once by `scripts/migrate_to_workspaces.py`, and by "Import from environment" in local mode.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import dotenv_values
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

ROUTE_KEYS = ("default", "prototype", "copilot", "docs", "marketing")
VOICE_ENV_PREFIXES = ("CARTESIA_", "ELEVENLABS_", "HEYGEN_")


@dataclass
class LegacyConfig:
    connections: dict[str, dict] = field(default_factory=dict)
    profile: dict[str, Any] = field(default_factory=dict)
    people: dict[str, str] = field(default_factory=dict)
    team: dict = field(default_factory=dict)
    codebase_path: str = ""
    warnings: list[str] = field(default_factory=list)


def _read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _decrypt_secrets(data_dir: Path, warnings: list[str]) -> dict:
    raw = _read_json(data_dir / "workspace.secrets.json")
    if not raw:
        return {}
    if not raw.get("encrypted"):
        return {str(k): v for k, v in raw.items() if k not in {"encrypted", "version", "segments"}}
    key_path = data_dir / "workspace.key"
    if not key_path.is_file():
        warnings.append("workspace.secrets.json is encrypted but workspace.key is missing; secrets skipped.")
        return {}
    from cryptography.fernet import Fernet, InvalidToken

    fernet = Fernet(key_path.read_bytes().strip())
    flat: dict[str, Any] = {}
    for name, blob in (raw.get("segments") or {}).items():
        try:
            payload = json.loads(fernet.decrypt(str(blob).encode()).decode()) if isinstance(blob, str) else dict(blob or {})
        except (InvalidToken, ValueError):
            warnings.append(f"Could not decrypt the {name} secrets segment.")
            continue
        if name == "llm":
            keys = payload.get("provider_keys") if isinstance(payload.get("provider_keys"), dict) else {}
            flat["provider_keys"] = {str(k): str(v or "") for k, v in keys.items()}
            continue
        flat.update({str(k): v for k, v in payload.items()})
    return flat


def _first(*values: Any) -> str:
    for value in values:
        text = str(value if value is not None else "").strip()
        if text:
            return text
    return ""


def _llm(public: dict, secrets: dict, env: dict) -> dict:
    block = public.get("llm") if isinstance(public.get("llm"), dict) else {}
    providers: dict[str, dict] = {}
    raw = block.get("providers") or {}
    items = raw.items() if isinstance(raw, dict) else ((item.get("id") or item.get("label"), item) for item in raw if isinstance(item, dict))
    for pid, item in items:
        if not pid or not isinstance(item, dict):
            continue
        providers[str(pid)] = {
            "label": str(item.get("label") or pid),
            "protocol": str(item.get("protocol") or "openai"),
            "base_url": str(item.get("base_url") or "").rstrip("/"),
            "project": str(item.get("project") or ""),
        }
    keys = dict(secrets.get("provider_keys") or {})
    default_model = _first(env.get("LLM_MODEL"), "gpt-4o-mini")
    docs_model = _first(env.get("LLM_DOCS_MODEL"), env.get("MARKETING_MODEL"))
    if not providers:
        providers["openai"] = {"label": "OpenAI", "protocol": "openai", "base_url": _first(env.get("LLM_BASE_URL"), "https://api.openai.com/v1").rstrip("/"), "project": ""}
        if env.get("LLM_DOCS_API_KEY") or docs_model:
            providers["docs"] = {
                "label": "Claude" if "claude" in docs_model.lower() else "Docs",
                "protocol": "anthropic" if "claude" in docs_model.lower() else "openai",
                "base_url": _first(env.get("LLM_DOCS_BASE_URL"), env.get("LLM_BASE_URL")).rstrip("/"),
                "project": _first(env.get("LLM_DOCS_PROJECT")),
            }
    keys.setdefault("openai", _first(env.get("LLM_API_KEY")))
    if "docs" in providers:
        keys.setdefault("docs", _first(env.get("LLM_DOCS_API_KEY"), env.get("LLM_API_KEY")))
    docs_provider = "docs" if "docs" in providers else next(iter(providers))
    routes = {
        "default": {"provider": "openai" if "openai" in providers else next(iter(providers)), "model": default_model},
        "prototype": {"provider": "openai" if "openai" in providers else next(iter(providers)), "model": default_model},
        "copilot": {"provider": "openai" if "openai" in providers else next(iter(providers)), "model": _first(env.get("LLM_COPILOT_MODEL"), default_model)},
        "docs": {"provider": docs_provider, "model": _first(docs_model, default_model)},
        "marketing": {"provider": docs_provider, "model": _first(env.get("MARKETING_MODEL"), docs_model, default_model)},
    }
    for key, item in (block.get("routes") or {}).items():
        if key in routes and isinstance(item, dict):
            if item.get("provider") in providers:
                routes[key]["provider"] = item["provider"]
            if item.get("model"):
                routes[key]["model"] = str(item["model"])
    return {
        "providers": [{"id": pid, **meta, "api_key": keys.get(pid) or ""} for pid, meta in providers.items()],
        "routes": routes,
    }


def _env_files(env_file: Path | None) -> dict[str, str]:
    """The repo `.env`, then the Sense_Communication voice env files for keys `.env` leaves empty."""
    env: dict[str, str] = {}
    if env_file is None:
        return env
    reference = (env_file.parent / "Sense_Communication" / "remotion" / ".env", env_file.parent / "Sense_Communication" / "web" / ".env.local")
    for path in (env_file, *reference):
        if not path.is_file():
            continue
        for key, value in dotenv_values(path).items():
            if path != env_file and not key.startswith(VOICE_ENV_PREFIXES):
                continue
            if (value or "").strip() and not env.get(key):
                env[key] = value or ""
    return env


def read_legacy(data_dir: Path, env_file: Path | None = None) -> LegacyConfig:
    out = LegacyConfig()
    env = _env_files(env_file)
    public = _read_json(data_dir / "workspace.json")
    secrets = _decrypt_secrets(data_dir, out.warnings)
    cliq_cache = _read_json(data_dir / "cliq_token.json")

    def pick(public_key: str, env_key: str, default: str = "") -> str:
        return _first(public.get(public_key), env.get(env_key), default)

    def secret(key: str, env_key: str) -> str:
        return _first(secrets.get(key), env.get(env_key))

    out.connections["jira"] = {
        "base_url": pick("jira_base_url", "JIRA_BASE_URL"),
        "email": pick("jira_email", "JIRA_EMAIL"),
        "api_token": secret("jira_api_token", "JIRA_API_TOKEN"),
        "projects": pick("jira_projects", "JIRA_PROJECTS"),
        "allowed_projects": _first(env.get("JIRA_ALLOWED_PROJECTS")),
    }
    out.connections["cliq"] = {
        "client_id": pick("cliq_client_id", "CLIQ_CLIENT_ID"),
        "client_secret": secret("cliq_client_secret", "CLIQ_CLIENT_SECRET"),
        "api_domain": pick("cliq_api_domain", "CLIQ_API_DOMAIN", "https://cliq.zoho.in"),
        "accounts_url": pick("cliq_accounts_url", "CLIQ_ACCOUNTS_URL", "https://accounts.zoho.in"),
        "pm_email": pick("cliq_pm_email", "CLIQ_PM_EMAIL"),
        "pm_chat_id": pick("cliq_pm_chat_id", "CLIQ_PM_CHAT_ID"),
        "product_internal_chat_id": _first(public.get("product_internal_chat_id")),
        "refresh_token": _first(cliq_cache.get("refresh_token"), secrets.get("cliq_refresh_token"), env.get("CLIQ_REFRESH_TOKEN")),
        "access_token": _first(cliq_cache.get("access_token"), secrets.get("cliq_access_token"), env.get("CLIQ_ACCESS_TOKEN")),
    }
    out.connections["llm"] = _llm(public, secrets, env)

    gdrive_json = _first(secrets.get("gdrive_key_json"))
    key_file = Path(_first(env.get("GDRIVE_KEY_FILE"))).expanduser() if env.get("GDRIVE_KEY_FILE") else None
    for candidate in (key_file, data_dir / "workspace.gdrive.json"):
        if not gdrive_json and candidate and candidate.is_file():
            try:
                gdrive_json = candidate.read_text(encoding="utf-8").strip()
            except OSError:
                pass
    out.connections["google"] = {
        "service_account_json": gdrive_json,
        "folder_id": pick("gdrive_folder_id", "GDRIVE_FOLDER_ID"),
        "assets_folder_id": pick("gdrive_assets_folder_id", "GDRIVE_ASSETS_FOLDER_ID"),
        "drive_root": pick("marketing_drive_root", "MARKETING_DRIVE_ROOT"),
        "domain": pick("gdrive_domain", "GDRIVE_DOMAIN"),
        "sheet_id": pick("marketing_sheet_id", "MARKETING_SHEET_ID"),
        "sheet_tab": pick("marketing_sheet_tab", "MARKETING_SHEET_TAB"),
        "release_note_template_doc_id": pick("release_note_template_doc_id", "RELEASE_NOTE_TEMPLATE_DOC_ID"),
    }
    out.connections["smtp"] = {
        "host": pick("smtp_host", "SMTP_HOST"),
        "port": pick("smtp_port", "SMTP_PORT", "587"),
        "user": pick("smtp_user", "SMTP_USER"),
        "password": secret("smtp_password", "SMTP_PASSWORD"),
        "from_address": pick("smtp_from", "SMTP_FROM"),
        "use_tls": _first(public.get("smtp_use_tls"), env.get("SMTP_USE_TLS"), "true"),
        "release_notes_email": pick("release_notes_email", "RELEASE_NOTES_EMAIL"),
    }
    out.connections["cartesia"] = {
        "api_key": secret("cartesia_api_key", "CARTESIA_API_KEY"),
        "voice_id": pick("cartesia_voice_id", "CARTESIA_VOICE_ID"),
        "model": pick("cartesia_model", "CARTESIA_MODEL", "sonic-3"),
        "marketing_voice_id": pick("marketing_cartesia_voice_id", "MARKETING_CARTESIA_VOICE_ID"),
        "avatar_voice_id": pick("avatar_cartesia_voice_id", "AVATAR_CARTESIA_VOICE_ID"),
        "avatar_voice_name": pick("avatar_cartesia_voice_name", "AVATAR_CARTESIA_VOICE_NAME"),
        "avatar_locale": pick("avatar_cartesia_locale", "AVATAR_CARTESIA_LOCALE", "en-IN"),
        "avatar_accent": pick("avatar_cartesia_accent", "AVATAR_CARTESIA_ACCENT"),
    }
    out.connections["heygen"] = {
        "api_key": secret("heygen_api_key", "HEYGEN_API_KEY"),
        "base_url": pick("heygen_base_url", "HEYGEN_BASE_URL", "https://api.heygen.com"),
        "voice_id": pick("heygen_voice_id", "HEYGEN_VOICE_ID"),
        "voice_name": pick("heygen_voice_name", "HEYGEN_VOICE_NAME"),
    }
    out.connections["elevenlabs"] = {
        "api_key": secret("elevenlabs_api_key", "ELEVENLABS_API_KEY"),
        "voice_id": pick("elevenlabs_voice_id", "ELEVENLABS_VOICE_ID"),
        "voice_name": pick("elevenlabs_voice_name", "ELEVENLABS_VOICE_NAME"),
    }

    profile_file = _read_json(data_dir / "profile.json")
    out.profile = {
        "pm_display_name": _first(profile_file.get("pm_display_name"), public.get("pm_display_name"), env.get("PM_DISPLAY_NAME")),
        "pm_cliq_user_id": _first(profile_file.get("pm_cliq_user_id"), public.get("pm_cliq_user_id"), env.get("PM_CLIQ_USER_ID")),
        "pm_cliq_mentions": _first(profile_file.get("pm_cliq_mentions"), public.get("pm_cliq_mentions"), env.get("PM_CLIQ_MENTIONS")),
        "project_keywords": _first(env.get("PROJECT_KEYWORDS")),
        "data_branch": _first(profile_file.get("data_branch"), public.get("data_branch")),
        "timezone": _first(profile_file.get("timezone"), public.get("timezone"), env.get("TIMEZONE"), "Asia/Kolkata"),
        "standup_hour": _first(env.get("STANDUP_HOUR"), "9"),
        "release_notes_hour": _first(env.get("RELEASE_NOTES_HOUR"), "10"),
    }
    people = public.get("people") if isinstance(public.get("people"), dict) else {}
    people_file = _read_json(data_dir / "people.json")
    out.people = {**{str(k): str(v) for k, v in people_file.items()}, **{str(k): str(v) for k, v in people.items()}}
    out.team = public.get("team") if isinstance(public.get("team"), dict) else {}
    out.codebase_path = _first(public.get("codebase_path"), env.get("CODEBASE_PATH"))
    return out


def has_values(provider: str, values: dict) -> bool:
    if provider == "llm":
        return any(str(item.get("api_key") or "").strip() for item in values.get("providers") or [])
    from app.connections.registry import get_provider

    spec = get_provider(provider)
    for f in spec.fields:
        value = str(values.get(f.key) or "").strip()
        if value and (f.secret or f.required or value != str(f.default or "")):
            return True
    return False


def import_connections(db: Session, legacy: LegacyConfig, *, actor: str = "migration", overwrite: bool = False) -> dict[str, str]:
    """Save each provider that has credentials into the active workspace. Returns provider → outcome."""
    from app.connections import store

    outcome: dict[str, str] = {}
    for provider, values in legacy.connections.items():
        if not has_values(provider, values):
            outcome[provider] = "skipped (no credentials)"
            continue
        if store.get_connection(db, provider) is not None and not overwrite:
            outcome[provider] = "kept existing"
            continue
        clean = {key: value for key, value in values.items() if value not in (None, "")}
        store.save_connection(db, provider, clean, actor=actor)
        outcome[provider] = "imported"
    return outcome

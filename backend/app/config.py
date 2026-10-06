"""Platform settings plus a per-workspace view.

`Settings` reads the environment once per process. Platform fields (database, auth, storage,
worker) always come from there. Workspace fields (every integration credential and the product
profile) resolve from the active `WorkspaceContext`, which is built from that workspace's
connections. Outside a workspace (CLI, tests without a context) the environment value is used.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app import context

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Platform (environment only)
    app_name: str = "Product OS"
    environment: str = "development"
    data_dir: str = str(ROOT / "data")
    database_url: str = ""
    app_encryption_key: str = ""
    auth_mode: str = "local"
    clerk_issuer: str = ""
    clerk_jwks_url: str = ""
    clerk_secret_key: str = ""
    clerk_webhook_secret: str = ""
    clerk_authorized_parties: str = ""
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    public_app_url: str = "http://localhost:3000"
    local_workspace_slug: str = ""
    local_workspace_name: str = "My workspace"
    local_user_email: str = ""
    run_worker: str = "inline"
    worker_concurrency: int = 4
    run_scheduler: bool = True
    egress_ip_url: str = "https://api.ipify.org"
    remotion_dir: str = ""
    prototype_kit_dir: str = ""
    source_index_keep: int = 3
    max_cliq_chats: int = 40
    max_messages_per_chat: int = 80
    codebase_pull: bool = True
    marketing_parallel_formats: int = 6
    release_notes_enable_scheduler: bool = True
    release_notes_fresh_days: int = 3
    release_shots_enabled: bool = True
    release_shots_node: str = ""

    # Workspace (resolved from connections and the product profile)
    timezone: str = "Asia/Kolkata"
    standup_hour: int = 9
    standup_nudge_minute: int = 55
    release_notes_hour: int = 10

    jira_base_url: str = ""
    jira_projects: str = ""
    jira_email: str = ""
    jira_api_token: str = ""
    jira_allowed_projects: str = ""

    cliq_client_id: str = ""
    cliq_client_secret: str = ""
    cliq_refresh_token: str = ""
    cliq_access_token: str = ""
    cliq_api_domain: str = "https://cliq.zoho.in"
    cliq_accounts_url: str = "https://accounts.zoho.in"
    cliq_redirect_uri: str = ""
    cliq_pm_chat_id: str = ""
    cliq_pm_email: str = ""
    cliq_people_json: str = ""
    cliq_product_internal_chat_id: str = ""
    cliq_wallet_chat_id: str = ""

    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_copilot_model: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_docs_api_key: str = ""
    llm_docs_model: str = ""
    marketing_model: str = "claude-opus-5-5"
    llm_docs_base_url: str = ""
    llm_docs_project: str = ""

    pm_display_name: str = ""
    pm_cliq_user_id: str = ""
    pm_cliq_mentions: str = ""
    project_keywords: str = "checkout,campaign,analytics,audit,agent"
    product_name: str = ""
    company_name: str = ""
    support_email: str = ""

    codebase_path: str = ""
    repository_id: int = 0
    repo_mode: str = "local"
    repo_default_branch: str = ""
    repo_release_pattern: str = "release/YYYY-MM-DD"
    repo_merge_format: str = "any"
    repo_path_scopes: str = ""
    repo_ui_path: str = ""

    release_notes_email: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True
    release_notes_cron_token: str = ""
    release_shots_ui_path: str = ""
    release_note_template_doc_id: str = ""

    gdrive_key_file: str = ""
    gdrive_key_json: str = ""
    gdrive_folder_id: str = ""
    gdrive_assets_folder_id: str = ""
    gdrive_domain: str = ""
    marketing_drive_root: str = ""
    marketing_sheet_id: str = ""
    marketing_sheet_tab: str = ""
    cartesia_api_key: str = ""
    cartesia_voice_id: str = ""
    cartesia_model: str = "sonic-3"
    marketing_cartesia_voice_id: str = ""
    heygen_api_key: str = ""
    heygen_base_url: str = "https://api.heygen.com"
    heygen_voice_id: str = ""
    heygen_voice_name: str = ""
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = ""
    elevenlabs_voice_name: str = ""
    avatar_cartesia_voice_id: str = ""
    avatar_cartesia_voice_name: str = ""
    avatar_cartesia_locale: str = "en-IN"
    avatar_cartesia_accent: str = ""
    prototype_kit: str = "starter"

    @model_validator(mode="after")
    def _derive(self) -> "Settings":
        if not self.database_url:
            self.database_url = f"sqlite:///{Path(self.data_dir) / 'platform.db'}"
        self.database_url = normalize_database_url(self.database_url)
        return self


def normalize_database_url(url: str) -> str:
    text = (url or "").strip()
    if text.startswith("postgres://"):
        text = "postgresql://" + text[len("postgres://"):]
    if text.startswith("postgresql://"):
        text = "postgresql+psycopg://" + text[len("postgresql://"):]
    return text


PLATFORM_FIELDS = frozenset(
    {
        "app_name",
        "environment",
        "data_dir",
        "database_url",
        "app_encryption_key",
        "auth_mode",
        "clerk_issuer",
        "clerk_jwks_url",
        "clerk_secret_key",
        "clerk_webhook_secret",
        "clerk_authorized_parties",
        "allowed_origins",
        "public_app_url",
        "local_workspace_slug",
        "local_workspace_name",
        "local_user_email",
        "run_worker",
        "worker_concurrency",
        "run_scheduler",
        "egress_ip_url",
        "remotion_dir",
        "prototype_kit_dir",
        "source_index_keep",
        "max_cliq_chats",
        "max_messages_per_chat",
        "codebase_pull",
        "marketing_parallel_formats",
        "release_notes_enable_scheduler",
        "release_notes_fresh_days",
        "release_shots_enabled",
        "release_shots_node",
    }
)
WORKSPACE_FIELDS = frozenset(name for name in Settings.model_fields if name not in PLATFORM_FIELDS)
_DEFAULTS: dict[str, Any] = {name: field.default for name, field in Settings.model_fields.items()}


def field_default(name: str) -> Any:
    return _DEFAULTS.get(name)


class SettingsProxy:
    """`settings.x` reads the workspace value inside a workspace and the env value outside."""

    __slots__ = ("_base",)

    def __init__(self, base: Settings) -> None:
        object.__setattr__(self, "_base", base)

    def __getattr__(self, name: str) -> Any:
        if name in WORKSPACE_FIELDS:
            ctx = context.current()
            if ctx is not None:
                if name in ctx.values:
                    return ctx.values[name]
                return _DEFAULTS.get(name)
        return getattr(object.__getattribute__(self, "_base"), name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in WORKSPACE_FIELDS:
            ctx = context.current()
            if ctx is not None:
                ctx.values[name] = value
                return
        setattr(object.__getattribute__(self, "_base"), name, value)

    def __delattr__(self, name: str) -> None:
        ctx = context.current()
        if name in WORKSPACE_FIELDS and ctx is not None:
            ctx.values.pop(name, None)
            return
        delattr(object.__getattribute__(self, "_base"), name)

    @property
    def base(self) -> Settings:
        return object.__getattribute__(self, "_base")

    def env_value(self, name: str) -> Any:
        return getattr(object.__getattribute__(self, "_base"), name)

    @property
    def is_production(self) -> bool:
        return (self.env_value("environment") or "").strip().lower() in {"production", "prod"}

    @property
    def origins(self) -> list[str]:
        return [item.strip().rstrip("/") for item in (self.env_value("allowed_origins") or "").split(",") if item.strip()]


settings = SettingsProxy(Settings())


def data_root() -> Path:
    return Path(settings.env_value("data_dir")).expanduser()


PLACEHOLDERS = {
    "",
    "changeme",
    "change-me",
    "your-key",
    "your_key",
    "xxx",
    "todo",
    "replace-me",
    "placeholder",
    "sk-xxx",
    "x" * 8,
}


def _is_placeholder(value: str) -> bool:
    text = (value or "").strip()
    if not text:
        return True
    lowered = text.lower()
    if lowered in PLACEHOLDERS:
        return True
    if lowered.startswith("your-") or lowered.startswith("<") or lowered.endswith(">"):
        return True
    if "example" in lowered or "placeholder" in lowered:
        return True
    return False


def platform_problems() -> list[str]:
    """Hosting configuration that must be fixed before a production boot. Integrations are optional."""
    problems: list[str] = []
    if settings.is_production:
        if _is_placeholder(settings.env_value("app_encryption_key")):
            problems.append("APP_ENCRYPTION_KEY")
        if (settings.env_value("auth_mode") or "").strip().lower() != "clerk":
            problems.append("AUTH_MODE=clerk")
        if not (settings.env_value("clerk_issuer") or settings.env_value("clerk_jwks_url")):
            problems.append("CLERK_ISSUER")
        if settings.env_value("database_url").startswith("sqlite"):
            problems.append("DATABASE_URL (Postgres)")
    return problems


def validate_startup() -> None:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return
    problems = platform_problems()
    if problems:
        raise RuntimeError("Product OS cannot start in production until these are set: " + ", ".join(problems))

import os
import sys

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AI PM Daily Standup Agent"
    timezone: str = "Asia/Kolkata"
    standup_hour: int = 9
    database_url: str = f"sqlite:///{ROOT / 'data' / 'pm_agent.db'}"

    jira_base_url: str = ""
    jira_projects: str = "AC,PS"
    jira_email: str = ""
    jira_api_token: str = ""

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

    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_copilot_model: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_docs_api_key: str = ""
    llm_docs_model: str = ""
    marketing_model: str = "claude-opus-4-8"
    llm_docs_base_url: str = ""
    llm_docs_project: str = ""

    pm_display_name: str = ""
    pm_cliq_user_id: str = ""
    pm_cliq_mentions: str = ""
    project_keywords: str = "checkout,campaign,analytics,audit,agent"

    max_cliq_chats: int = 40
    max_messages_per_chat: int = 80

    codebase_path: str = ""
    codebase_pull: bool = True

    release_notes_hour: int = 10
    release_notes_email: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_use_tls: bool = True
    release_notes_enable_scheduler: bool = True
    release_notes_fresh_days: int = 3
    release_notes_cron_token: str = ""
    standup_nudge_minute: int = 55
    strict_config: bool = True

    gdrive_key_file: str = ""
    gdrive_folder_id: str = ""
    gdrive_assets_folder_id: str = ""
    gdrive_domain: str = "convin.ai"
    marketing_sheet_id: str = "1K1iC6I8k3UL77ik7tqvLHyHcA3t0egldebrYovmiDiI"
    marketing_sheet_tab: str = ""
    cartesia_api_key: str = ""
    cartesia_voice_id: str = ""
    cartesia_model: str = "sonic-3"
    marketing_cartesia_voice_id: str = ""  # Optional override for the marketing female narrator.


settings = Settings()


def apply_settings_overlay() -> None:
    try:
        from app.services.workspace import apply_workspace

        apply_workspace()
    except Exception:
        return


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


def missing_required_settings() -> list[str]:
    required = [
        ("JIRA_EMAIL", settings.jira_email),
        ("JIRA_API_TOKEN", settings.jira_api_token),
        ("LLM_API_KEY", settings.llm_api_key),
    ]
    return [name for name, value in required if _is_placeholder(value)]


def validate_startup() -> None:
    apply_settings_overlay()
    if not settings.strict_config:
        return
    if os.environ.get("PYTEST_CURRENT_TEST") or "pytest" in sys.modules:
        return
    missing = missing_required_settings()
    if missing:
        raise RuntimeError(
            "PM Platform cannot start — set these in Settings or .env (not placeholders): " + ", ".join(missing)
        )

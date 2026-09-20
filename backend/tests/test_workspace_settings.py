import json

from app.clients.jira import JiraClient
from app.clients.llm import LLMClient, model_for
from app.config import settings


def _patch_paths(monkeypatch, tmp_path):
    from app.services import workspace

    monkeypatch.setattr(workspace, "PUBLIC_PATH", tmp_path / "workspace.json")
    monkeypatch.setattr(workspace, "SECRETS_PATH", tmp_path / "secrets.json")
    monkeypatch.setattr(workspace, "KEY_PATH", tmp_path / "workspace.key")
    monkeypatch.setattr(workspace, "CLIQ_TOKEN_PATH", tmp_path / "cliq_token.json")
    monkeypatch.setattr(workspace, "GDRIVE_KEY_PATH", tmp_path / "gdrive.json")


def _snap():
    return {
        "jira_base_url": settings.jira_base_url,
        "jira_email": settings.jira_email,
        "jira_api_token": settings.jira_api_token,
        "llm_model": settings.llm_model,
        "llm_api_key": settings.llm_api_key,
        "llm_base_url": settings.llm_base_url,
        "llm_docs_model": settings.llm_docs_model,
        "llm_docs_api_key": settings.llm_docs_api_key,
        "llm_copilot_model": settings.llm_copilot_model,
        "marketing_model": settings.marketing_model,
        "pm_display_name": settings.pm_display_name,
        "pm_cliq_user_id": settings.pm_cliq_user_id,
        "pm_cliq_mentions": settings.pm_cliq_mentions,
        "cliq_client_id": settings.cliq_client_id,
        "cliq_client_secret": settings.cliq_client_secret,
        "cliq_refresh_token": settings.cliq_refresh_token,
        "cliq_access_token": settings.cliq_access_token,
        "codebase_path": settings.codebase_path,
    }


def _restore(snap: dict) -> None:
    for key, value in snap.items():
        setattr(settings, key, value)


def test_jira_overlay_masks_token(tmp_path, monkeypatch):
    from app.services import workspace

    snap = _snap()
    _patch_paths(monkeypatch, tmp_path)
    try:
        public = workspace.save_workspace(
            {
                "jira": {
                    "base_url": "https://acme.atlassian.net",
                    "email": "pm@acme.com",
                    "projects": "AC",
                    "api_token": "super-secret-token-12345",
                }
            }
        )
        dumped = json.dumps(public)
        assert "super-secret-token-12345" not in dumped
        assert public["jira"]["token_set"] is True
        assert public["jira"]["email"] == "pm@acme.com"
        assert settings.jira_api_token == "super-secret-token-12345"
        assert JiraClient().configured
        raw = json.loads((tmp_path / "secrets.json").read_text())
        assert raw.get("encrypted") is True
        dumped = (tmp_path / "secrets.json").read_text()
        assert "super-secret-token-12345" not in dumped
        assert workspace._read_secrets()["jira_api_token"] == "super-secret-token-12345"
    finally:
        _restore(snap)


def test_empty_secret_patch_keeps_token(tmp_path, monkeypatch):
    from app.services import workspace

    snap = _snap()
    _patch_paths(monkeypatch, tmp_path)
    try:
        workspace.save_workspace({"jira": {"api_token": "keep-me-token-9999", "email": "a@b.com", "base_url": "https://x.atlassian.net"}})
        workspace.save_workspace({"jira": {"api_token": "", "email": "a@b.com"}})
        assert settings.jira_api_token == "keep-me-token-9999"
        workspace.save_workspace({"jira": {"api_token": "********", "email": "a@b.com"}})
        assert settings.jira_api_token == "keep-me-token-9999"
        workspace.save_workspace({"jira": {"clear_api_token": True}})
        assert settings.jira_api_token == ""
    finally:
        _restore(snap)


def test_prototype_route_uses_mapped_provider(tmp_path, monkeypatch):
    from app.services import workspace

    snap = _snap()
    _patch_paths(monkeypatch, tmp_path)
    try:
        workspace.save_workspace(
            {
                "llm": {
                    "providers": [
                        {
                            "id": "openai",
                            "label": "OpenAI",
                            "protocol": "openai",
                            "base_url": "https://api.openai.com/v1",
                            "api_key": "sk-live-openai",
                        },
                        {
                            "id": "studio",
                            "label": "Studio",
                            "protocol": "openai",
                            "base_url": "https://studio.example/v1",
                            "api_key": "sk-proto-key",
                        },
                    ],
                    "routes": {
                        "default": {"provider": "openai", "model": "gpt-4o"},
                        "prototype": {"provider": "studio", "model": "gpt-4o-mini"},
                        "copilot": {"provider": "openai", "model": "gpt-5.6-luna"},
                    },
                }
            }
        )
        assert model_for("prototype") == "gpt-4o-mini"
        client = LLMClient(surface="prototype")
        assert client.model == "gpt-4o-mini"
        assert client.api_key == "sk-proto-key"
        assert client.base_url == "https://studio.example/v1"
        public = workspace.public_settings()
        assert "sk-proto-key" not in json.dumps(public)
        assert public["llm"]["routes"]["prototype"]["provider"] == "studio"
    finally:
        _restore(snap)


def test_profile_does_not_inject_arsalaan(tmp_path, monkeypatch):
    from app.services import profile

    snap = _snap()
    monkeypatch.setattr(profile, "PROFILE_PATH", tmp_path / "profile.json")
    monkeypatch.setattr(settings, "pm_display_name", "")
    monkeypatch.setattr(settings, "pm_cliq_user_id", "")
    monkeypatch.setattr(settings, "pm_cliq_mentions", "")
    try:
        loaded = profile.load_profile()
        assert loaded["pm_display_name"] == ""
        assert loaded["pm_cliq_user_id"] == ""
        assert "60031811823" not in loaded["pm_cliq_mentions"]
        assert loaded["pm_display_name"] != "Arsalaan"
    finally:
        _restore(snap)


def test_cliq_save_writes_token_file_not_env(tmp_path, monkeypatch):
    from app.services import workspace

    snap = _snap()
    token_path = tmp_path / "cliq_token.json"
    _patch_paths(monkeypatch, tmp_path)
    try:
        workspace.save_workspace(
            {
                "cliq": {
                    "client_id": "client-1",
                    "client_secret": "secret-1",
                    "refresh_token": "refresh-1",
                    "access_token": "access-1",
                    "api_domain": "https://cliq.zoho.in",
                }
            }
        )
        saved = json.loads(token_path.read_text())
        assert saved["access_token"] == "access-1"
        assert saved["refresh_token"] == "refresh-1"
        public = workspace.public_settings()
        assert public["cliq"]["configured"] is True
        assert "secret-1" not in json.dumps(public)
        assert "secret-1" not in (tmp_path / "secrets.json").read_text()
        assert workspace._read_secrets()["cliq_client_secret"] == "secret-1"
    finally:
        _restore(snap)


def test_encrypted_segments_round_trip(tmp_path, monkeypatch):
    from app.services import workspace

    snap = _snap()
    _patch_paths(monkeypatch, tmp_path)
    try:
        workspace.save_workspace(
            {
                "jira": {"api_token": "jira-secret-aaaa"},
                "mail": {"smtp_password": "smtp-secret-bbbb"},
                "workspace": {"cartesia_api_key": "cartesia-secret-cccc"},
            }
        )
        raw = json.loads((tmp_path / "secrets.json").read_text())
        assert set(raw["segments"]) == {"jira", "cliq", "llm", "mail", "marketing"}
        blob = (tmp_path / "secrets.json").read_text()
        assert "jira-secret-aaaa" not in blob
        assert "smtp-secret-bbbb" not in blob
        assert "cartesia-secret-cccc" not in blob
        loaded = workspace._read_secrets()
        assert loaded["jira_api_token"] == "jira-secret-aaaa"
        assert loaded["smtp_password"] == "smtp-secret-bbbb"
        assert loaded["cartesia_api_key"] == "cartesia-secret-cccc"
        assert workspace.public_settings()["security"]["encrypted"] is True
    finally:
        _restore(snap)

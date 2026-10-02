import json
import uuid

import pytest

from app import context
from app.clients.jira import JiraClient
from app.clients.llm import LLMClient, model_for
from app.config import ROOT, settings
from app.connections import crypto, store
from app.connections.registry import get_provider
from app.database import SessionLocal
from app.workspaces import create_workspace, in_workspace


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _workspace(db, **profile):
    ws = create_workspace(db, f"Settings {uuid.uuid4().hex[:6]}", profile=profile or None)
    return ws, context.WorkspaceContext(id=ws.id, slug=ws.slug, name=ws.name, role="owner")


def _mtime(path):
    return path.stat().st_mtime_ns if path.exists() else None


def test_jira_connection_masks_token_and_reaches_settings(db):
    ws, ctx = _workspace(db)
    with context.use(ctx):
        row = store.save_connection(db, "jira", {
            "base_url": "https://acme.atlassian.net/",
            "email": "pm@acme.com",
            "projects": "AC",
            "api_token": "super-secret-token-12345",
        })
        public = store.public_view(db, row, get_provider("jira"))
    dumped = json.dumps(public)
    assert "super-secret-token-12345" not in dumped
    assert public["secrets"]["api_token"]["set"] is True
    assert public["config"] == {"base_url": "https://acme.atlassian.net", "email": "pm@acme.com", "projects": "AC"}
    assert "super-secret-token-12345" not in row.secrets
    with in_workspace(db, ws.id):
        assert settings.jira_api_token == "super-secret-token-12345"
        assert settings.jira_base_url == "https://acme.atlassian.net"
        assert JiraClient().configured


def test_blank_or_masked_secret_keeps_token_and_clear_removes_it(db):
    ws, ctx = _workspace(db)
    with context.use(ctx):
        store.save_connection(db, "jira", {"api_token": "keep-me-token-9999", "email": "a@b.com", "base_url": "https://x.atlassian.net"})
        for blank in ("", "********", None):
            store.save_connection(db, "jira", {"api_token": blank, "email": "a@b.com"})
            assert store.connection_values(db, store.get_connection(db, "jira"))["api_token"] == "keep-me-token-9999"
        row = store.save_connection(db, "jira", {}, clear=["api_token"])
        assert "api_token" not in store.connection_values(db, row)
        assert row.status == "incomplete"
    with in_workspace(db, ws.id):
        assert settings.jira_api_token == ""
        assert not JiraClient().configured


def test_prototype_route_uses_mapped_provider(db):
    ws, ctx = _workspace(db)
    with context.use(ctx):
        row = store.save_connection(db, "llm", {
            "providers": [
                {"id": "openai", "label": "OpenAI", "protocol": "openai", "base_url": "https://api.openai.com/v1", "api_key": "sk-live-openai"},
                {"id": "studio", "label": "Studio", "protocol": "openai", "base_url": "https://studio.example/v1", "api_key": "sk-proto-key"},
            ],
            "routes": {
                "default": {"provider": "openai", "model": "gpt-4o"},
                "prototype": {"provider": "studio", "model": "gpt-4o-mini"},
                "copilot": {"provider": "openai", "model": "gpt-5.6-luna"},
            },
        })
        public = store.public_view(db, row, get_provider("llm"))
    assert "sk-proto-key" not in json.dumps(public) and "sk-live-openai" not in json.dumps(public)
    assert public["config"]["routes"]["prototype"]["provider"] == "studio"
    with in_workspace(db, ws.id):
        assert model_for("prototype") == "gpt-4o-mini"
        client = LLMClient(surface="prototype")
        assert (client.model, client.api_key, client.base_url) == ("gpt-4o-mini", "sk-proto-key", "https://studio.example/v1")
        assert LLMClient(surface="copilot").api_key == "sk-live-openai"


def test_new_workspace_does_not_inherit_the_env_pm(db, monkeypatch):
    from app.services.profile import load_profile

    monkeypatch.setattr(settings._base, "pm_display_name", "Arsalaan")
    monkeypatch.setattr(settings._base, "pm_cliq_user_id", "10000000001")
    ws, _ = _workspace(db)
    with in_workspace(db, ws.id):
        loaded = load_profile()
    assert loaded["pm_display_name"] == ""
    assert loaded["pm_cliq_user_id"] == ""
    assert "10000000001" not in loaded["pm_cliq_mentions"]


def test_refreshed_cliq_tokens_go_to_the_connection_not_files(db):
    from app.services.workspace import store_cliq_tokens

    env_file = ROOT / ".env"
    token_file = ROOT / "data" / "cliq_token.json"
    before = (_mtime(env_file), _mtime(token_file))
    ws, ctx = _workspace(db)
    with context.use(ctx):
        store.save_connection(db, "cliq", {"client_id": "client-1", "client_secret": "secret-1", "refresh_token": "refresh-1"})
    with in_workspace(db, ws.id):
        store_cliq_tokens("access-2", "refresh-2")
        assert settings.cliq_access_token == "access-2"
    with context.use(ctx):
        values = store.connection_values(db, store.get_connection(db, "cliq"))
    assert (values["access_token"], values["refresh_token"], values["client_secret"]) == ("access-2", "refresh-2", "secret-1")
    with in_workspace(db, ws.id):
        assert settings.cliq_refresh_token == "refresh-2"
    assert (_mtime(env_file), _mtime(token_file)) == before


def test_secrets_are_encrypted_per_workspace(db):
    first, first_ctx = _workspace(db)
    second, second_ctx = _workspace(db)
    with context.use(first_ctx):
        row_a = store.save_connection(db, "smtp", {"host": "smtp.a.test", "password": "smtp-secret-aaaa"})
        cartesia = store.save_connection(db, "cartesia", {"api_key": "cartesia-secret-cccc"})
    with context.use(second_ctx):
        row_b = store.save_connection(db, "smtp", {"host": "smtp.b.test", "password": "smtp-secret-bbbb"})
    for row, plain in ((row_a, "smtp-secret-aaaa"), (row_b, "smtp-secret-bbbb"), (cartesia, "cartesia-secret-cccc")):
        assert row.secrets and plain not in row.secrets
    assert first.data_key != second.data_key
    assert crypto.decrypt_json(first.data_key, row_a.secrets)["password"] == "smtp-secret-aaaa"
    assert crypto.decrypt_json(second.data_key, row_a.secrets) == {}
    with in_workspace(db, first.id):
        assert (settings.smtp_host, settings.smtp_password, settings.cartesia_api_key) == ("smtp.a.test", "smtp-secret-aaaa", "cartesia-secret-cccc")
    with in_workspace(db, second.id):
        assert (settings.smtp_host, settings.smtp_password, settings.cartesia_api_key) == ("smtp.b.test", "smtp-secret-bbbb", "")

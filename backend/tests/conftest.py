import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="productos-tests-"))
os.environ["DATA_DIR"] = str(_TMP / "data")
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP / 'app.db'}"
os.environ["AUTH_MODE"] = "local"
os.environ["ENVIRONMENT"] = "test"
os.environ["RUN_WORKER"] = "off"
os.environ["RUN_SCHEDULER"] = "false"
os.environ["APP_ENCRYPTION_KEY"] = ""
os.environ.setdefault("LOCAL_WORKSPACE_SLUG", "test-workspace")

import pytest  # noqa: E402

from app import context  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def platform_database():
    from app.database import SessionLocal, run_migrations
    from app.workspaces import ensure_local_principal

    run_migrations()
    with context.system():
        db = SessionLocal()
        try:
            ensure_local_principal(db)
        finally:
            db.close()
    yield


@pytest.fixture(autouse=True)
def workspace_context():
    ctx = context.WorkspaceContext(id=1, slug=os.environ["LOCAL_WORKSPACE_SLUG"], name="Test workspace", role="owner")
    with context.use(ctx):
        yield ctx


def _acme_seed():
    import importlib.util

    spec = importlib.util.spec_from_file_location("acme_seed", Path(__file__).resolve().parent / "acme_seed.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def acme_context(base: context.WorkspaceContext) -> context.WorkspaceContext:
    """The context `build_context` produces for the migrated Acme workspace, without touching the database."""
    from app.connections.registry import get_provider
    from app.workspaces import PROFILE_DEFAULTS, PROFILE_SETTINGS

    seed = _acme_seed()
    values: dict = {}
    for provider, extra in seed.CONNECTION_DEFAULTS.items():
        settings_for = {spec.key: spec.setting for spec in get_provider(provider).fields if spec.setting}
        for key, value in extra.items():
            if key in settings_for:
                values[settings_for[key]] = value
    repo = seed.REPOSITORY
    values.update(
        repo_default_branch=repo["default_branch"],
        repo_release_pattern=repo["release_pattern"],
        repo_merge_format=repo["merge_format"],
        repo_path_scopes=",".join(repo["path_scopes"]),
        repo_ui_path=repo["ui_path"],
    )
    profile = {
        **PROFILE_DEFAULTS,
        **seed.PROFILE,
        "pm_display_name": "Arsalaan",
        "pm_cliq_user_id": "10000000001",
        "pm_cliq_mentions": "arsalaan",
    }
    for key in PROFILE_SETTINGS:
        if profile.get(key) not in (None, ""):
            values[key] = profile[key]
    values["timezone"] = "Asia/Kolkata"
    profile["people"] = [
        {
            "short": person.get("short") or person["name"].split()[0],
            "name": person["name"],
            "email": person.get("email", ""),
            "account_id": person.get("jira_account_id", ""),
            "cliq_user_id": person.get("cliq_user_id", ""),
            "cliq_chat_id": person.get("cliq_chat_id", ""),
            "role": person["role"],
            "aliases": list(person.get("aliases") or []),
        }
        for person in seed.PEOPLE
    ]
    return context.WorkspaceContext(
        id=base.id, slug=base.slug, name="Acme", timezone="Asia/Kolkata", values=values, profile=profile, role=base.role
    )


@pytest.fixture
def acme_workspace(workspace_context):
    """Run inside a workspace configured like the migrated Acme workspace (AC/PS, Voice, the Acme roster)."""
    ctx = acme_context(workspace_context)
    with context.use(ctx):
        yield ctx

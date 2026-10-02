"""Process start-up shared by the API, the worker and the CLI.

A laptop install that predates workspaces still has `DATA_DIR/pm_agent.db`. On its first boot in
local mode, while the platform database has no workspaces, the old install is copied into its
workspace with `scripts/migrate_to_workspaces.py`. The legacy database, `.env` and data files are
only read, so the pre-workspace setup keeps working if this code is rolled back.
"""

from __future__ import annotations

import fcntl
import importlib.util
import logging
from pathlib import Path

from app import context
from app.config import ENV_FILE, data_root, settings

log = logging.getLogger(__name__)

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "migrate_to_workspaces.py"


class CutoverFailed(RuntimeError):
    pass


def legacy_database() -> Path | None:
    path = data_root() / "pm_agent.db"
    return path if path.is_file() else None


def _has_workspaces() -> bool:
    from app.database import SessionLocal
    from app.models import Workspace

    with context.system():
        db = SessionLocal()
        try:
            return db.query(Workspace.id).first() is not None
        finally:
            db.close()


def _run_migration_script(legacy: Path) -> int:
    spec = importlib.util.spec_from_file_location("migrate_to_workspaces", SCRIPT)
    if spec is None or spec.loader is None:
        raise CutoverFailed(f"Migration script not found at {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return int(
        module.main(
            [
                "--source", str(legacy),
                "--source-data", str(legacy.parent),
                "--env-file", str(ENV_FILE),
                "--slug", settings.env_value("local_workspace_slug") or "default",
                "--name", settings.env_value("local_workspace_name") or "My workspace",
                "--files", "copy",
            ]
        )
        or 0
    )


def cutover_legacy_install() -> bool:
    """Returns True when this call copied a legacy install into its workspace."""
    from app.auth import auth_mode

    legacy = legacy_database()
    if auth_mode() != "local" or legacy is None or _has_workspaces():
        return False
    lock_path = data_root() / ".cutover.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if _has_workspaces():
            return False
        log.warning("Copying the existing install (%s) into the %s workspace. This runs once.", legacy, settings.env_value("local_workspace_slug"))
        code = _run_migration_script(legacy)
        if code != 0:
            raise CutoverFailed(
                f"Copying the existing install into its workspace failed (exit {code}). Nothing in {legacy.parent} was changed. "
                "Delete DATA_DIR/platform.db and DATA_DIR/workspaces, then start again."
            )
    return True


def bootstrap() -> None:
    from app.auth import auth_mode
    from app.database import SessionLocal, run_migrations

    run_migrations()
    if auth_mode() != "local":
        return
    cutover_legacy_install()
    from app.workspaces import ensure_local_principal

    with context.system():
        db = SessionLocal()
        try:
            ensure_local_principal(db)
        finally:
            db.close()

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

log = logging.getLogger(__name__)
BACKEND_DIR = Path(__file__).resolve().parents[1]


class Base(DeclarativeBase):
    pass


def is_sqlite(url: str | None = None) -> bool:
    return (url or settings.database_url).startswith("sqlite")


def is_postgres(url: str | None = None) -> bool:
    return (url or settings.database_url).startswith("postgresql")


def make_engine(url: str):
    connect_args: dict = {}
    kwargs: dict = {"future": True, "pool_pre_ping": True}
    if is_sqlite(url):
        path = url.replace("sqlite:///", "")
        if path and path != ":memory:" and not url.startswith("sqlite://:"):
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        connect_args = {"check_same_thread": False, "timeout": 30}
    else:
        kwargs.update(pool_size=10, max_overflow=20, pool_recycle=1800)
    engine = create_engine(url, connect_args=connect_args, **kwargs)
    if is_sqlite(url):

        @event.listens_for(engine, "connect")
        def _sqlite_pragma(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=8000")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.execute("PRAGMA cache_size=-20000")
            cursor.execute("PRAGMA mmap_size=268435456")
            cursor.close()

    return engine


engine = make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def alembic_config(url: str | None = None):
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", (url or settings.database_url).replace("%", "%%"))
    return cfg


class LegacyDatabaseError(RuntimeError):
    pass


def is_legacy_database(bind=None) -> bool:
    """The single-tenant SQLite file from before workspaces: domain tables but no `workspaces`."""
    tables = set(inspect(bind or engine).get_table_names())
    return bool(tables) and "workspaces" not in tables and "jira_issues" in tables


def run_migrations(url: str | None = None) -> None:
    from alembic import command

    bind = engine if url is None else make_engine(url)
    if is_legacy_database(bind):
        raise LegacyDatabaseError(
            "This database predates workspaces. Run `python scripts/migrate_to_workspaces.py` "
            "to copy it into a workspace, then point DATABASE_URL at the new database."
        )
    command.upgrade(alembic_config(url), "head")


def migrate_schema() -> None:
    """Kept for callers from before Alembic; schema changes now live in alembic/versions."""
    run_migrations()

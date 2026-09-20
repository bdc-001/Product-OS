from pathlib import Path

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


connect_args = {}
if settings.database_url.startswith("sqlite"):
    Path(settings.database_url.replace("sqlite:///", "")).parent.mkdir(parents=True, exist_ok=True)
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    future=True,
    pool_pre_ping=True,
)

if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _sqlite_pragma(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=8000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _add_column(conn, table: str, name: str, coltype: str, existing: set[str]) -> None:
    if name not in existing:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {coltype}"))


def migrate_schema() -> None:
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        if "marketing_features" in tables:
            cols = {column["name"] for column in inspector.get_columns("marketing_features")}
            _add_column(conn, "marketing_features", "decision", "JSON DEFAULT '{}'", cols)
            for name, coltype in (
                ("module", "VARCHAR(120) DEFAULT ''"),
                ("priority", "VARCHAR(16) DEFAULT ''"),
                ("summary", "VARCHAR(280) DEFAULT ''"),
                ("hook", "TEXT DEFAULT ''"),
                ("start_date", "VARCHAR(32) DEFAULT ''"),
                ("end_date", "VARCHAR(32) DEFAULT ''"),
                ("sheet_status", "VARCHAR(64) DEFAULT 'Not started'"),
                ("script", "TEXT DEFAULT ''"),
                ("video", "TEXT DEFAULT ''"),
                ("tag", "VARCHAR(64) DEFAULT 'New'"),
            ):
                _add_column(conn, "marketing_features", name, coltype, cols)
        if "marketing_campaigns" in tables:
            cols = {column["name"] for column in inspector.get_columns("marketing_campaigns")}
            _add_column(conn, "marketing_campaigns", "run_key", "VARCHAR(200)", cols)
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_marketing_run_key ON marketing_campaigns(run_key)"))
        if "marketing_scans" in tables:
            cols = {column["name"] for column in inspector.get_columns("marketing_scans")}
            _add_column(conn, "marketing_scans", "source_sha", "VARCHAR(64) DEFAULT ''", cols)
        if "standups" in tables:
            cols = {column["name"] for column in inspector.get_columns("standups")}
            for name in ("bugs", "tasks", "wallet_requests", "long_pending", "week_actions", "dev_load", "monday_plan", "this_week", "other_actions", "cliq_briefing"):
                _add_column(conn, "standups", name, "JSON", cols)
        if "jira_issues" in tables:
            cols = {column["name"] for column in inspector.get_columns("jira_issues")}
            _add_column(conn, "jira_issues", "extra_json", "JSON", cols)
            _add_column(conn, "jira_issues", "archived_at", "DATETIME", cols)
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_jira_issues_archived_at ON jira_issues (archived_at)"))
        if "prds" in tables:
            cols = {column["name"] for column in inspector.get_columns("prds")}
            _add_column(conn, "prds", "issue_keys", "JSON", cols)
        if "codebase_snapshots" in tables:
            cols = {column["name"] for column in inspector.get_columns("codebase_snapshots")}
            for name, coltype in (
                ("live_base", "VARCHAR(128) DEFAULT ''"),
                ("live_summary", "TEXT DEFAULT ''"),
                ("live_commits", "JSON"),
                ("live_files", "JSON"),
            ):
                _add_column(conn, "codebase_snapshots", name, coltype, cols)
        if "release_packs" in tables:
            cols = {column["name"] for column in inspector.get_columns("release_packs")}
            _add_column(conn, "release_packs", "kind", "VARCHAR(32) DEFAULT 'pack'", cols)
            _add_column(conn, "release_packs", "artifacts", "JSON", cols)
        if "copilot_plans" in tables:
            cols = {column["name"] for column in inspector.get_columns("copilot_plans")}
            _add_column(conn, "copilot_plans", "parent_plan_id", "INTEGER DEFAULT 0", cols)
            _add_column(conn, "copilot_plans", "context_json", "JSON", cols)
            _add_column(conn, "copilot_plans", "plan_hash", "VARCHAR(64) DEFAULT ''", cols)
            _add_column(conn, "copilot_plans", "fingerprint", "JSON", cols)
        if "daily_notes" in tables:
            cols = {column["name"] for column in inspector.get_columns("daily_notes")}
            _add_column(conn, "daily_notes", "kind", "VARCHAR(32) DEFAULT 'daily'", cols)
            _add_column(conn, "daily_notes", "blocks", "JSON", cols)
        if "pipeline_runs" in tables:
            cols = {column["name"] for column in inspector.get_columns("pipeline_runs")}
            _add_column(conn, "pipeline_runs", "attempt", "INTEGER DEFAULT 1", cols)
            _add_column(conn, "pipeline_runs", "dead_letter", "BOOLEAN DEFAULT 0", cols)
        if "background_jobs" in tables:
            cols = {column["name"] for column in inspector.get_columns("background_jobs")}
            _add_column(conn, "background_jobs", "worker_pid", "INTEGER DEFAULT 0", cols)
        if "release_jobs" in tables:
            index_names = {ix.get("name") for ix in inspector.get_indexes("release_jobs")}
            unique_names = {uc.get("name") for uc in inspector.get_unique_constraints("release_jobs")}
            if "uq_release_branch_sha" not in index_names and "uq_release_branch_sha" not in unique_names:
                conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_release_branch_sha ON release_jobs (branch, sha)"))

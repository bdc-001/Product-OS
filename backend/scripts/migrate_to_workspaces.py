#!/usr/bin/env python
"""Copy the single-tenant install (SQLite `pm_agent.db`, `data/*`, encrypted settings) into a workspace.

The source is never modified: the SQLite file is opened read-only, files are copied (or hard-linked)
into `DATA_DIR/workspaces/<slug>/`, and `.env`, `workspace.json`, `workspace.secrets.json`,
`workspace.key`, `cliq_token.json` and the Google key file are only read.

    # See what would happen
    python scripts/migrate_to_workspaces.py --dry-run

    # Rehearse into a throwaway database and folder
    python scripts/migrate_to_workspaces.py --target sqlite:////tmp/rehearsal/app.db --data-dir /tmp/rehearsal/data --files link

    # Real run into Postgres
    python scripts/migrate_to_workspaces.py --target postgresql://... --data-dir /data
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))

# Files that hold configuration or the source database: read, never copied into the workspace.
LEGACY_FILES = {
    "pm_agent.db",
    "pm_agent.db-wal",
    "pm_agent.db-shm",
    "workspace.json",
    "workspace.secrets.json",
    "workspace.key",
    "workspace.gdrive.json",
    "cliq_token.json",
    "profile.json",
    "people.json",
    "git.lock",
}
SKIP_DIRS = {"workspaces", "__pycache__"}
TABLE_RENAMES = {"background_jobs": "runs"}
CONFIG_TABLES = {"pipeline_configs", "audit_events", "connections", "repositories", "people"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", default=str(ROOT / "data" / "pm_agent.db"), help="Legacy SQLite database (read-only).")
    parser.add_argument("--source-data", default=str(ROOT / "data"), help="Legacy data folder (read-only).")
    parser.add_argument("--env-file", default=str(ROOT / ".env"), help="Legacy .env (read-only).")
    parser.add_argument("--target", default="", help="Target DATABASE_URL. Defaults to $DATABASE_URL or DATA_DIR/platform.db.")
    parser.add_argument("--data-dir", default="", help="Target DATA_DIR. Defaults to $DATA_DIR or ./data.")
    parser.add_argument("--slug", default="default")
    parser.add_argument("--name", default="My workspace")
    parser.add_argument("--owner-email", default="", help="Owner of the workspace. Defaults to the Jira or Cliq email.")
    parser.add_argument("--files", choices=("copy", "link", "move", "skip"), default="copy", help="How to bring data/* across. `move` is the only mode that changes the source.")
    parser.add_argument("--repo-mode", choices=("local", "managed", "none"), default="local")
    parser.add_argument("--seed", default="", help="Workspace seed module (scripts/<name>_seed.py). Defaults to the only one present.")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def _configure_env(args: argparse.Namespace) -> None:
    if args.data_dir:
        os.environ["DATA_DIR"] = str(Path(args.data_dir).expanduser().resolve())
    if args.target:
        os.environ["DATABASE_URL"] = args.target
    os.environ.setdefault("RUN_WORKER", "off")
    os.environ.setdefault("RUN_SCHEDULER", "false")


def file_inventory(source_data: Path) -> list[Path]:
    files: list[Path] = []
    if not source_data.is_dir():
        return files
    for path in sorted(source_data.rglob("*")):
        rel = path.relative_to(source_data)
        if rel.parts and rel.parts[0] in SKIP_DIRS:
            continue
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if len(rel.parts) == 1 and (rel.name in LEGACY_FILES or rel.name.startswith("platform.db")):
            continue
        if path.is_file() and not path.is_symlink():
            files.append(rel)
    return files


def source_tables(source_url: str) -> dict[str, int]:
    from sqlalchemy import create_engine, inspect, text

    engine = create_engine(source_url)
    with engine.connect() as conn:
        names = inspect(conn).get_table_names()
        return {name: conn.execute(text(f'SELECT COUNT(*) FROM "{name}"')).scalar_one() for name in names}


def table_plan(counts: dict[str, int]):
    from app.database import Base
    from app.tenancy import is_scoped

    scoped = {mapper.local_table.name: mapper.class_ for mapper in Base.registry.mappers if is_scoped(mapper.class_)}
    plan = []
    for source_name, rows in counts.items():
        target_name = TABLE_RENAMES.get(source_name, source_name)
        if target_name in scoped and target_name not in CONFIG_TABLES:
            plan.append((source_name, Base.metadata.tables[target_name], rows))
    unknown = sorted(name for name in counts if TABLE_RENAMES.get(name, name) not in scoped and name != "alembic_version")
    order = {table.name: i for i, table in enumerate(Base.metadata.sorted_tables)}
    plan.sort(key=lambda item: order.get(item[1].name, 0))
    return plan, unknown


def _empty_for(column):
    from sqlalchemy import JSON, Boolean, DateTime, Float, Integer

    if column.default is not None:
        arg = column.default.arg
        return arg(None) if callable(arg) else arg
    kind = column.type
    if isinstance(kind, JSON):
        return {}
    if isinstance(kind, Boolean):
        return False
    if isinstance(kind, (Integer, Float)):
        return 0
    if isinstance(kind, DateTime):
        return datetime.utcnow()
    return ""


class PathRewriter:
    """Absolute paths into the legacy data folder become workspace-relative."""

    def __init__(self, source_data: Path) -> None:
        roots = {str(source_data), str(source_data.resolve())}
        self.prefixes = sorted({root.rstrip("/") + "/" for root in roots}, key=len, reverse=True)
        self.rewritten = 0

    def __call__(self, value):
        if isinstance(value, str):
            for prefix in self.prefixes:
                if value.startswith(prefix):
                    self.rewritten += 1
                    return value[len(prefix):]
            return value
        if isinstance(value, list):
            return [self(item) for item in value]
        if isinstance(value, dict):
            return {key: self(item) for key, item in value.items()}
        return value


def copy_table(source_engine, target_conn, source_name: str, target_table, workspace_id: int, rewrite: PathRewriter) -> int:
    from sqlalchemy import Column, MetaData, Table, inspect, select

    with source_engine.connect() as src:
        present = {col["name"] for col in inspect(src).get_columns(source_name)}
        common = [col for col in target_table.columns if col.name in present and col.name != "workspace_id"]
        mirror = Table(source_name, MetaData(), *[Column(col.name, col.type) for col in common])
        result = src.execute(select(mirror))
        copied = 0
        batch: list[dict] = []
        for row in result.mappings():
            record = {}
            for col in target_table.columns:
                if col.name == "workspace_id":
                    record[col.name] = workspace_id
                    continue
                value = row.get(col.name) if col.name in present else None
                if value is None and not col.nullable:
                    value = _empty_for(col)
                record[col.name] = rewrite(value)
            if target_table.name == "runs":
                record = _run_from_job(record)
            batch.append(record)
            if len(batch) >= 500:
                target_conn.execute(target_table.insert(), batch)
                copied += len(batch)
                batch = []
        if batch:
            target_conn.execute(target_table.insert(), batch)
            copied += len(batch)
    return copied


def _run_from_job(record: dict) -> dict:
    from app.pipelines.registry import TASK_PIPELINE

    kind = record.get("kind") or ""
    record["task"] = record.get("task") or kind
    record["pipeline_id"] = record.get("pipeline_id") or TASK_PIPELINE.get(kind, "")
    record["trigger"] = record.get("trigger") or "manual"
    if record.get("status") in {"queued", "running"}:
        record["status"] = "failed"
        record["error"] = record.get("error") or "Interrupted before the move to workspaces."
        record["finished_at"] = record.get("finished_at") or datetime.utcnow()
    record["started_at"] = record.get("started_at") or record.get("created_at")
    return record


def reset_sequences(conn, tables) -> None:
    from sqlalchemy import text

    if conn.dialect.name != "postgresql":
        return
    for table in tables:
        if "id" not in table.columns:
            continue
        conn.execute(
            text(
                f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), "
                f"COALESCE((SELECT MAX(id) FROM \"{table.name}\"), 1), "
                f"(SELECT MAX(id) FROM \"{table.name}\") IS NOT NULL)"
            )
        )


def bring_files(source_data: Path, target_root: Path, files: list[Path], mode: str) -> int:
    done = 0
    for rel in files:
        src = source_data / rel
        dst = target_root / rel
        if dst.exists():
            done += 1
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        if mode == "move":
            shutil.move(str(src), str(dst))
        elif mode == "link":
            try:
                os.link(src, dst)
            except OSError:
                shutil.copy2(src, dst)
        else:
            _copy(src, dst)
        done += 1
    return done


def _copy(src: Path, dst: Path) -> None:
    # APFS clones are independent copies that share blocks until either side changes.
    if sys.platform == "darwin":
        proc = subprocess.run(["cp", "-c", "-p", str(src), str(dst)], capture_output=True)
        if proc.returncode == 0:
            return
    shutil.copy2(src, dst)


def git_remote(path: str) -> str:
    if not path or not Path(path).expanduser().is_dir():
        return ""
    proc = subprocess.run(["git", "-C", str(Path(path).expanduser()), "remote", "get-url", "origin"], capture_output=True, text=True)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def load_seed(path: str):
    """The operator's git-ignored seed: PROFILE, CONNECTION_DEFAULTS, REPOSITORY, PEOPLE and pipeline defaults."""
    import importlib.util

    if path:
        seed_path = Path(path).expanduser().resolve()
    else:
        found = sorted(Path(__file__).resolve().parent.glob("*_seed.py"))
        if len(found) != 1:
            raise SystemExit("Pass --seed scripts/<name>_seed.py (found %d seed files)." % len(found))
        seed_path = found[0]
    spec = importlib.util.spec_from_file_location(seed_path.stem, seed_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _configure_env(args)

    from sqlalchemy import func, select

    from app import context
    from app.config import settings
    from app.connections.legacy import has_values, import_connections, read_legacy
    from app.database import SessionLocal, engine, is_legacy_database, run_migrations
    from app.models import Person, Repository, Workspace
    from app.storage import workspace_root

    seed = load_seed(args.seed)

    source = Path(args.source).expanduser().resolve()
    source_data = Path(args.source_data).expanduser().resolve()
    env_file = Path(args.env_file).expanduser()
    if not source.is_file():
        print(f"Source database not found: {source}")
        return 2
    source_url = f"sqlite:///file:{source}?mode=ro&uri=true"
    target_url = settings.database_url
    if Path(target_url.replace("sqlite:///", "")).resolve() == source:
        print("The target database is the legacy file. Point --target or DATABASE_URL at a new database.")
        return 2

    from sqlalchemy import create_engine

    source_engine = create_engine(source_url)
    counts = source_tables(source_url)
    plan, unknown = table_plan(counts)
    files = file_inventory(source_data)
    legacy = read_legacy(source_data, env_file)

    print(f"Source database : {source}")
    print(f"Target database : {target_url.split('@')[-1]}")
    print(f"Target data dir : {settings.env_value('data_dir')}")
    print(f"Workspace       : {args.name} ({args.slug})")
    print(f"Tables to copy  : {len(plan)} ({sum(rows for _, _, rows in plan)} rows)")
    for source_name, table, rows in plan:
        label = source_name if source_name == table.name else f"{source_name} -> {table.name}"
        print(f"  {label:<34} {rows:>7}")
    if unknown:
        print("Tables without a model (not copied): " + ", ".join(unknown))
    print(f"Files ({args.files}) : {len(files)}")
    print("Connections     : " + ", ".join(f"{p}={'yes' if has_values(p, v) else 'no'}" for p, v in legacy.connections.items()))
    for warning in legacy.warnings:
        print("Warning: " + warning)
    if args.dry_run:
        print("Dry run: nothing written.")
        return 0

    with context.system():
        if is_legacy_database():
            print("The target database is a legacy single-tenant file. Use a new database.")
            return 2
        run_migrations()
        db = SessionLocal()
        try:
            existing = db.query(Workspace).filter(Workspace.slug == args.slug).one_or_none()
            for _, table, _ in plan:
                taken = db.execute(select(func.count()).select_from(table)).scalar_one()
                if taken:
                    print(f"Target table {table.name} already has rows. Migrate into a fresh database.")
                    return 3
            from app.workspaces import create_workspace, ensure_user

            owner_email = args.owner_email or legacy.connections["jira"].get("email") or legacy.connections["cliq"].get("pm_email") or "owner@localhost"
            owner = ensure_user(db, clerk_user_id=None, email=owner_email, name=legacy.profile.get("pm_display_name") or "")
            profile = {**seed.PROFILE, **{k: v for k, v in legacy.profile.items() if v and k != "timezone"}}
            for key in ("standup_hour", "release_notes_hour"):
                try:
                    profile[key] = int(profile.get(key) or 0) or None
                except (TypeError, ValueError):
                    profile.pop(key, None)
            profile = {k: v for k, v in profile.items() if v is not None}
            ws = existing or create_workspace(db, args.name, slug=args.slug, owner=owner, timezone=legacy.profile.get("timezone") or "Asia/Kolkata", profile=profile)
            workspace_id = ws.id
        finally:
            db.close()

        rewrite = PathRewriter(source_data)
        copied: dict[str, int] = {}
        with engine.begin() as conn:
            for source_name, table, rows in plan:
                copied[table.name] = copy_table(source_engine, conn, source_name, table, workspace_id, rewrite)
                print(f"  copied {table.name:<28} {copied[table.name]:>7}")
            reset_sequences(conn, [table for _, table, _ in plan])

    ctx = context.WorkspaceContext(id=workspace_id, slug=args.slug, name=args.name)
    with context.use(ctx):
        target_root = workspace_root()
        target_root.mkdir(parents=True, exist_ok=True)
        moved = bring_files(source_data, target_root, files, args.files) if args.files != "skip" else 0

        db = SessionLocal()
        try:
            for provider, extra in seed.CONNECTION_DEFAULTS.items():
                values = legacy.connections.setdefault(provider, {})
                for key, value in extra.items():
                    if not str(values.get(key) or "").strip():
                        values[key] = value
            outcome = import_connections(db, legacy)
            for person in seed.PEOPLE:
                if not db.query(Person.id).filter(Person.name == person["name"]).first():
                    db.add(Person(**{k: v for k, v in person.items()}))
            db.commit()

            repo_row = None
            if args.repo_mode != "none" and not db.query(Repository.id).first():
                remote = git_remote(legacy.codebase_path)
                data = {**seed.REPOSITORY, "remote_url": remote, "is_primary": True}
                if args.repo_mode == "local" and legacy.codebase_path:
                    data.update(mode="local", local_path=legacy.codebase_path)
                    repo_row = _save_repo(db, data)
                elif remote:
                    data.update(mode="managed")
                    repo_row = _save_repo(db, data)
            if repo_row is not None:
                old_index = target_root / "codebase" / "source.sqlite3"
                new_index = target_root / "repos" / str(repo_row.id) / "source.sqlite3"
                if old_index.is_file() and not new_index.exists():
                    new_index.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(old_index, new_index)

            from app.models import PipelineConfig

            for row in db.query(PipelineConfig).filter(PipelineConfig.pipeline_id.in_(seed.SCHEDULED_PIPELINES)).all():
                row.schedule_enabled = True
            for row in db.query(PipelineConfig).filter(PipelineConfig.pipeline_id.in_(tuple(seed.PIPELINE_SETTINGS))).all():
                row.settings = {**(row.settings or {}), **seed.PIPELINE_SETTINGS[row.pipeline_id]}
            from app.connections.store import audit

            audit(db, "workspace.migrated", args.slug, {"tables": copied, "files": moved, "connections": outcome}, "migration")
            db.commit()
        finally:
            db.close()

        problems = verify(plan, copied, files, target_root, args.files)
        report = {
            "finished_at": datetime.utcnow().isoformat(),
            "workspace": {"id": workspace_id, "slug": args.slug},
            "tables": {table.name: {"source": rows, "target": copied.get(table.name, 0)} for _, table, rows in plan},
            "files": {"source": len(files), "target": moved, "mode": args.files},
            "paths_rewritten": rewrite.rewritten,
            "connections": outcome,
            "problems": problems,
        }
        (target_root / "migration-report.json").write_text(json.dumps(report, indent=2, default=str))

    print("Connections: " + ", ".join(f"{k}={v}" for k, v in outcome.items()))
    print(f"Files: {moved}/{len(files)} ({args.files}); paths rewritten: {rewrite.rewritten}")
    if problems:
        print("Verification FAILED:")
        for problem in problems:
            print("  " + problem)
        return 1
    print("Verification passed: row and file counts match.")
    return 0


def _save_repo(db, data: dict):
    from app.services.repos import save_repository

    try:
        return save_repository(db, data)
    except ValueError as exc:
        print(f"Repository not created: {exc}")
        return None


def verify(plan, copied: dict[str, int], files: list[Path], target_root: Path, mode: str) -> list[str]:
    from sqlalchemy import func, select

    from app import context
    from app.database import engine

    problems = []
    workspace_id = context.require().id
    with engine.connect() as conn:
        for _, table, rows in plan:
            found = conn.execute(select(func.count()).select_from(table).where(table.c.workspace_id == workspace_id)).scalar_one()
            if found != rows:
                problems.append(f"{table.name}: source {rows}, target {found}")
    if mode != "skip":
        missing = [str(rel) for rel in files if not (target_root / rel).is_file()]
        if missing:
            problems.append(f"{len(missing)} files missing in the workspace folder, e.g. {missing[0]}")
    return problems


if __name__ == "__main__":
    raise SystemExit(main())

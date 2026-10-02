"""Command line for local installs, the laptop daily sync and the worker container.

    python -m app migrate
    python -m app pipelines [--workspace <slug>]
    python -m app run daily-sync [--workspace <slug>] [--params '{"key": "value"}'] [--trigger schedule]
    python -m app worker
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from app import models as _models  # noqa: F401

TERMINAL = {"completed", "failed", "cancelled"}


def _workspace_id(slug: str) -> int:
    from app import context
    from app.database import SessionLocal
    from app.workspaces import local_workspace

    with context.system():
        db = SessionLocal()
        try:
            row = local_workspace(db, slug)
            if row is None:
                raise SystemExit(f"No workspace with slug {slug!r}." if slug else "No workspace yet. Start the API once to create one.")
            return row.id
        finally:
            db.close()


def _summary(run) -> dict:
    steps = {}
    for name, step in (run.steps or {}).items():
        step = step if isinstance(step, dict) else {}
        steps[name] = {k: (v[:300] if isinstance(v, str) else v) for k, v in step.items() if isinstance(v, (str, int, float, bool)) or v is None}
    return {
        "run_id": run.id,
        "pipeline": run.pipeline_id,
        "status": run.status,
        "error": run.error or "",
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "steps": steps,
    }


def cmd_migrate(_args) -> int:
    from app.bootstrap import bootstrap

    bootstrap()
    print("Database is at the latest revision.")
    return 0


def cmd_pipelines(args) -> int:
    from app.bootstrap import bootstrap
    from app.database import SessionLocal
    from app.pipelines.registry import catalog
    from app.workspaces import in_workspace

    bootstrap()
    db = SessionLocal()
    try:
        with in_workspace(db, _workspace_id(args.workspace)):
            for item in catalog(db):
                missing = ", ".join(item["readiness"]["missing"])
                print(f"{item['id']:<20} {item['status']:<18} {missing}")
    finally:
        db.close()
    return 0


def cmd_run(args) -> int:
    from app.bootstrap import bootstrap
    from app.database import SessionLocal
    from app.pipelines.registry import PipelineNotReady, start_pipeline
    from app.services.jobs import get_job
    from app.workspaces import in_workspace

    bootstrap()
    params = json.loads(args.params) if args.params else {}
    deadline = time.monotonic() + args.timeout * 60
    db = SessionLocal()
    try:
        with in_workspace(db, _workspace_id(args.workspace)):
            try:
                run = start_pipeline(db, args.pipeline, trigger=args.trigger, params=params, started_by="cli", inline=True)
            except (KeyError, PipelineNotReady) as exc:
                print(json.dumps({"status": "not_started", "error": str(exc)}, indent=2))
                return 2
            run_id = run.id
            while True:
                db.expire_all()
                row = get_job(db, run_id)
                if row is None or row.status in TERMINAL:
                    break
                if time.monotonic() > deadline:
                    summary = {**_summary(row), "status": "timeout", "error": f"Still {row.status} after {args.timeout} minutes."}
                    print(json.dumps(summary, indent=2, default=str))
                    if args.summary_file:
                        Path(args.summary_file).write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
                    return 1
                time.sleep(2)
            summary = _summary(row)
            print(json.dumps(summary, indent=2, default=str))
            if args.summary_file:
                Path(args.summary_file).write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
            return 0 if row is not None and row.status == "completed" else 1
    finally:
        db.close()


def cmd_worker(_args) -> int:
    from app.pipelines.worker import main as worker_main

    worker_main()
    return 0


def cmd_daily_release_notes(args) -> int:
    args.pipeline, args.trigger, args.params = "release-notes", "manual", json.dumps({"force": bool(args.force)})
    return cmd_run(args)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("migrate", help="Apply database migrations.").set_defaults(fn=cmd_migrate)

    listing = sub.add_parser("pipelines", help="List pipelines and their readiness.")
    listing.add_argument("--workspace", default="")
    listing.set_defaults(fn=cmd_pipelines)

    run = sub.add_parser("run", help="Run one pipeline now in this process and wait for it.")
    run.add_argument("pipeline")
    run.add_argument("--workspace", default="")
    run.add_argument("--params", default="")
    run.add_argument("--trigger", default="manual", choices=("manual", "schedule"))
    run.add_argument("--timeout", type=int, default=180, help="Minutes to wait before giving up.")
    run.add_argument("--summary-file", default="", help="Also write the JSON summary here.")
    run.set_defaults(fn=cmd_run)

    sub.add_parser("worker", help="Run the queue worker (and the scheduler when RUN_SCHEDULER is on).").set_defaults(fn=cmd_worker)

    notes = sub.add_parser("daily-release-notes", help="Same as `run release-notes`.")
    notes.add_argument("--workspace", default="")
    notes.add_argument("--force", action="store_true")
    notes.add_argument("--timeout", type=int, default=180)
    notes.add_argument("--summary-file", default="")
    notes.set_defaults(fn=cmd_daily_release_notes)

    args = parser.parse_args(argv)
    sys.exit(args.fn(args))

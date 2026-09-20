import argparse
import json

from app import models as _models  # noqa: F401
from app.database import Base, SessionLocal, engine, migrate_schema
from app.services.release_notes_job import run_daily_release_notes


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app")
    parser.add_argument("command", choices=["daily-release-notes"])
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    Base.metadata.create_all(bind=engine)
    migrate_schema()
    db = SessionLocal()
    try:
        result = run_daily_release_notes(db, force=args.force)
        job = result.get("job") or {}
        print(json.dumps({"status": job.get("status"), "branch": job.get("branch"), "error": job.get("error") or ""}, indent=2))
        if job.get("status") == "error":
            raise SystemExit(1)
    finally:
        db.close()

from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import BackgroundJob, JiraIssue, Standup
from app.services.codebase import clear_stale_git_locks
from app.services.evaluate import evaluate_standup
from app.services.ingest import ingest_jira
from app.services.jobs import ORPHAN_ERROR, enqueue, get_job, reap_orphaned_jobs, worker_pid


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def test_jira_section_refresh_does_not_ingest_other_sources(monkeypatch):
    from app.api.routers import platform
    from app.services import ingest

    db = _db()
    calls = []
    monkeypatch.setattr(ingest, "ingest_jira", lambda session, start: calls.append("jira") or 7)
    def unexpected(*args, **kwargs):
        pytest.fail("A section refresh must not run unrelated integrations")
    monkeypatch.setattr(ingest, "ingest_cliq", unexpected)
    monkeypatch.setattr(platform, "refresh_platform", unexpected)
    monkeypatch.setattr(platform, "run_pipeline", unexpected)
    def enqueue_now(session, kind, work):
        assert kind == "refresh-jira"
        return work(session, lambda *args: None)
    monkeypatch.setattr(platform, "enqueue", enqueue_now)
    monkeypatch.setattr(platform, "job_out", lambda result: result)
    response = platform.refresh_section("jira", db)
    import json
    payload = json.loads(response.body)
    assert payload["steps"]["jira"]["jira_count"] == 7
    assert calls == ["jira"]
    db.close()


def _issue(db, key="AC-1", archived=None):
    row = JiraIssue(
        issue_key=key,
        summary="keep me",
        status="In Progress",
        issue_type="Task",
        comments_json=[],
        changelog_json=[],
        extra_json={},
        archived_at=archived,
    )
    db.add(row)
    db.commit()
    return row


def test_reap_orphaned_jobs_fails_other_pid():
    db = _db()
    row = BackgroundJob(kind="refresh", status="running", worker_pid=1, steps={"jira": {"ok": True, "status": "running"}}, result={})
    db.add(row)
    db.commit()
    assert reap_orphaned_jobs(db) == 1
    db.refresh(row)
    assert row.status == "failed"
    assert "interrupted" in row.error.lower()


def test_reap_keeps_live_worker_job():
    db = _db()
    row = BackgroundJob(kind="refresh", status="running", worker_pid=worker_pid(), steps={}, result={})
    db.add(row)
    db.commit()
    assert reap_orphaned_jobs(db) == 0
    db.refresh(row)
    assert row.status == "running"


def test_enqueue_starts_new_job_after_orphan(monkeypatch):
    db = _db()
    zombie = BackgroundJob(kind="refresh", status="running", worker_pid=1, steps={}, result={})
    db.add(zombie)
    db.commit()
    started = []

    class FakeThread:
        def __init__(self, target=None, daemon=None, name=None):
            self.target = target

        def start(self):
            started.append("thread")

    monkeypatch.setattr("app.services.jobs.threading.Thread", FakeThread)
    job = enqueue(db, "refresh", lambda session, set_step: {"ok": True})
    db.refresh(zombie)
    assert zombie.status == "failed"
    assert job.id != zombie.id
    assert job.worker_pid == worker_pid()
    assert started == ["thread"]


def test_get_job_reaps_orphan():
    db = _db()
    row = BackgroundJob(kind="refresh", status="queued", worker_pid=999999, steps={}, result={})
    db.add(row)
    db.commit()
    found = get_job(db, row.id)
    assert found.status == "failed"
    assert found.error == ORPHAN_ERROR


def test_empty_jira_fetch_does_not_archive_board(monkeypatch):
    db = _db()
    _issue(db, "AC-9")

    class FakeJira:
        configured = True

        def fetch_open_board_issues(self):
            raise RuntimeError("Jira HTTP 500")

        def fetch_pm_issues(self, updated_since=None):
            return []

        def fetch_pm_workflow_issues(self):
            return []

        def fetch_by_keys(self, keys, scoped=False):
            return []

        def fetch_summary_matches(self, phrase):
            return []

        def normalize(self, raw):
            return raw

    monkeypatch.setattr("app.services.ingest.JiraClient", lambda: FakeJira())
    monkeypatch.setattr("app.services.ingest.planned_tasks_from_db", lambda db, start: {"tasks": []})
    monkeypatch.setattr("app.services.ingest.unmatched_search_phrases", lambda plan: [])
    with pytest.raises(RuntimeError, match="Jira pulled nothing"):
        ingest_jira(db, datetime(2026, 9, 3, 9, 0))
    kept = db.query(JiraIssue).filter(JiraIssue.issue_key == "AC-9").one()
    assert kept.archived_at is None


def test_zero_issues_without_error_leaves_board(monkeypatch):
    db = _db()
    _issue(db, "AC-9")

    class FakeJira:
        configured = True

        def fetch_open_board_issues(self):
            return []

        def fetch_pm_issues(self, updated_since=None):
            return []

        def fetch_pm_workflow_issues(self):
            return []

        def fetch_by_keys(self, keys, scoped=False):
            return []

        def fetch_summary_matches(self, phrase):
            return []

        def normalize(self, raw):
            return raw

    monkeypatch.setattr("app.services.ingest.JiraClient", lambda: FakeJira())
    monkeypatch.setattr("app.services.ingest.planned_tasks_from_db", lambda db, start: {"tasks": []})
    monkeypatch.setattr("app.services.ingest.unmatched_search_phrases", lambda plan: [])
    count = ingest_jira(db, datetime(2026, 9, 3, 9, 0))
    assert count == 1
    kept = db.query(JiraIssue).filter(JiraIssue.issue_key == "AC-9").one()
    assert kept.archived_at is None


def test_evaluate_standup_persists():
    db = _db()
    standup = Standup(run_id=1, needs_attention=[], todays_actions=[], week_actions=[])
    db.add(standup)
    db.commit()
    row = evaluate_standup(db, standup, [])
    assert row.standup_id == standup.id
    assert row.overall >= 0


def test_clear_stale_git_locks(tmp_path: Path):
    git = tmp_path / ".git"
    git.mkdir()
    lock = git / "index.lock"
    lock.write_text("stale")
    leftover = git / "HEAD.lock"
    leftover.write_text("stale")
    fresh = git / "config.lock"
    fresh.write_text("fresh")
    import os
    import time

    old = time.time() - 120
    os.utime(lock, (old, old))
    os.utime(leftover, (old, old))
    removed = clear_stale_git_locks(tmp_path, max_age_s=20)
    assert "index.lock" in removed
    assert "HEAD.lock" in removed
    assert not lock.exists()
    assert fresh.exists()

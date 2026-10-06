import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import JiraIssue, Run, Standup
from app.services.codebase import clear_stale_git_locks
from app.services.evaluate import evaluate_standup
from app.services.ingest import ingest_jira
from app.services.jobs import ORPHAN_ERROR, enqueue, get_job, reap_orphaned_jobs, worker_pid


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def _now():
    return datetime.utcnow()


def test_section_refresh_endpoint_queues_only_that_section(monkeypatch):
    from app.api.routers import platform

    queued = []
    monkeypatch.setattr(platform, "enqueue", lambda session, kind: queued.append(kind) or kind)
    monkeypatch.setattr(platform, "job_out", lambda kind: {"kind": kind})
    response = platform.refresh_section("jira", None)
    assert response.status_code == 202 and json.loads(response.body) == {"kind": "refresh-jira"}
    assert queued == ["refresh-jira"]
    with pytest.raises(Exception, match="Unknown refresh section"):
        platform.refresh_section("everything", None)


def test_jira_section_task_does_not_ingest_other_sources(monkeypatch):
    from app.pipelines.tasks import TASKS
    from app.services import ingest

    db = _db()
    calls = []
    monkeypatch.setattr(ingest, "ingest_jira", lambda session, start: calls.append("jira") or 7)

    def unexpected(*args, **kwargs):
        pytest.fail("A section refresh must not run unrelated integrations")

    monkeypatch.setattr(ingest, "ingest_cliq", unexpected)
    monkeypatch.setattr("app.services.refresh.refresh_platform", unexpected)
    monkeypatch.setattr("app.services.pipeline.run_pipeline", unexpected)
    payload = TASKS["refresh-jira"](db, lambda *args: None, {})
    assert payload["steps"]["jira"]["jira_count"] == 7
    assert calls == ["jira"]
    db.close()


def test_competitors_section_task_does_not_ingest_other_sources(monkeypatch):
    from app.pipelines.tasks import TASKS
    from app.services import ingest

    db = _db()
    news = []

    def unexpected(*args, **kwargs):
        pytest.fail("A section refresh must not run unrelated integrations")

    monkeypatch.setattr(ingest, "ingest_jira", unexpected)
    monkeypatch.setattr(ingest, "ingest_cliq", unexpected)
    monkeypatch.setattr("app.services.refresh.refresh_platform", unexpected)
    monkeypatch.setattr("app.services.competitive.refresh_all", lambda session, include_ai=True: news.append(include_ai) or {"ok": True, "created": 3})
    payload = TASKS["refresh-competitors"](db, lambda *args: None, {})
    assert payload["steps"]["competitors"]["count"] == 3
    assert news == [False]
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


def test_reap_fails_pre_lease_run_from_another_process():
    db = _db()
    row = Run(kind="refresh", status="running", worker_pid=1, steps={"jira": {"ok": True, "status": "running"}}, result={})
    db.add(row)
    db.commit()
    assert reap_orphaned_jobs(db) == 1
    db.refresh(row)
    assert row.status == "failed"
    assert row.error == ORPHAN_ERROR


def test_reap_keeps_run_with_live_lease():
    db = _db()
    row = Run(kind="refresh", task="refresh", status="running", worker_pid=1, lease_owner="other-host",
              lease_expires_at=_now() + timedelta(minutes=2), steps={}, result={})
    db.add(row)
    db.commit()
    assert reap_orphaned_jobs(db) == 0
    db.refresh(row)
    assert row.status == "running"


def test_expired_lease_requeues_a_named_task_with_attempts_left():
    db = _db()
    row = Run(kind="refresh", task="refresh", status="running", attempts=1, max_attempts=3, lease_owner="dead-host",
              lease_expires_at=_now() - timedelta(seconds=5), steps={}, result={})
    db.add(row)
    db.commit()
    assert reap_orphaned_jobs(db) == 1
    db.refresh(row)
    assert (row.status, row.lease_owner) == ("queued", "")
    assert row.lease_expires_at > _now()


def test_expired_lease_fails_once_attempts_are_used():
    db = _db()
    row = Run(kind="refresh", task="refresh", status="running", attempts=1, max_attempts=1, lease_owner="dead-host",
              lease_expires_at=_now() - timedelta(seconds=5), steps={}, result={})
    db.add(row)
    db.commit()
    assert reap_orphaned_jobs(db) == 1
    db.refresh(row)
    assert (row.status, row.error) == ("failed", ORPHAN_ERROR)


def test_enqueue_closure_starts_new_run_after_orphan(monkeypatch):
    db = _db()
    zombie = Run(kind="refresh", status="running", worker_pid=1, steps={}, result={})
    db.add(zombie)
    db.commit()
    started = []
    monkeypatch.setattr("app.services.jobs.context.spawn", lambda target, *args, **kwargs: started.append(kwargs.get("name")))
    job = enqueue(db, "refresh", lambda session, set_step: {"ok": True})
    db.refresh(zombie)
    assert zombie.status == "failed"
    assert job.id != zombie.id
    assert (job.status, job.worker_pid, job.attempts) == ("running", worker_pid(), 1)
    assert job.lease_expires_at > _now()
    assert started == [f"run-refresh-{job.id}"]


def test_enqueue_named_task_queues_for_the_worker(monkeypatch):
    db = _db()
    woke = []
    monkeypatch.setattr("app.pipelines.worker.notify", lambda: woke.append(True))
    job = enqueue(db, "refresh-jira", params={"source": "test"}, trigger="schedule")
    assert (job.status, job.task, job.trigger, job.params) == ("queued", "refresh-jira", "schedule", {"source": "test"})
    assert woke == [True]
    assert enqueue(db, "refresh-jira").id == job.id
    with pytest.raises(KeyError, match="Unknown task"):
        enqueue(db, "not-a-task")


def test_get_job_reaps_stale_queued_run():
    db = _db()
    row = Run(kind="refresh", status="queued", worker_pid=999999, created_at=_now() - timedelta(hours=7), steps={}, result={})
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

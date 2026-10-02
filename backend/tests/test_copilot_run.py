from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import CopilotAudit, CopilotPlan, JiraIssue
from app.services.copilot import run_copilot
from app.services.copilot_schema import fingerprint_from_issues, plan_hash


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def _plan(db, **kwargs):
    actions = kwargs.pop(
        "actions",
        [{"id": "a1", "kind": "comment", "issue_key": "AC-1", "body": "hi", "ready": True}],
    )
    issue = JiraIssue(
        issue_key="AC-1",
        summary="Ticket",
        status="To Do",
        updated_at=datetime(2026, 1, 1),
    )
    db.add(issue)
    db.flush()
    row = CopilotPlan(
        status="preview",
        actions=actions,
        plan_hash=plan_hash(actions),
        fingerprint=kwargs.pop("fingerprint", fingerprint_from_issues([issue])),
        prompt="comment",
        notes="",
        **kwargs,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_unapproved_raises():
    db = _db()
    row = _plan(db)
    with pytest.raises(RuntimeError, match="Approve"):
        run_copilot(db, plan_id=row.id, approved=False, action_ids=["a1"])


def test_second_run_blocked():
    db = _db()
    row = _plan(db)
    row.status = "ran"
    db.commit()
    with pytest.raises(RuntimeError, match="already ran"):
        run_copilot(db, plan_id=row.id, approved=True, action_ids=["a1"])


def test_fingerprint_change_invalidates_approval():
    db = _db()
    row = _plan(db)
    issue = db.query(JiraIssue).filter(JiraIssue.issue_key == "AC-1").one()
    issue.status = "Staging"
    db.commit()
    with pytest.raises(RuntimeError, match="Jira changed"):
        run_copilot(db, plan_id=row.id, approved=True, action_ids=["a1"])
    db.refresh(row)
    assert row.status == "stale"
    assert db.query(CopilotAudit).filter(CopilotAudit.status == "stale").count() == 1


def test_hash_mismatch_invalidates_approval():
    db = _db()
    row = _plan(db)
    row.actions = [{**row.actions[0], "body": "tampered"}]
    db.commit()
    with pytest.raises(RuntimeError, match="altered"):
        run_copilot(db, plan_id=row.id, approved=True, action_ids=["a1"])
    db.refresh(row)
    assert row.status == "stale"

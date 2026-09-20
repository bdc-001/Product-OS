from datetime import datetime

import pytest

from app.database import Base
from app.models import JiraIssue
from app.services.week_actions import build_week_actions, empty_dev_load, is_staging_status


@pytest.fixture
def db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, future=True)()
    yield session
    session.close()


def _issue(**kwargs):
    payload = {
        "issue_key": "AC-10",
        "summary": "UAT the checkout banner",
        "status": "Staging",
        "status_category": "indeterminate",
        "priority": "High",
        "issue_type": "Task",
        "assignee": "Lovelesh Kumar",
        "assignee_id": "60f55c8a52162b0068d0a655",
        "extra_json": {"product_manager": "Arsalaan"},
        "comments_json": [],
        "changelog_json": [],
        "url": "https://convin.atlassian.net/browse/AC-10",
    }
    payload.update(kwargs)
    return JiraIssue(**payload)


def test_staging_is_uat(db, monkeypatch):
    monkeypatch.setattr("app.services.week_actions.current_dev_load", empty_dev_load)
    monkeypatch.setattr("app.services.week_actions.llm_prioritize_actions", lambda this_week, other: (this_week, other))
    monkeypatch.setattr(
        "app.services.week_actions.planned_tasks_from_db",
        lambda _db, _now: {"found": False, "tasks": [], "chat": "#product-internal"},
    )
    db.add(_issue())
    db.commit()
    result = build_week_actions(db, datetime(2026, 9, 1, 9, 0, 0))
    kinds = {item.get("kind") for item in result["other_actions"]}
    assert "uat" in kinds
    assert any(item.get("issue_key") == "AC-10" for item in result["other_actions"])


def test_done_on_arsalaan_assigns_developer(db, monkeypatch):
    monkeypatch.setattr("app.services.week_actions.current_dev_load", empty_dev_load)
    monkeypatch.setattr("app.services.week_actions.llm_prioritize_actions", lambda this_week, other: (this_week, other))
    monkeypatch.setattr(
        "app.services.week_actions.planned_tasks_from_db",
        lambda _db, _now: {"found": False, "tasks": [], "chat": "#product-internal"},
    )
    db.add(_issue(issue_key="AC-11", status="Done", assignee="Arsalaan", assignee_id="", extra_json={"product_manager": "Arsalaan"}))
    db.commit()
    result = build_week_actions(db, datetime(2026, 9, 1, 9, 0, 0))
    assert any(item.get("kind") == "assign_dev" and item.get("issue_key") == "AC-11" for item in result["other_actions"])


def test_monday_mapping_uses_product_internal(db, monkeypatch):
    monkeypatch.setattr("app.services.week_actions.current_dev_load", empty_dev_load)
    monkeypatch.setattr("app.services.week_actions.llm_prioritize_actions", lambda this_week, other: (this_week, other))
    monkeypatch.setattr(
        "app.services.week_actions.planned_tasks_from_db",
        lambda _db, _now: {
            "found": True,
            "chat": "#product-internal",
            "tasks": [{"title": "Ship checkout", "issue_key": "AC-10", "needs_ticket": False, "match_score": 9, "status": "Staging", "assignee": "Lovelesh"}],
        },
    )
    db.add(_issue())
    db.commit()
    result = build_week_actions(db, datetime(2026, 9, 1, 9, 0, 0))
    assert any(item.get("kind") == "week_plan" and item.get("issue_key") == "AC-10" for item in result["this_week"])


def test_staging_helper():
    assert is_staging_status("Staging")
    assert is_staging_status("UAT")
    assert not is_staging_status("Done")

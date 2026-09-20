from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import JiraIssue
from app.repositories.issues import apply_normalized, compact_changelog, list_active, merge_comments


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def test_merge_comments_dedupes_by_id_keeping_newer():
    old = [{"id": "1", "body": "a", "updated": "2026-01-01"}, {"id": "2", "body": "b", "updated": "2026-01-01"}]
    new = [{"id": "1", "body": "a2", "updated": "2026-02-01"}]
    merged = merge_comments(old, new)
    by_id = {c["id"]: c for c in merged if c.get("id")}
    assert by_id["1"]["body"] == "a2"
    assert by_id["2"]["body"] == "b"


def test_compact_changelog_keeps_status_only():
    items = [
        {"field": "status", "from": "To Do", "to": "Staging"},
        {"field": "description", "from": "long", "to": "longer"},
        {"field": "assignee", "from": "A", "to": "B"},
    ]
    out = compact_changelog(items)
    fields = {item["field"] for item in out}
    assert fields == {"status", "assignee"}


def test_aborted_issue_is_soft_archived_not_deleted():
    db = _session()
    row = apply_normalized(
        None,
        {
            "issue_key": "AC-9",
            "summary": "gone",
            "status": "Aborted",
            "comments_json": [],
            "changelog_json": [],
            "extra_json": {},
        },
        db,
    )
    db.commit()
    assert row.archived_at is not None
    assert db.query(JiraIssue).count() == 1
    assert list_active(db) == []


def test_reopened_issue_is_restored():
    db = _session()
    existing = apply_normalized(
        None,
        {"issue_key": "AC-9", "summary": "gone", "status": "Aborted", "comments_json": [], "changelog_json": [], "extra_json": {}},
        db,
    )
    db.commit()
    apply_normalized(
        existing,
        {"issue_key": "AC-9", "summary": "back", "status": "To Do", "comments_json": [], "changelog_json": [], "extra_json": {}},
        db,
    )
    db.commit()
    active = list_active(db)
    assert len(active) == 1
    assert active[0].archived_at is None
    assert active[0].summary == "back"


def test_list_issues_filters_board_without_descriptions():
    from app.api.routers.issues import list_issues

    db = _session()
    apply_normalized(None, {"issue_key": "AC-1", "summary": "Sense board", "status": "To Do", "issue_type": "Task", "description": "secret long body", "comments_json": [], "changelog_json": [], "extra_json": {}}, db)
    apply_normalized(None, {"issue_key": "PS-1", "summary": "Support board", "status": "To Do", "issue_type": "Bug", "description": "other body", "comments_json": [], "changelog_json": [], "extra_json": {}}, db)
    db.commit()
    compact = list_issues(board="AC", compact=True, db=db)
    assert [row["issue_key"] for row in compact["issues"]] == ["AC-1"]
    assert "description" not in compact["issues"][0]
    full = list_issues(board="AC", compact=False, db=db)
    assert full["issues"][0]["description"] == "secret long body"

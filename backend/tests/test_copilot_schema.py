"""Copilot write allowlist — hostile plans must never become previewable."""

import pytest

from app.services.copilot import validate_actions
from app.services.copilot_schema import (
    ActionKind,
    ALLOWED_FIELD_KEYS,
    fingerprints_match,
    parse_plan_document,
    plan_hash,
)


EPICS = [{"key": "AC-100", "title": "Checkout", "status": "In Progress"}]


def _validate(raw, notes="Ship the checkout banner", people=None, image_ids=None):
    return validate_actions(
        raw,
        epics=EPICS,
        image_ids=image_ids or [],
        people=people or ["Lovelesh"],
        notes=notes,
    )


def test_allowed_kinds_are_structural():
    assert {item.value for item in ActionKind} == {
        "create",
        "comment",
        "assign",
        "transition",
        "set_fields",
        "attach",
        "set_parent",
    }


HOSTILE_KINDS = [
    "delete",
    "destroy",
    "archive",
    "bulk",
    "bulk_edit",
    "bulk_transition",
    "watcher",
    "add_watcher",
    "worklog",
    "admin",
    "clone_epic",
    "create_epic",
    "remove",
    "drop",
    "unlink",
    "merge",
    "send_cliq",
    "edit_code",
    "webhook",
    "permission",
    "sprint_create",
    "clone",
    "move_project",
    "sql",
]


@pytest.mark.parametrize("kind", HOSTILE_KINDS)
def test_hostile_kind_never_previewable(kind):
    actions, questions = _validate([{"id": "a1", "kind": kind, "issue_key": "AC-1", "summary": "x", "body": "x"}])
    assert actions == []
    assert questions


@pytest.mark.parametrize(
    "kind",
    ["DELETE", "Create_Epic", "BULK", "Archive", "Remove", "Drop"],
)
def test_hostile_kind_case_insensitive(kind):
    actions, _ = _validate([{"kind": kind, "issue_key": "AC-1", "body": "x"}])
    assert actions == []


def test_invented_epic_not_ready():
    actions, questions = validate_actions(
        [
            {
                "kind": "create",
                "project": "AC",
                "issue_type": "Task",
                "summary": "Totally unique xyzzy work",
                "description": "xyzzy",
                "parent_epic": "AC-99999",
                "fields": {"product_area": "Other", "request_type": "Feature", "prd_link": "https://x", "priority": "Medium"},
            }
        ],
        epics=EPICS,
        image_ids=[],
        people=["Lovelesh"],
        notes="Totally unique xyzzy work",
    )
    assert len(actions) == 1
    assert actions[0]["ready"] is False
    assert actions[0].get("parent_epic") in {"", None}
    assert any("AC-99999" in item or "epic" in item.lower() for item in questions)


def test_set_parent_ps_scope_rejected():
    actions, questions = _validate([{"kind": "set_parent", "issue_key": "AC-1", "parent_epic": "PS-12"}])
    assert actions == []
    assert any("epic" in item.lower() or "PS-12" in item for item in questions)


def test_set_parent_invented_ac_rejected():
    actions, questions = _validate([{"kind": "set_parent", "issue_key": "AC-1", "parent_epic": "AC-404"}])
    assert actions == []
    assert any("AC-404" in item for item in questions)


def test_set_parent_on_ps_ticket_rejected():
    actions, _ = _validate([{"kind": "set_parent", "issue_key": "PS-1", "parent_epic": "AC-100"}])
    assert actions == []


def test_set_parent_valid():
    actions, _ = _validate([{"kind": "set_parent", "issue_key": "AC-1", "parent_epic": "AC-100"}])
    assert len(actions) == 1
    assert actions[0]["ready"] is True
    assert actions[0]["parent_epic"] == "AC-100"


def test_set_fields_alias():
    parsed = parse_plan_document({"actions": [{"kind": "update_fields", "issue_key": "AC-1", "fields": {"priority": "High"}}]})
    assert parsed.actions[0]["kind"] == "set_fields"
    actions, _ = _validate(parsed.actions)
    assert actions[0]["kind"] == "set_fields"
    assert actions[0]["ready"] is True


@pytest.mark.parametrize("alias, expected", [("move", "transition"), ("status", "transition"), ("parent", "set_parent"), ("set_field", "set_fields"), ("fields", "set_fields")])
def test_kind_aliases(alias, expected):
    parsed = parse_plan_document({"actions": [{"kind": alias, "issue_key": "AC-1", "transition": "Done", "parent_epic": "AC-100", "fields": {"priority": "High"}}]})
    assert parsed.actions[0]["kind"] == expected


def test_action_cap():
    raw = [{"kind": "comment", "issue_key": "AC-1", "body": f"note {i}"} for i in range(30)]
    parsed = parse_plan_document({"actions": raw})
    assert len(parsed.actions) == 8
    assert parsed.rejected


def test_plan_hash_stable():
    actions = [{"id": "a1", "kind": "comment", "issue_key": "AC-1", "body": "hi", "ready": True}]
    assert plan_hash(actions) == plan_hash([{**actions[0], "ready": False, "blocked": "x"}])


def test_plan_hash_changes_on_body():
    a = [{"id": "a1", "kind": "comment", "issue_key": "AC-1", "body": "hi"}]
    b = [{"id": "a1", "kind": "comment", "issue_key": "AC-1", "body": "bye"}]
    assert plan_hash(a) != plan_hash(b)


@pytest.mark.parametrize(
    "transition",
    ["Abort", "Cancel", "Cancelled", "Archive", "Delete", "Won't Do", "Wont Do", "abort and close"],
)
def test_denied_transitions_dropped(transition):
    actions, _ = _validate([{"kind": "transition", "issue_key": "AC-1", "transition": transition}])
    assert actions == []


def test_allowed_transition_previewable():
    actions, _ = _validate([{"kind": "transition", "issue_key": "AC-1", "transition": "Staging"}])
    assert len(actions) == 1
    assert actions[0]["ready"] is True
    assert actions[0]["transition"] == "Staging"


def test_foreign_project_comment_dropped():
    actions, _ = _validate([{"kind": "comment", "issue_key": "XX-99", "body": "hi"}])
    assert actions == []


def test_sql_looking_key_dropped():
    actions, _ = _validate([{"kind": "comment", "issue_key": "AC-1; DROP TABLE", "body": "hi"}])
    assert actions == []


def test_empty_comment_dropped():
    actions, _ = _validate([{"kind": "comment", "issue_key": "AC-1", "body": "   "}])
    assert actions == []


def test_valid_comment():
    actions, _ = _validate([{"kind": "comment", "issue_key": "ac-1", "body": "ship it"}])
    assert actions[0]["issue_key"] == "AC-1"
    assert actions[0]["ready"] is True


def test_unknown_assignee_dropped():
    actions, _ = _validate([{"kind": "assign", "issue_key": "AC-1", "assignee": "NotAPerson"}])
    assert actions == []


def test_known_assignee():
    actions, _ = _validate([{"kind": "assign", "issue_key": "AC-1", "assignee": "Lovelesh"}])
    assert len(actions) == 1
    assert actions[0]["ready"] is True


def test_unknown_field_keys_stripped():
    actions, _ = _validate([{"kind": "set_fields", "issue_key": "AC-1", "fields": {"customfield_999": "x", "not_a_field": 1}}])
    assert actions == []


def test_allowed_field_survives_with_junk():
    actions, _ = _validate([{"kind": "set_fields", "issue_key": "AC-1", "fields": {"priority": "High", "customfield_999": "x"}}])
    assert actions[0]["fields"] == {"priority": "High"}
    assert "customfield_999" not in actions[0]["fields"]


def test_allowed_field_keys_do_not_include_admin():
    assert "password" not in ALLOWED_FIELD_KEYS
    assert "account_id" not in ALLOWED_FIELD_KEYS
    assert "project" not in ALLOWED_FIELD_KEYS


def test_attach_without_this_turn_images_dropped():
    actions, _ = _validate([{"kind": "attach", "issue_key": "AC-1", "image_ids": ["not-real.png"]}])
    assert actions == []


def test_attach_needs_ticket_key():
    actions, _ = _validate(
        [{"kind": "attach", "issue_key": "", "image_ids": ["ok.png"]}],
        image_ids=["ok.png"],
    )
    assert len(actions) == 1
    assert actions[0]["ready"] is False


def test_attach_foreign_project_dropped():
    actions, _ = _validate(
        [{"kind": "attach", "issue_key": "XX-1", "image_ids": ["ok.png"]}],
        image_ids=["ok.png"],
    )
    assert actions == []


def test_create_unknown_project_dropped():
    actions, _ = _validate(
        [{"kind": "create", "project": "ZZ", "issue_type": "Task", "summary": "x", "fields": {}}],
        notes="x",
    )
    assert actions == []


def test_create_missing_summary_not_ready():
    actions, questions = _validate(
        [{"kind": "create", "project": "AC", "issue_type": "Task", "summary": "", "description": "x"}],
        notes="notes exist",
    )
    assert actions
    assert actions[0]["ready"] is False
    assert questions


def test_ps_bug_does_not_need_epic():
    actions, _ = _validate(
        [
            {
                "kind": "create",
                "project": "PS",
                "issue_type": "Bug",
                "summary": "Login 500",
                "description": "repro",
                "fields": {
                    "priority": "High",
                    "steps_to_reproduce": "open app",
                    "customer": "Acme",
                    "product_area": "Other",
                },
            }
        ],
        notes="Login 500",
    )
    assert len(actions) == 1
    # may still miss schema fields; must not require parent epic
    assert actions[0].get("needs_epic") is False
    assert "Parent epic" not in (actions[0].get("missing") or [])


def test_ac_task_without_epic_not_ready():
    actions, _ = validate_actions(
        [
            {
                "kind": "create",
                "project": "AC",
                "issue_type": "Task",
                "summary": "xyzzy unique work",
                "description": "xyzzy",
                "fields": {"product_area": "Other", "request_type": "Feature", "prd_link": "https://x", "priority": "Medium"},
            }
        ],
        epics=EPICS,
        image_ids=[],
        people=["Lovelesh"],
        notes="xyzzy unique work",
    )
    assert actions[0]["ready"] is False
    assert actions[0]["needs_epic"] is True


def test_non_object_action_rejected():
    parsed = parse_plan_document({"actions": ["delete everything", 12, None]})
    assert parsed.actions == []
    assert len(parsed.rejected) == 3


def test_missing_kind_rejected():
    parsed = parse_plan_document({"actions": [{"issue_key": "AC-1", "body": "hi"}]})
    assert parsed.actions == []
    assert parsed.rejected


def test_extra_keys_ignored_on_schema():
    parsed = parse_plan_document({"actions": [{"kind": "comment", "issue_key": "AC-1", "body": "hi", "jql": "delete", "webhook": "http://x"}]})
    assert "jql" not in parsed.actions[0]
    assert "webhook" not in parsed.actions[0]


def test_fingerprint_mismatch_on_status():
    left = {"AC-1": {"status": "To Do", "updated_at": "1", "archived": False}}
    right = {"AC-1": {"status": "Done", "updated_at": "1", "archived": False}}
    assert fingerprints_match(left, left)
    assert not fingerprints_match(left, right)


def test_fingerprint_mismatch_on_deleted_issue():
    left = {"AC-1": {"status": "To Do", "updated_at": "1", "archived": False}}
    assert not fingerprints_match(left, {})


def test_fingerprint_mismatch_on_archive():
    left = {"AC-1": {"status": "To Do", "updated_at": "1", "archived": False}}
    right = {"AC-1": {"status": "To Do", "updated_at": "1", "archived": True}}
    assert not fingerprints_match(left, right)


def test_mixed_plan_keeps_only_allowed():
    actions, questions = _validate(
        [
            {"kind": "delete", "issue_key": "AC-1"},
            {"kind": "comment", "issue_key": "AC-1", "body": "ok"},
            {"kind": "create_epic", "summary": "nope"},
            {"kind": "transition", "issue_key": "AC-1", "transition": "Staging"},
        ]
    )
    kinds = {item["kind"] for item in actions}
    assert kinds == {"comment", "transition"}
    assert questions

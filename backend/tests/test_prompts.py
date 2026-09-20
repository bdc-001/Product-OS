from app.services.prompts import parse_json_object, parse_standup_items, strip_example_leaks
from app.services.team import canonical_name, developer_handoff_names, roster_prompt_block
from app.services.week_actions import heuristic_prioritize_actions


def test_nischal_normalizes_to_nishchal():
    assert canonical_name("Nischal") == "Nishchal"
    assert canonical_name("nischal") == "Nishchal"


def test_handoff_includes_neha():
    names = developer_handoff_names()
    assert "Neha" in names
    assert "Nishchal" in names
    assert "Nischal" not in names


def test_roster_block_has_one_spelling():
    block = roster_prompt_block()
    assert "Nishchal" in block
    assert '"Nischal" → "Nishchal"' in block


def test_parse_json_object_tolerates_wrapper():
    raw = "Here you go\n{\"ok\": true, \"needs_attention\": []}\nthanks"
    assert parse_json_object(raw)["ok"] is True


def test_standup_item_repairs_bad_action_type():
    items = parse_standup_items(
        [
            {"title": "Follow Lovelesh", "action_type": "poke", "sources": [{"type": "jira", "ref": "AC-1"}], "issue_key": "AC-1"},
            {"title": "", "body": ""},
            "not an object",
            {"title": "Ok", "action_type": "escalate", "confidence": "high", "sources": [{"type": "cliq", "ref": "#product-internal"}]},
        ]
    )
    assert len(items) == 2
    assert items[0]["action_type"] == "follow_up"
    assert items[1]["action_type"] == "escalate"
    assert items[1]["confidence"] == "HIGH"


def test_strip_example_leaks_unless_in_payload():
    text = "We shipped the Billing Dashboard and Custom CRM."
    cleaned = strip_example_leaks(text, {"angle": "nothing relevant"})
    assert "Billing Dashboard" not in cleaned
    kept = strip_example_leaks(text, {"angle": "Billing Dashboard for CSMs"})
    assert "Billing Dashboard" in kept


def test_heuristic_prioritize_keeps_all_and_orders():
    this_week = [{"kind": "week_plan", "issue_key": "AC-1", "title": "plan"}]
    other = [
        {"kind": "blocker", "issue_key": "AC-2", "title": "b", "urgency": 5},
        {"kind": "assign_dev", "issue_key": "AC-3", "title": "a", "urgency": 9},
        {"kind": "uat", "issue_key": "AC-4", "title": "u", "urgency": 8},
        {"kind": "qa_remind", "issue_key": "AC-5", "title": "q", "urgency": 7},
    ]
    week, rest = heuristic_prioritize_actions(this_week, other)
    assert week == this_week
    assert [item["kind"] for item in rest] == ["assign_dev", "uat", "qa_remind", "blocker"]
    assert {item["issue_key"] for item in rest} == {"AC-2", "AC-3", "AC-4", "AC-5"}

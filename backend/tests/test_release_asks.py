import json
from datetime import datetime

from app.services.release_asks import classify_released_task, collect_release_asks, dm_text, released_on
from app.services.team import match_notes_pm
from app.services.time_window import tz


def _task(*, key="AC-100", summary="Entity Dashboard", status="Released", issue_type="Task", pm="Lalit Kumar", day="2026-09-01", extra=None, changelog=None):
    extras = {"product_manager": pm, "resolution_date": day, **(extra or {})}
    return {
        "issue_key": key,
        "summary": summary,
        "status": status,
        "issue_type": issue_type,
        "updated_at": f"{day}T12:00:00+05:30",
        "url": f"https://convin.atlassian.net/browse/{key}",
        "extra_json": extras,
        "changelog_json": changelog
        if changelog is not None
        else [
            {"field": "status", "from": "Done", "to": "Released", "created": f"{day}T18:15:00.000+0530"},
        ],
    }


def test_match_notes_pm_names():
    assert match_notes_pm("Lalit Kumar")["short"] == "Lalit"
    assert match_notes_pm("Vidya S")["short"] == "Vidhya"
    assert match_notes_pm("Arsalaan") is None


def test_released_on_uses_first_changelog_date():
    day = released_on(
        [
            {"field": "status", "to": "Done", "created": "2026-08-20T10:00:00.000+0530"},
            {"field": "status", "to": "Released", "created": "2026-09-01T18:15:00.000+0530"},
            {"field": "status", "to": "Released", "created": "2026-09-02T09:00:00.000+0530"},
        ],
        {"resolution_date": "2026-09-03"},
    )
    assert day == "2026-09-01"


def test_collect_filters_pm_status_type_and_board():
    rows = [
        _task(key="AC-1", summary="Wallet retry", pm="Lalit"),
        _task(key="AC-2", summary="Entity Dashboard", pm="Vidhya Nair", day="2026-08-20"),
        _task(key="AC-3", summary="Other PM", pm="Arsalaan"),
        _task(key="AC-4", summary="Still open", status="Done", pm="Lalit"),
        _task(key="AC-5", summary="Bug", issue_type="Bug", pm="Lalit"),
        _task(key="PS-9", summary="Support", pm="Lalit"),
        _task(key="AC-6", summary="Old", pm="Lalit", day="2026-07-01", changelog=[{"field": "status", "to": "Released", "created": "2026-07-01T10:00:00.000+0530"}]),
    ]
    groups = collect_release_asks(rows, after_date="2026-08-04")
    by_pm = {group["pm"]: [t["issue_key"] for t in group["tickets"]] for group in groups}
    assert by_pm == {"Lalit": ["AC-1"], "Vidhya": ["AC-2"]}
    vidhya = next(group for group in groups if group["pm"] == "Vidhya")
    assert vidhya["tickets"][0]["released_on"] == "2026-08-20"
    assert vidhya["tickets"][0]["released_label"] == "20 Aug 2026"


def test_list_always_includes_both_pms(tmp_path, monkeypatch):
    from app.services import release_asks
    from app.services.release_asks import list_release_asks

    monkeypatch.setattr(release_asks, "STATE_PATH", tmp_path / "release_asks.json")
    payload = list_release_asks(
        normalized=[_task(key="AC-1", pm="Lalit", day="2026-09-07")],
        now=datetime(2026, 9, 7, 12, 0, tzinfo=tz()),
    )
    assert [group["pm"] for group in payload["groups"]] == ["Lalit", "Vidhya"]
    assert [t["issue_key"] for t in payload["groups"][0]["tickets"]] == ["AC-1"]
    assert payload["groups"][1]["tickets"] == []
    assert payload["after_date"] == "2026-09-07"
    assert payload["queue_start"] == "2026-09-07"


def test_classify_requires_exact_released():
    assert classify_released_task(_task(status="Ready for Release"), "2026-08-01") is None
    assert classify_released_task(_task(status="released"), "2026-08-01")["issue_key"] == "AC-100"


def test_nudge_text_has_tickets_and_feature_names():
    groups = collect_release_asks(
        [_task(key="AC-4120", summary="Entity Dashboard", pm="Lalit", day="2026-09-01")],
        after_date="2026-08-01",
    )
    text = dm_text("Lalit", groups[0]["tickets"])
    assert "AC-4120" in text
    assert "Entity Dashboard" in text
    assert "Status: Released" in text
    assert "Type: Task" in text
    assert "Released on: 1 Sep 2026" in text
    assert "https://convin.atlassian.net/browse/AC-4120" in text
    assert "#product-internal" in text
    assert "not other open work" in text.lower()
    assert groups[0]["email"] == "lalit@convin.ai"


def test_vidhya_cliq_email_is_canonical():
    groups = collect_release_asks(
        [_task(key="AC-9", summary="Dashboards", pm="Vidhya Sriram", extra={"product_manager_email": "vidhya@convin.ai"})],
        after_date="2026-08-01",
    )
    assert groups[0]["email"] == "vidhya.sriram@convin.ai"
    assert groups[0]["tickets"][0]["email"] == "vidhya.sriram@convin.ai"


def test_classify_ignores_updated_at_without_released_date():
    row = _task(changelog=[], extra={"resolution_date": ""})
    assert classify_released_task(row, "2026-08-01") is None


def test_send_nudge_dms_only_released_tickets(monkeypatch, tmp_path):
    from app.services import release_asks
    from app.services.release_asks import send_nudge

    monkeypatch.setattr(release_asks, "STATE_PATH", tmp_path / "release_asks.json")
    sent = []

    class FakeCliq:
        configured = True

        def send_dm(self, text, *, chat_id="", email=""):
            sent.append((email or chat_id, text))
            return {}

        def send_to_email(self, email, text):
            return self.send_dm(text, email=email)

        def send_message(self, chat_id, text):
            raise AssertionError("must not post the reminder to a channel")

    monkeypatch.setattr("app.services.release_asks.CliqClient", lambda: FakeCliq())
    groups = collect_release_asks(
        [
            _task(key="AC-1", summary="Wallet retry", pm="Lalit"),
            _task(key="AC-2", summary="Entity Dashboard", pm="Vidhya Sriram"),
            _task(key="AC-4", summary="Still open", status="Done", pm="Lalit"),
            _task(key="AC-5", summary="Bug", issue_type="Bug", pm="Vidhya Sriram"),
        ],
        after_date="2026-08-01",
    )
    result = send_nudge(groups=groups)
    assert result["ok"] is True
    emails = [row[0] for row in sent]
    assert emails == ["lalit@convin.ai", "vidhya.sriram@convin.ai"]
    vidhya_text = sent[1][1]
    assert "AC-2" in vidhya_text
    assert "Entity Dashboard" in vidhya_text
    assert "AC-4" not in vidhya_text
    assert "AC-5" not in vidhya_text
    assert "Status: Released" in vidhya_text


def test_send_nudge_one_pm_leaves_the_other(monkeypatch, tmp_path):
    from app.services import release_asks
    from app.services.release_asks import send_nudge

    monkeypatch.setattr(release_asks, "STATE_PATH", tmp_path / "release_asks.json")
    sent = []

    class FakeCliq:
        configured = True

        def send_dm(self, text, *, chat_id="", email=""):
            sent.append(email or chat_id)
            return {}

    monkeypatch.setattr("app.services.release_asks.CliqClient", lambda: FakeCliq())
    groups = collect_release_asks(
        [_task(key="AC-1", pm="Lalit"), _task(key="AC-2", pm="Vidhya Sriram")],
        after_date="2026-08-01",
    )
    result = send_nudge(groups=groups, pm="Lalit")
    assert result["ok"] is True
    assert sent == ["lalit@convin.ai"]
    assert [row["pm"] for row in result["sent"]] == ["Lalit"]


def test_vidhya_failure_does_not_block_lalit(monkeypatch, tmp_path):
    from app.services import release_asks
    from app.services.release_asks import send_nudge

    monkeypatch.setattr(release_asks, "STATE_PATH", tmp_path / "release_asks.json")
    sent = []

    class FakeCliq:
        configured = True

        def send_dm(self, text, *, chat_id="", email=""):
            if "vidhya" in (email or "") or chat_id == "1207194750863251476":
                raise RuntimeError("401")
            sent.append(email or chat_id)
            return {}

    monkeypatch.setattr("app.services.release_asks.CliqClient", lambda: FakeCliq())
    groups = collect_release_asks(
        [_task(key="AC-1", pm="Lalit"), _task(key="AC-2", pm="Vidhya Sriram")],
        after_date="2026-08-01",
    )
    result = send_nudge(groups=groups)
    assert result["ok"] is True
    assert sent == ["lalit@convin.ai"]
    assert result["errors"]
    assert any(row["pm"] == "Lalit" and row["ok"] for row in result["sent"])
    assert any(row["pm"] == "Vidhya" and not row["ok"] for row in result["sent"])


def test_queue_start_drops_tickets_before_today(tmp_path, monkeypatch):
    from app.services import release_asks
    from app.services.release_asks import list_release_asks

    monkeypatch.setattr(release_asks, "STATE_PATH", tmp_path / "release_asks.json")
    (tmp_path / "release_asks.json").write_text(
        '{"last_nudged_at": "2026-09-03T13:57:31+05:30", "sent": [{"pm": "Lalit", "ok": true}]}',
        encoding="utf-8",
    )
    payload = list_release_asks(
        normalized=[
            _task(key="AC-4100", pm="Lalit", day="2026-09-01"),
            _task(key="AC-4101", pm="Lalit", day="2026-09-07"),
        ],
        now=datetime(2026, 9, 7, 12, 0, tzinfo=tz()),
    )
    assert payload["after_date"] == "2026-09-07"
    assert payload["last_nudged_at"] == ""
    assert [ticket["issue_key"] for ticket in payload["groups"][0]["tickets"]] == ["AC-4101"]


def test_dismiss_excludes_ticket_from_list_and_nudge(tmp_path, monkeypatch):
    from app.services import release_asks
    from app.services.release_asks import dismiss_ticket, list_release_asks, send_nudge

    monkeypatch.setattr(release_asks, "STATE_PATH", tmp_path / "release_asks.json")
    now = datetime(2026, 9, 7, 12, 0, tzinfo=tz())
    rows = [
        _task(key="AC-1", summary="Keep me", pm="Lalit", day="2026-09-07"),
        _task(key="AC-2", summary="Skip me", pm="Lalit", day="2026-09-07"),
    ]
    listing = list_release_asks(normalized=rows, now=now)
    assert {ticket["issue_key"] for ticket in listing["groups"][0]["tickets"]} == {"AC-1", "AC-2"}

    result = dismiss_ticket("AC-2")
    assert result["ok"] is True
    assert result["issue_key"] == "AC-2"
    next_listing = list_release_asks(normalized=rows, now=now)
    assert [ticket["issue_key"] for ticket in next_listing["groups"][0]["tickets"]] == ["AC-1"]
    assert "AC-2" in (next_listing.get("dismissed") or [])
    assert "AC-2" not in {ticket["issue_key"] for ticket in next_listing["groups"][0]["tickets"]}

    sent = []

    class FakeCliq:
        configured = True

        def send_dm(self, text, *, chat_id="", email=""):
            sent.append(text)
            return {}

    class FakeJira:
        configured = True

        def fetch_released_ac_tasks(self, after):
            return rows

        def normalize(self, issue):
            return issue

    monkeypatch.setattr(release_asks, "now_local", lambda: now)
    monkeypatch.setattr("app.services.release_asks.CliqClient", lambda: FakeCliq())
    monkeypatch.setattr("app.services.release_asks.JiraClient", lambda: FakeJira())
    result = send_nudge(pm="Lalit")
    assert result["ok"] is True
    assert len(sent) == 1
    assert "AC-1" in sent[0]
    assert "Keep me" in sent[0]
    assert "AC-2" not in sent[0]
    assert "Skip me" not in sent[0]
    assert result["sent"][0]["keys"] == ["AC-1"]
    saved = json.loads((tmp_path / "release_asks.json").read_text(encoding="utf-8"))
    recorded = [key for row in saved.get("sent") or [] for key in (row.get("keys") or [])]
    assert recorded == ["AC-1"]
    assert "AC-2" not in json.dumps(saved.get("sent") or [])


def test_data_branch_isolates_release_ask_state(tmp_path, monkeypatch):
    from app.services import release_asks
    from app.services.release_asks import dismiss_ticket, state_file

    monkeypatch.setattr(release_asks, "_DEFAULT_STATE_PATH", tmp_path / "legacy.json")
    monkeypatch.setattr(release_asks, "STATE_PATH", tmp_path / "legacy.json")
    monkeypatch.setattr(release_asks, "STORES_DIR", tmp_path / "stores")
    monkeypatch.setattr(release_asks, "data_branch_name", lambda: "release/demo")

    path = state_file()
    assert path == tmp_path / "stores" / "release-demo" / "release_asks.json"
    dismiss_ticket("AC-9")
    text = path.read_text(encoding="utf-8")
    assert "AC-9" in text
    assert not (tmp_path / "legacy.json").exists()


def test_profile_persists_data_branch(tmp_path, monkeypatch):
    from app.services import profile

    monkeypatch.setattr(profile, "PROFILE_PATH", tmp_path / "profile.json")
    saved = profile.save_profile({"data_branch": "release/demo"})
    assert saved["data_branch"] == "release/demo"
    assert profile.load_profile()["data_branch"] == "release/demo"


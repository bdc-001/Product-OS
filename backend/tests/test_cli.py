import json

import pytest

from app import cli
from app.database import SessionLocal
from app.models import Run
from app.pipelines.tasks import TASKS


def _run_cli(*argv: str) -> int:
    with pytest.raises(SystemExit) as exit_info:
        cli.main(list(argv))
    return int(exit_info.value.code or 0)


def test_run_executes_the_pipeline_inline_and_writes_a_summary(monkeypatch, tmp_path):
    calls = []

    def fake(db, set_step, params):
        calls.append(params.get("trigger"))
        set_step("competitive", {"ok": True, "status": "done", "count": 3, "nested": {"skip": True}})
        return {"ok": True}

    monkeypatch.setitem(TASKS, "competitive_refresh", fake)
    out = tmp_path / "summary.json"
    assert _run_cli("run", "market-watch", "--trigger", "schedule", "--summary-file", str(out)) == 0
    summary = json.loads(out.read_text())
    assert summary["status"] == "completed"
    assert summary["steps"]["competitive"] == {"ok": True, "status": "done", "count": 3}
    assert calls == ["schedule"]
    db = SessionLocal()
    try:
        row = db.get(Run, summary["run_id"])
        assert (row.pipeline_id, row.trigger, row.started_by, row.max_attempts) == ("market-watch", "schedule", "cli", 1)
    finally:
        db.close()


def test_failed_inline_run_exits_non_zero_without_requeueing(monkeypatch, tmp_path):
    def boom(db, set_step, params):
        raise RuntimeError("source down")

    monkeypatch.setitem(TASKS, "competitive_refresh", boom)
    out = tmp_path / "summary.json"
    assert _run_cli("run", "market-watch", "--trigger", "schedule", "--summary-file", str(out)) == 1
    summary = json.loads(out.read_text())
    assert summary["status"] == "failed" and "source down" in summary["error"]


def test_run_refuses_a_pipeline_whose_connection_is_missing(capsys):
    assert _run_cli("run", "jira-sync") == 2
    assert "Connect jira first" in capsys.readouterr().out

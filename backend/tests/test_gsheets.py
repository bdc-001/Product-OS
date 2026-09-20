from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import MarketingFeature
from app.services import gsheets, marketing


@pytest.fixture
def db():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def test_header_aliases_map_shared_columns():
    mapped = gsheets._header_map(["Module", "Feature", "Description", "Use Case", "Industry"])
    assert mapped == {"module": 0, "name": 1, "summary": 2, "description": 3, "audience": 4}


def test_header_aliases_map_video_columns():
    mapped = gsheets._header_map(["Module", "Feature", "Description", "Use Case", "Industry", "Status", "Script", "Video"])
    assert mapped["sheet_status"] == 5 and mapped["script"] == 6 and mapped["video"] == 7


def test_two_liner_keeps_two_sentences():
    assert marketing.two_liner("First sentence. Second sentence. Third.") == "First sentence. Second sentence."
    assert marketing.product_module("Released") == "Sense"
    assert marketing.product_module("AI Agents") == "AI Agents"


def test_unconfigured_sheet_is_skipped(db, monkeypatch):
    monkeypatch.setattr(gsheets, "sheets_configured", lambda: False)
    assert gsheets.pull_into(db)["skipped"]
    assert gsheets.push_from(db)["skipped"]


def test_pull_adds_new_rows_and_updates_nonempty_cells(db, monkeypatch):
    existing = MarketingFeature(
        name="Agent Testing", identity="agent testing", module="Old", summary="Old line",
        description="Old use case", audience="All", status="draft", source="manual",
    )
    db.add(existing)
    db.commit()
    monkeypatch.setattr(gsheets, "sheets_configured", lambda: True)
    monkeypatch.setattr(gsheets, "read_rows", lambda: [
        {"module": "AI Agents", "name": "Agent Testing", "summary": "Try the agent before customers hear it.",
         "description": "Run a live test call.", "audience": "BFSI"},
        {"module": "Privacy", "name": "PII Masking", "summary": "Hide sensitive values in the UI.",
         "description": "", "audience": "Compliance teams"},
        {"module": "", "name": "Agent Testing", "summary": "", "description": "", "audience": ""},
    ])
    result = gsheets.pull_into(db)
    assert result["ok"] and result["added"] == 1 and result["updated"] == 1
    testing = db.query(MarketingFeature).filter_by(identity="agent testing").one()
    assert testing.module == "AI Agents" and "live test" in testing.description
    masking = db.query(MarketingFeature).filter_by(identity="pii masking").one()
    assert masking.source == "sheet" and masking.module == "Privacy"


def test_pull_updates_video_and_script_when_present(db, monkeypatch):
    db.add(MarketingFeature(
        name="Agent Testing", identity="agent testing", module="AI Agents",
        summary="Try it.", description="Use it.", audience="All", video="old.mp4",
    ))
    db.commit()
    monkeypatch.setattr(gsheets, "sheets_configured", lambda: True)
    monkeypatch.setattr(gsheets, "read_rows", lambda: [{
        "module": "AI Agents", "name": "Agent Testing", "summary": "Try it.",
        "description": "Use it.", "audience": "All", "sheet_status": "In Progress",
        "script": "Open the test call.", "video": "reel.mp4",
    }])
    result = gsheets.pull_into(db)
    row = db.query(MarketingFeature).filter_by(identity="agent testing").one()
    assert result["ok"] and result["updated"] == 1
    assert row.video == "reel.mp4" and row.script.startswith("Open") and row.sheet_status == "In Progress"


def test_push_writes_shared_columns_and_skips_dismissed(db, monkeypatch):
    db.add(MarketingFeature(name="Keep", identity="keep", module="AI Agents", summary="Two lines of copy.",
                            description="A concrete use case.", audience="BFSI", status="draft"))
    db.add(MarketingFeature(name="Gone", identity="gone", module="AI Agents", summary="Hidden",
                            description="Dismissed", audience="None", status="dismissed"))
    db.commit()
    written = []
    monkeypatch.setattr(gsheets, "sheets_configured", lambda: True)
    monkeypatch.setattr(gsheets, "write_rows", lambda rows: written.append(rows) or "Sheet1")
    result = gsheets.push_from(db)
    assert result["ok"] and result["count"] == 1
    assert written[0] == [["AI Agents", "Keep", "Two lines of copy.", "A concrete use case.", "BFSI", "Not started", "", ""]]


def test_unformatted_sheet_is_treated_as_empty(monkeypatch):
    class Values:
        def get(self, **kwargs):
            return self
        def execute(self):
            return {"values": [["Notes", "Scratch"]]}
    class Spreadsheets:
        def get(self, **kwargs):
            return SimpleNamespace(execute=lambda: {"sheets": [{"properties": {"title": "Sheet1"}}]})
        def values(self):
            return Values()
    monkeypatch.setattr(gsheets, "_service", lambda: SimpleNamespace(spreadsheets=lambda: Spreadsheets()))
    monkeypatch.setattr(gsheets, "sheet_id", lambda: "sheet")
    assert gsheets.read_rows() == []


def test_permission_error_tells_operator_to_share(monkeypatch):
    monkeypatch.setattr(gsheets, "_service_email", lambda: "bot@example.iam.gserviceaccount.com")
    message = gsheets._explain(RuntimeError("403 PERMISSION_DENIED"))
    assert "bot@example.iam.gserviceaccount.com" in message
    assert "Editor" in message

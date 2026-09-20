from types import SimpleNamespace
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base, get_db
from app.models import CodebaseModule, CodebaseSnapshot, MarketingCampaign, MarketingFeature, MarketingScan
from app.services import marketing, marketing_manager as manager

@pytest.fixture(autouse=True)
def no_live_manager(monkeypatch, tmp_path):
    monkeypatch.setattr(marketing, "CAMPAIGN_DIR", tmp_path)
    monkeypatch.setattr(manager, "chat_json", lambda *a, **k: pytest.fail("Tests must mock PMM calls"))
    monkeypatch.setattr("app.config.settings.marketing_sheet_id", "")
from app.services.marketing_video import bind_scene, document_html

@pytest.fixture
def db():
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()

@pytest.fixture
def client(db):
    from app.api.routers.marketing import router
    app = FastAPI(); app.include_router(router)
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)

def seed(db, **kwargs):
    row = MarketingFeature(name="AI campaigns", identity="ai campaigns", description="Create campaigns", audience="Sales teams", **kwargs)
    db.add(row); db.commit()
    return row

def test_sheet_updates_are_validated_and_versioned(client, db):
    assert client.post("/marketing/features", json={"name": "  "}).status_code == 422
    created = client.post("/marketing/features", json={"name": "Campaign analytics", "description": "Insights"}).json()
    assert created["source"] == "manual"
    assert client.post("/marketing/features", json={"name": " Campaign ANALYTICS "}).status_code == 409
    saved = client.put(f"/marketing/features/{created['id']}", json={"name": "Campaign analytics", "description": "Edited", "revision": 1}).json()
    assert saved["revision"] == 2
    assert client.put(f"/marketing/features/{created['id']}", json={"name": "Campaign analytics", "revision": 1}).status_code == 409
    assert db.get(MarketingFeature, created["id"]).description == "Edited"

def test_generation_requires_useful_description(client, db):
    row = seed(db, status="draft")
    assert client.post("/marketing/generate", json={"feature_ids": [row.id]}).status_code == 400
    assert client.post("/marketing/generate", json={"feature_ids": []}).status_code == 422
    assert client.post("/marketing/generate", json={"feature_ids": [999]}).status_code == 404

def test_discovery_waits_for_first_manual_entry(db, monkeypatch):
    monkeypatch.setattr(marketing, "chat_json", lambda *a, **k: pytest.fail("No model call before initial sheet"))
    assert marketing.discover_features(db)["count"] == 0

def campaign_content():
    raw = {"strategy": {"positioning": "Manage campaigns in Sense"}, "video": {"title": "Sense campaigns", "scenes": []}}
    for channel in marketing.CHANNELS:
        raw[channel] = {"title": channel.title(), "body": "Complete feature content with a customer benefit. " * 8}
    for i in range(12):
        raw["video"]["scenes"].append({"kind": "hook" if i == 0 else "cta" if i == 11 else "benefit",
            "headline": "Understand your campaigns", "body": "See how your campaigns are performing.",
            "narration": "See how each campaign performs in one clear view.", "evidence": "User supplied description"})
    return raw

def test_content_validation_rejects_incomplete_outputs_and_overflow():
    raw = campaign_content()
    assert marketing.validate_content(raw) == raw
    raw["linkedin"]["body"] = "Outline"
    with pytest.raises(ValueError, match="incomplete"): marketing.validate_content(raw)
    raw = campaign_content(); raw["video"]["scenes"][0]["headline"] = "very " * 20
    with pytest.raises(ValueError, match="readable"): marketing.validate_content(raw)

def test_audio_timing_prevents_cutoffs_and_overlapping_captions():
    timed = bind_scene(campaign_content()["video"]["scenes"][0], 4.25, 150)
    assert timed["frames"] % 3 == 0 and timed["frames"] >= timed["audioFrames"] + 9
    assert timed["from"] == 150
    assert timed["captions"][0]["to"] <= timed["captions"][1]["from"]
    assert timed["captions"][-1]["to"] < timed["frames"]
    with pytest.raises(ValueError): bind_scene(campaign_content()["video"]["scenes"][0], float("nan"), 0)

def test_printable_documents_escape_model_html():
    rendered = document_html("<script>alert(1)</script>", "# Title\n\n<script>alert(2)</script>")
    assert "<script>" not in rendered and "&lt;script&gt;" in rendered and "<h2>Title</h2>" in rendered

def test_generation_failure_never_creates_placeholder_content(db, tmp_path, monkeypatch):
    row = seed(db, status="ready")
    campaign = MarketingCampaign(feature_id=row.id, feature_revision=1, feature_snapshot=marketing.feature_out(row))
    db.add(campaign); db.commit()
    monkeypatch.setattr(marketing, "CAMPAIGN_DIR", tmp_path)
    def fail(*a, **k): raise RuntimeError("Model unavailable")
    monkeypatch.setattr(manager, "chat_json", fail)
    assert marketing.produce_campaign(db, campaign)["ok"] is False
    assert campaign.status == "failed" and not campaign.content and not campaign.assets

def test_retry_preserves_content_and_skips_successful_video(db, tmp_path, monkeypatch):
    row = seed(db, status="ready")
    campaign = MarketingCampaign(feature_id=row.id, feature_revision=1, feature_snapshot=marketing.feature_out(row),
        content=campaign_content(), assets=[{"filename": "landscape.mp4"}, {"filename": "portrait.mp4"}], status="partial")
    db.add(campaign); db.commit()
    monkeypatch.setattr(marketing, "CAMPAIGN_DIR", tmp_path)
    monkeypatch.setattr(marketing, "chat_json", lambda *a, **k: pytest.fail("Must not regenerate saved content"))
    monkeypatch.setattr("app.services.marketing_video.render_campaign_video", lambda *a, **k: pytest.fail("Must not rerender completed videos"))
    uploaded = []
    monkeypatch.setattr(marketing, "upload_campaign", lambda db, row: uploaded.append(row.id))
    assert marketing.produce_campaign(db, campaign)["ok"] is True
    assert uploaded == [campaign.id] and campaign.status == "completed"

def test_upload_checkpoint_reuses_remote_files(db, monkeypatch):
    row = seed(db)
    campaign = MarketingCampaign(feature_id=row.id, feature_revision=1, feature_snapshot=marketing.feature_out(row), drive_folder_id="folder",
        assets=[{"filename": "linkedin.md", "mime": "text/markdown", "file_id": "existing"}, {"filename": "document.md", "mime": "text/markdown"}])
    db.add(campaign); db.commit()
    class Files:
        def list(self, **kwargs):
            return SimpleNamespace(execute=lambda **k: {"files": [{"id": "recovered", "webViewLink": "https://drive.google.com/file/recovered"}]})
        def create(self, **kwargs): pytest.fail("Recovered uploads must not be duplicated")
    monkeypatch.setattr(marketing, "drive_destination", lambda: {"configured": True, "folder_id": "root"})
    monkeypatch.setattr(marketing, "_service", lambda: SimpleNamespace(files=lambda: Files()))
    marketing.upload_campaign(db, campaign)
    assert [a["file_id"] for a in campaign.assets] == ["existing", "recovered"]

def test_download_only_allows_manifest_entries(client, db, tmp_path, monkeypatch):
    from app.api.routers import marketing as routes
    row = seed(db)
    campaign = MarketingCampaign(feature_id=row.id, feature_revision=1, feature_snapshot=marketing.feature_out(row), assets=[{"filename": "document.md", "mime": "text/markdown"}])
    db.add(campaign); db.commit()
    folder = tmp_path / str(campaign.id); folder.mkdir(); (folder / "document.md").write_text("safe")
    (folder / "private.txt").write_text("private")
    monkeypatch.setattr(routes, "CAMPAIGN_DIR", tmp_path)
    assert client.get(f"/marketing/campaigns/{campaign.id}/files/document.md").text == "safe"
    assert client.get(f"/marketing/campaigns/{campaign.id}/files/private.txt").status_code == 404

def test_csv_export_neutralizes_formulas(client, db):
    row = seed(db); row.script = '=HYPERLINK("x")'; db.commit()
    response = client.get("/marketing/features.csv")
    assert response.status_code == 200 and "'=HYPERLINK" in response.text
    assert "Module,Feature,Description,Use Case,Industry" in response.text


QUOTE = "View a breakdown of campaign results by channel."

def decision(verdict="approve", selected=("linkedin_post",)):
    selected = selected if verdict == "approve" else ()
    return {"verdict": verdict, "rationale": "A clear customer-facing capability with a specific buyer use case.",
        "audience": "Sales operations", "buyer_problem": "Teams need to understand their campaign results.",
        "positioning": "Understand campaign outcomes by channel.", "evidence_quotes": [QUOTE],
        "missing_evidence": ["Deployment availability is not documented."] if verdict == "defer" else [],
        "cta": "Explore how Sense supports campaign reporting.",
        "assignments": [{"format": key, "reason": "This format clearly explains the reporting workflow.", "angle": "Compare campaign outcomes by channel.",
                         "objective": "Help buyers understand the reporting capability.", "outline": ["Customer problem", "Supported workflow"]} for key in selected],
        "omitted_formats": {key: "Additional depth or visual treatment is not justified here." for key in manager.FORMATS if key not in selected}}


def mock_release(monkeypatch, raw):
    release = {"sha": "a" * 40, "base_sha": "b" * 40, "branch": "release/2026-09-10", "merged_at": "2026-09-10T10:00:00Z"}
    monkeypatch.setattr("app.services.release_detect.detect_release_merges", lambda **kw: [release])
    monkeypatch.setattr(manager, "release_batches", lambda release: [[{"path": "convin-activate/internal/service/campaign.go", "text": QUOTE, "added_lines": [QUOTE]}]])
    monkeypatch.setattr(manager, "chat_json", lambda *a, **k: raw)
    return release


def discovered_item(verdict="approve"):
    return {"name": "Channel results", "description": QUOTE, "evidence_quote": QUOTE,
            "evidence_path": "convin-activate/internal/service/campaign.go", "decision": decision(verdict)}


def test_release_discovery_adds_sheet_row_without_auto_queue(db, monkeypatch):
    original = seed(db, status="dismissed", notes="Preserve my notes")
    mock_release(monkeypatch, {"features": [discovered_item()]})
    assert marketing.discover_features(db)["count"] == 1
    assert marketing.discover_features(db)["count"] == 0
    assert db.query(MarketingCampaign).count() == 0
    feature = db.query(MarketingFeature).filter_by(name="Channel results").one()
    assert feature.status == "candidate" and feature.decision["verdict"] == "approve"
    assert feature.tag == "New" and feature.sheet_status == "Not started"
    assert feature.module == "Sense" and feature.summary
    assert feature.evidence[0]["sha"] == "a" * 40
    assert original.notes == "Preserve my notes" and original.status == "dismissed"

def test_release_failure_does_not_checkpoint_unverified_feature(db, monkeypatch):
    seed(db)
    item = discovered_item(); item["evidence_quote"] = "Invented evidence which is not in the diff."
    mock_release(monkeypatch, {"features": [item]})
    assert not marketing.discover_features(db)["ok"]
    assert db.query(MarketingScan).count() == 0
    assert db.query(MarketingCampaign).count() == 0
    monkeypatch.setattr(manager, "chat_json", lambda *a, **k: {"features": [discovered_item()]})
    assert marketing.discover_features(db)["count"] == 1


def test_discovery_rejects_unchanged_context_as_new_feature(db, monkeypatch):
    seed(db)
    mock_release(monkeypatch, {"features": [discovered_item()]})
    monkeypatch.setattr(manager, "release_batches", lambda r: [[{"path": "convin-activate/internal/service/campaign.go", "text": QUOTE, "added_lines": ["internal refactor only"]}]])
    assert marketing.discover_features(db)["ok"] is False
    assert db.query(MarketingCampaign).count() == 0


def test_no_release_history_never_falls_back_to_unreleased_index(db, monkeypatch):
    seed(db)
    monkeypatch.setattr("app.services.release_detect.detect_release_merges", lambda **kw: None)
    assert not marketing.discover_features(db)["ok"]
    assert db.query(MarketingScan).count() == 0


def test_pmm_decision_is_dynamic_and_evidence_bound():
    assert manager.validate_decision(decision(selected=("linkedin_carousel", "article")), QUOTE)["verdict"] == "approve"
    assert manager.validate_decision(decision("skip"), QUOTE)["assignments"] == []
    assert manager.validate_decision(decision("defer"), QUOTE)["missing_evidence"]
    bad = decision(); bad["assignments"].append(bad["assignments"][0])
    with pytest.raises(ValueError): manager.validate_decision(bad, QUOTE)
    bad = decision(); bad["evidence_quotes"] = ["Unsupported new capability in a made-up source"]
    with pytest.raises(ValueError): manager.validate_decision(bad, QUOTE)
    bad = decision(); bad["omitted_formats"] = {}
    with pytest.raises(ValueError): manager.validate_decision(bad, QUOTE)


def queued_campaign(db, verdict="approve", selected=("linkedin_post",)):
    feature = seed(db, status="candidate")
    feature.description = QUOTE
    db.commit()
    campaign = manager.queue_feature(db, feature, manager.validate_decision(decision(verdict, selected), QUOTE))
    db.commit()
    return campaign


@pytest.mark.parametrize("verdict,status", [("skip", "skipped"), ("defer", "deferred")])
def test_pmm_can_choose_no_production(db, tmp_path, monkeypatch, verdict, status):
    campaign = queued_campaign(db, verdict)
    monkeypatch.setattr(marketing, "CAMPAIGN_DIR", tmp_path)
    monkeypatch.setattr("app.services.marketing_content.write_format", lambda *a: pytest.fail("Unselected formats must never run"))
    monkeypatch.setattr(marketing, "upload_campaign", lambda *a: pytest.fail("No production to upload"))
    assert marketing.produce_campaign(db, campaign)["ok"]
    assert campaign.status == status
    assert (tmp_path / str(campaign.id) / "pmm-decision.json").is_file()


def test_failed_format_does_not_block_others_and_retry_is_resumable(db, tmp_path, monkeypatch):
    campaign = queued_campaign(db, selected=("linkedin_post", "article"))
    monkeypatch.setattr(marketing, "CAMPAIGN_DIR", tmp_path)
    writes, renders, uploads = [], [], []
    def write(brief, plan, assignment):
        writes.append(assignment["format"])
        return {"title": "Channel outcomes", "body": QUOTE}
    def render(key, content, folder, step):
        renders.append(key)
        if key == "linkedin_post" and renders.count(key) == 1:
            raise RuntimeError("Renderer disconnected")
        return [{"filename": f"{key}.md", "mime": "text/markdown", "channel": key}]
    monkeypatch.setattr("app.services.marketing_content.write_format", write)
    monkeypatch.setattr("app.services.marketing_content.render_format", render)
    monkeypatch.setattr(marketing, "upload_campaign", lambda db, c: uploads.append([a["filename"] for a in c.assets]))
    assert not marketing.produce_campaign(db, campaign)["ok"]
    assert "article.md" in uploads[0] and campaign.status == "partial"
    assert marketing.produce_campaign(db, campaign)["ok"]
    assert writes == ["linkedin_post", "article"]
    assert renders == ["linkedin_post", "article", "linkedin_post"]
    assert campaign.status == "completed"


def test_campaign_key_deduplicates_repeated_refresh_and_allows_edited_version(db):
    campaign = queued_campaign(db)
    feature = db.get(MarketingFeature, campaign.feature_id)
    assert manager.queue_feature(db, feature).id == campaign.id
    feature.revision += 1; db.commit()
    newer = manager.queue_feature(db, feature); db.commit()
    assert newer.id != campaign.id


def test_dismissed_feature_cancels_pending_production(db, tmp_path, monkeypatch):
    campaign = queued_campaign(db)
    db.get(MarketingFeature, campaign.feature_id).status = "dismissed"; db.commit()
    monkeypatch.setattr(marketing, "CAMPAIGN_DIR", tmp_path)
    assert marketing.produce_campaign(db, campaign)["ok"]
    assert campaign.status == "cancelled"


def test_unattended_refresh_does_not_auto_start_production(db, monkeypatch):
    monkeypatch.setattr(manager, "discover_released_features", lambda *a: {"ok": True, "count": 1})
    called = []
    monkeypatch.setattr(manager, "drain_queue", lambda *a: called.append("drain") or {"ok": True})
    monkeypatch.setattr(manager, "schedule_pending", lambda *a: called.append("dispatch") or SimpleNamespace(id=9))
    result = manager.refresh_marketing(db)
    assert result["production"]["ok"] and result["production_job_id"] is None
    result = manager.refresh_marketing(db, lambda *a: None)
    assert result["production_job_id"] is None
    assert called == []


def test_refresh_marketing_syncs_sheet_then_discovers_then_writes_back(db, monkeypatch):
    seed(db)
    order = []
    monkeypatch.setattr(marketing, "seed_mastersheet", lambda db: order.append("seed") or {"ok": True, "added": 0})
    monkeypatch.setattr("app.services.gsheets.pull_into", lambda db: order.append("pull") or {"ok": True, "added": 1, "updated": 0})
    monkeypatch.setattr(manager, "discover_released_features", lambda *a: order.append("discover") or {"ok": True, "count": 1, "error": ""})
    monkeypatch.setattr("app.services.gsheets.push_from", lambda db: order.append("push") or {"ok": True, "count": 2})
    result = manager.refresh_marketing(db)
    assert order == ["seed", "pull", "discover", "push"]
    assert result["ok"] and result["count"] == 1
    assert result["filtered"]["hidden"] == 0
    assert result["sheet_pull"]["added"] == 1 and result["sheet_push"]["count"] == 2
    assert result["production_job_id"] is None


def test_queue_resumes_interrupted_stages_only(db, tmp_path, monkeypatch):
    campaign = queued_campaign(db)
    campaign.status = "rendering"; db.commit()
    monkeypatch.setattr(marketing, "CAMPAIGN_DIR", tmp_path)
    def finish(db, row, step):
        row.status = "completed"; db.commit()
        return {"ok": True}
    monkeypatch.setattr(marketing, "produce_campaign", finish)
    assert manager.drain_queue(db)["ok"]
    assert campaign.status == "completed"
    assert manager.drain_queue(db)["campaigns"] == []


def test_manager_and_specialists_explicitly_use_opus():
    from app.clients.llm import model_for
    assert model_for("marketing_manager") == model_for("marketing_writer") == model_for("marketing_review") == "claude-opus-4-8"


def test_specialist_repairs_editorial_failures(monkeypatch):
    from app.services import marketing_content as content
    calls = []
    def model(surface, prompt, payload, **kw):
        calls.append(surface)
        if surface == "marketing_writer":
            return {"title": "See campaign outcomes by channel", "body": QUALITY_POST}
        if calls.count("marketing_review") == 1:
            return {"passed": False, "issues": ["Clarify the buyer problem"], "scores": {}}
        return quality_review(payload["content"])
    monkeypatch.setattr(content, "chat_json", model)
    result = content.write_format({"description": QUOTE}, decision(), decision()["assignments"][0])
    assert result["review"]["passed"]
    assert calls == ["marketing_writer", "marketing_review", "marketing_writer", "marketing_review"]


def test_manual_sheet_rows_are_not_auto_queued_on_refresh(db, monkeypatch):
    feature = seed(db); feature.description = QUOTE; db.commit()
    monkeypatch.setattr(manager, "discover_released_features", lambda *a: {"ok": True, "count": 0})
    monkeypatch.setattr(manager, "schedule_pending", lambda db: SimpleNamespace(id=7))
    manager.refresh_marketing(db, lambda *a: None)
    manager.refresh_marketing(db, lambda *a: None)
    assert db.query(MarketingCampaign).count() == 0


def test_buyer_sellable_keeps_operator_tools_and_drops_engineer_work():
    assert marketing.buyer_sellable(
        "Phone Number rotation",
        summary="Rotate outbound DIDs so campaigns do not burn a single number.",
        description="Campaign operators spread outbound traffic across a pool of numbers.",
        audience="Collections and sales campaign operators",
    )[0]
    assert marketing.buyer_sellable(
        "Agent Testing", summary="Ship with confidence.",
        description="Try your agent on a real call before customers hear it.",
        audience="All 4 verticals",
    )[0]
    assert marketing.buyer_sellable(
        "AI Agent Builder", summary="Idea to live agent, no engineering.",
        description="Build a launch-ready voice agent without writing code.",
        audience="All 4 verticals", benefit="Idea to live agent, no engineering",
    )[0]
    assert not marketing.buyer_sellable(
        "Developer API", description="Engineering teams add leads programmatically.",
        audience="E-commerce, BFSI",
    )[0]
    assert not marketing.buyer_sellable(
        "Gemini Explicit Caching", description="Cache Gemini prompts for cheaper completions.",
        audience="Internal engineering",
    )[0]
    assert not marketing.buyer_sellable(
        "SSO & Tenancy Management", description="Employees log in with company SSO.",
        audience="All 4 verticals",
    )[0]
    assert not marketing.buyer_sellable(
        "Roles & Permissions", description="Control who can launch campaigns.",
        audience="All 4 verticals",
    )[0]
    assert marketing.buyer_sellable(
        "Warm Transfer Agent Whisper",
        summary="Coach the human before they join the live call.",
        description="Operators whisper context to the receiving agent during warm transfer.",
        audience="Contact-center and CX operations leaders",
        module="Released",
    )[0]
    assert marketing.buyer_sellable(
        "Campaign Scheduling",
        summary="Hold a campaign until Monday 10:00.",
        description="Ops schedules a collections blast for the next working window.",
        audience="BFSI, Collections",
    )[0]
    assert marketing.buyer_sellable(
        "Phone Number Round-Robin",
        summary="Rotate outbound DIDs so campaigns do not burn a single number.",
        description="Campaign operators spread outbound traffic across a pool of numbers.",
        audience="Collections and sales campaign operators",
    )[0]


def test_hide_unsellable_dismisses_without_deleting(db):
    keep = seed(db)
    drop = MarketingFeature(
        name="Developer API", identity="developer api",
        description="Engineering teams add, update, archive, and fetch leads programmatically.",
        audience="E-commerce, BFSI", status="draft", source="mastersheet",
    )
    db.add(drop)
    db.commit()
    result = marketing.hide_unsellable_features(db)
    assert result["hidden"] == 1 and result["names"] == ["Developer API"]
    assert db.get(MarketingFeature, drop.id).status == "dismissed"
    assert db.get(MarketingFeature, drop.id).tag == "Not selected"
    assert db.get(MarketingFeature, keep.id).status == "draft"
    assert db.query(MarketingFeature).count() == 2


def test_discovery_skips_engineer_facing_even_if_pmm_approves(db, monkeypatch):
    seed(db)
    item = discovered_item()
    item["name"] = "Gemini Explicit Caching"
    item["audience"] = "Internal engineering"
    item["decision"] = {**item["decision"], "audience": "Internal engineering"}
    mock_release(monkeypatch, {"features": [item]})
    result = marketing.discover_features(db)
    assert result["ok"] and result["count"] == 0 and result["rejected"] == 1
    assert db.query(MarketingFeature).filter_by(name="Gemini Explicit Caching").first() is None


def test_discovery_keeps_phone_number_rotation(db, monkeypatch):
    seed(db)
    item = discovered_item()
    item["name"] = "Phone Number rotation"
    item["summary"] = "Rotate outbound DIDs across campaigns."
    item["audience"] = "Campaign operators"
    item["decision"] = {**item["decision"], "audience": "Campaign operators"}
    mock_release(monkeypatch, {"features": [item]})
    assert marketing.discover_features(db)["count"] == 1
    row = db.query(MarketingFeature).filter_by(name="Phone Number rotation").one()
    assert row.status == "candidate" and row.decision["verdict"] == "approve"


def test_mastersheet_seed_imports_features(db, tmp_path):
    csv_path = tmp_path / "mastersheet.csv"
    csv_path.write_text(
        "Module,Feature,Priority,Hook,Use Case,Who To Market To,Start Date,End Date,Status,Script,Video\n"
        "AI Agents,Agent Testing,P1,Ship with confidence,Try your agent on a real call before customers.,All verticals,10-09-26,17-09-26,In Progress,,\n"
        "Platform,PII Masking,P1,Privacy built in,Sensitive data is masked across views.,BFSI,,,,,\n"
        "Integrations,Developer API,P3,Build exactly what your ops need,Engineering teams fetch leads programmatically.,E-commerce,,,,,\n",
        encoding="utf-8",
    )
    first = marketing.seed_mastersheet(db, csv_path)
    second = marketing.seed_mastersheet(db, csv_path)
    assert first["added"] == 2 and second["added"] == 0
    assert db.query(MarketingFeature).filter_by(name="Developer API").first() is None
    rows = db.query(MarketingFeature).order_by(MarketingFeature.name).all()
    assert rows[0].tag == "New" and rows[0].module == "AI Agents"
    assert rows[0].sheet_status == "In Progress"
    assert "real call" in rows[0].description
    assert rows[0].summary


def test_api_accepts_draft_for_pmm_judgment_without_human_ready(client, db, monkeypatch):
    from app.api.routers import marketing as routes
    feature = seed(db, status="draft"); feature.description = QUOTE; db.commit()
    monkeypatch.setattr(routes, "enqueue", lambda *a: {"id": 9, "kind": "marketing", "status": "queued"})
    monkeypatch.setattr(routes, "job_out", lambda row: row)
    assert client.post("/marketing/generate", json={"feature_ids": [feature.id]}).status_code == 202
    assert client.post("/marketing/generate", json={"feature_ids": [feature.id]}).status_code == 202
    assert db.query(MarketingCampaign).count() == 1
    assert db.get(MarketingFeature, feature.id).tag == "In pipeline"


def test_generate_queues_a_single_requested_content_type(client, db, monkeypatch):
    from app.api.routers import marketing as routes
    from app.services.marketing_status import content_inventory
    feature = seed(db, status="draft")
    feature.description = QUOTE
    db.commit()
    monkeypatch.setattr(routes, "enqueue", lambda *a: {"id": 11, "kind": "marketing", "status": "queued"})
    monkeypatch.setattr(routes, "job_out", lambda row: row)
    assert client.post("/marketing/generate", json={"feature_ids": [feature.id], "formats": ["linkedin_carousel"]}).status_code == 202
    campaign = db.query(MarketingCampaign).one()
    assert campaign.run_key == f"pmm-format-v1:{feature.id}:{feature.revision}:linkedin_carousel"
    assert campaign.content["requested_formats"] == ["linkedin_carousel"]
    assert client.post("/marketing/generate", json={"feature_ids": [feature.id], "formats": ["release_notes"]}).status_code == 202
    assert db.query(MarketingCampaign).count() == 2
    assert client.post("/marketing/generate", json={"feature_ids": [feature.id], "formats": ["not_a_format"]}).status_code == 422
    inventory = content_inventory(feature, db.query(MarketingCampaign).all())
    assert inventory["linkedin_carousel"]["status"] in {"queued", "planning", "generating", "rendering", "uploading"}
    assert inventory["linkedin_carousel"]["campaign_id"] == campaign.id
    assert inventory["article"]["status"] == "not_started"


def test_release_batches_pin_source_and_exclude_secrets(monkeypatch):
    calls = []
    def git(root, *args, **kwargs):
        calls.append(args)
        if "--name-only" in args:
            return SimpleNamespace(returncode=0, stdout="convin-activate/internal/service/campaign.go\nconvin-activate/.env\nother-product/README.md\n")
        return SimpleNamespace(returncode=0, stdout="+++ b/convin-activate/internal/service/campaign.go\n unchanged context\n+" + QUOTE + "\n-deleted capability\n")
    monkeypatch.setattr("app.services.codebase._git", git)
    batches = list(manager.release_batches({"sha": "a" * 40, "base_sha": "b" * 40}))
    assert len(calls) == 2
    assert "a" * 40 in calls[1] and "b" * 40 in calls[1]
    assert batches[0][0]["added_lines"] == [QUOTE]
    assert "deleted capability" not in batches[0][0]["text"]


def test_refresh_fetches_branches_before_pmm_and_preserves_other_steps(db, monkeypatch, tmp_path):
    from app.services import refresh
    calls = []
    monkeypatch.setattr(refresh, "run_pipeline", lambda *a, **k: SimpleNamespace(status="completed", error="", jira_count=1, cliq_count=1))
    monkeypatch.setattr(refresh, "sync_roadmap_statuses", lambda *a, **k: None)
    monkeypatch.setattr(refresh, "codebase_root", lambda: tmp_path)
    monkeypatch.setattr(refresh, "latest_snapshot", lambda db: None)
    monkeypatch.setattr(refresh, "update_index", lambda *a, **k: calls.append("index") or {})
    monkeypatch.setattr(refresh, "list_recent_branches", lambda **k: calls.append("fetch") or {"branches": []})
    monkeypatch.setattr("app.services.release_worker.detect_and_enqueue", lambda *a, **k: calls.append("releases") or [])
    monkeypatch.setattr(manager, "refresh_marketing", lambda *a, **k: calls.append("marketing") or {"ok": True})
    result = refresh.refresh_platform(db, lambda *a: None)
    assert result["ok"] and result["steps"]["marketing"]["ok"]
    assert calls == ["index", "fetch", "releases", "marketing"]


def test_layout_failure_requests_revised_copy_on_retry(db, tmp_path, monkeypatch):
    campaign = queued_campaign(db)
    monkeypatch.setattr(marketing, "CAMPAIGN_DIR", tmp_path)
    calls = []
    def write(*args, **kwargs):
        calls.append(kwargs)
        return {"title": "Feature report", "body": QUOTE}
    attempts = []
    def render(*args):
        attempts.append(1)
        if len(attempts) == 1: raise ValueError("Headline exceeds its safe area")
        return []
    monkeypatch.setattr("app.services.marketing_content.write_format", write)
    monkeypatch.setattr("app.services.marketing_content.render_format", render)
    monkeypatch.setattr(marketing, "upload_campaign", lambda *a: None)
    assert marketing.produce_campaign(db, campaign)["ok"]
    assert len(attempts) == 2
    assert calls[1]["repair"] == "Headline exceeds its safe area"


def visual_brief(**overrides):
    return {
        "title": "Read a campaign channel by channel",
        "dek": "See which channel deserves a closer look before the campaign review starts.",
        "stats": [{"value": "1 view", "label": "Every channel in the campaign"}],
        "blocks": [
            {"kind": "why", "heading": "Why you need this",
             "risk": "One campaign total hides the channel that actually needs attention this week.",
             "items": [{"lead": "A specific start", "text": "Open the breakdown and see which channel differs from the rest."},
                       {"lead": "Fewer blind guesses", "text": "Ask about the channel that moved, not about the campaign total."}]},
            {"kind": "flow", "heading": "How the review runs",
             "items": [{"lead": "Open the campaign", "text": "Pick the campaign you are reviewing with the team."},
                       {"lead": "Read by channel", "text": "Compare what each channel produced in the same window."},
                       {"lead": "Carry one question", "text": "Take the difference you found into the review itself."}]},
            {"kind": "panel", "heading": "What to know first",
             "items": [{"lead": "Descriptive, not causal", "text": "A channel difference is a question to explore, never proof."},
                       {"lead": "Setup still matters", "text": "Audience and timing can explain part of the gap you see."}]},
        ],
        "cta": "Open a recent campaign and read it channel by channel.",
        **overrides}


def visual_carousel(**slide_overrides):
    slides = [
        {"layout": "hook", "visual": "statement", "headline": "One campaign total hides the answer",
         "body": "The number tells you how much happened.", "points": [], "evidence": QUOTE},
        {"layout": "problem", "visual": "contrast", "headline": "Totals against channels",
         "body": "Same campaign, two very different readings.", "points": ["One blended total", "Four channel results"], "evidence": QUOTE},
        {"layout": "steps", "visual": "steps", "headline": "How the review runs",
         "body": "Three moves before the meeting.", "points": ["Open the campaign", "Read by channel", "Carry one question"], "evidence": QUOTE},
        {"layout": "proof", "visual": "spotlight", "headline": "Sense breaks results out by channel",
         "body": "The breakdown sits with the campaign.", "points": ["Per channel results"], "evidence": QUOTE},
        {"layout": "benefit", "visual": "spotlight", "headline": "Reviews start on the difference",
         "body": "Discussion opens where results diverge.", "points": ["A focused question"], "evidence": QUOTE},
        {"layout": "cta", "visual": "statement", "headline": "Read your last campaign again",
         "body": "Start with the channel that moved.", "points": [], "evidence": QUOTE},
    ]
    if slide_overrides:
        slides[1] = {**slides[1], **slide_overrides}
    return {"title": "Read a campaign channel by channel", "body": QUALITY_POST, "slides": slides}


def test_brief_is_a_visual_pack_not_a_prose_document():
    from app.services.marketing_content import validate_format
    value = validate_format("feature_brief", visual_brief())
    assert "## Why you need this" in value["body"] and "**1 view**" in value["body"]
    assert 110 <= len(value["body"].split()) <= 250
    cards = {"kind": "cards", "heading": "Where it helps", "items": visual_brief()["blocks"][0]["items"]}
    with pytest.raises(ValueError, match="three different devices"):
        validate_format("feature_brief", visual_brief(blocks=[cards, {**cards, "heading": "Who it helps"}, {**cards, "heading": "When it helps"}]))
    prose = visual_brief()["blocks"]
    prose[2] = {**prose[2], "items": [{"lead": "Descriptive, not causal", "text": "A channel difference is a question to explore. " * 4}, *prose[2]["items"][1:]]}
    with pytest.raises(ValueError, match="scannable|at most"):
        validate_format("feature_brief", visual_brief(blocks=prose))


def test_brief_needs_a_structural_device_and_honest_stats():
    from app.services.marketing_content import validate_format
    blocks = visual_brief()["blocks"]
    flat = [blocks[0], blocks[2], {"kind": "cards", "heading": "Where it helps", "items": blocks[2]["items"]}]
    with pytest.raises(ValueError, match="structural device"):
        validate_format("feature_brief", visual_brief(blocks=flat))
    with pytest.raises(ValueError, match="different point"):
        validate_format("feature_brief", visual_brief(stats=[{"value": "4", "label": "Channels in one view"}, {"value": "4", "label": "Stages in the funnel"}]))


def test_carousel_slides_carry_a_visual_not_a_paragraph():
    from app.services.marketing_content import validate_format
    value = validate_format("linkedin_carousel", visual_carousel())
    assert [slide["visual"] for slide in value["slides"]][:3] == ["statement", "contrast", "steps"]
    with pytest.raises(ValueError, match="supporting line|at most"):
        validate_format("linkedin_carousel", visual_carousel(body="A campaign total tells you how much happened. " * 3))
    with pytest.raises(ValueError, match="short labels"):
        validate_format("linkedin_carousel", visual_carousel(points=["A blended total tells you how much happened overall", "Channels"]))
    with pytest.raises(ValueError, match="supported figure"):
        validate_format("linkedin_carousel", visual_carousel(visual="stat", points=["One blended total", "Channel results"]))


def test_carousel_rejects_one_treatment_repeated():
    from app.services.marketing_content import validate_format
    content = visual_carousel()
    content["slides"] = [{**slide, "visual": "statement", "points": []} if slide["layout"] not in {"steps", "problem"}
                         else {**slide, "visual": "steps"} for slide in content["slides"]]
    with pytest.raises(ValueError, match="three distinct visual treatments"):
        validate_format("linkedin_carousel", content)


QUALITY_POST = """A campaign total tells you how much happened. It does not tell you which channel deserves a closer look.

Sense lets you view a breakdown of campaign results by channel. For a sales operations manager preparing a campaign review, that gives the discussion a specific starting point: compare the channel results before deciding which questions to investigate.

For example, imagine reviewing a campaign that uses more than one channel. Start with the breakdown, note where the results differ, and bring those differences to your team. Treat that as a question to explore, not proof that one channel caused a better outcome. Audience, timing and campaign setup may also matter.

The useful shift is from discussing one overall result to asking a more focused question about each channel. What would you investigate first in your next campaign review?

#SalesOperations #CampaignReporting"""


def quality_review(value):
    return {"passed": True, "issues": [], "scores": dict.fromkeys(
        ("factuality", "specificity", "channel_fit", "narrative", "readability"), 5),
        "feature_specificity": "The copy explains a channel breakdown and how a sales operations manager would use that breakdown to structure a review.",
        "audience_value": "Sales operations can ask focused questions without claiming causal attribution from descriptive reporting.",
        "distinct_from_other_formats": "This post opens a focused conversation; there are no other supplied formats with which it overlaps.",
        "claims": [{"location": "body", "content_quote": "Sense lets you view a breakdown of campaign results by channel.",
                    "evidence_quote": QUOTE, "explanation": "The supplied description explicitly supports viewing campaign results broken down by channel."}]}


def test_discovery_repairs_bad_evidence_in_same_window(db, monkeypatch):
    seed(db)
    good = discovered_item()
    bad = {**good, "evidence_quote": "This is a fabricated quote that must never pass."}
    mock_release(monkeypatch, {})
    calls = []
    def answer(surface, prompt, payload, **kwargs):
        calls.append(payload)
        return {"features": [bad if len(calls) == 1 else good]}
    monkeypatch.setattr(manager, "chat_json", answer)
    assert manager.discover_released_features(db)["ok"]
    assert len(calls) == 2 and "verifiable" in calls[1]["repair"]
    assert db.query(MarketingFeature).count() == 2


@pytest.mark.parametrize("verdict", ["skip", "defer"])
def test_rejected_discoveries_are_audited_not_added(db, monkeypatch, verdict):
    seed(db)
    mock_release(monkeypatch, {"features": [discovered_item(verdict)]})
    result = manager.discover_released_features(db)
    assert result["ok"] and result["count"] == 0 and result["rejected"] == 1
    assert db.query(MarketingFeature).count() == 1
    assert list((marketing.CAMPAIGN_DIR / "discovery").glob("*.json"))


def test_bad_window_does_not_block_later_windows(db, monkeypatch):
    seed(db)
    mock_release(monkeypatch, {})
    monkeypatch.setattr(manager, "release_batches", lambda release: [[{"bad": True}], [{"bad": False}]])
    def assess(release, batch, existing):
        if batch[0]["bad"]: raise ValueError("Bad evidence")
        return []
    monkeypatch.setattr(manager, "assess_release_batch", assess)
    result = manager.discover_released_features(db)
    assert not result["ok"] and result["scanned"] == 1 and result["failed_windows"] == 1
    assert db.query(MarketingScan).count() == 1


@pytest.mark.parametrize("path", ["convin-activate/docs/plan.md", "convin-activate/internal/service/x_test.go",
    "convin-activate/static/src/a.test.tsx", "convin-activate/secrets.go", "convin-activate/scripts/a.py", "another/product.go"])
def test_non_product_source_is_excluded(path):
    assert not manager.marketing_source(path)


def test_legacy_rejected_rows_remain_available_but_not_new(db):
    row = seed(db, decision=decision("skip"), source="codebase", tag="New")
    assert marketing.feature_out(row)["tag"] == "Not selected"
    assert row.tag == "New"  # Historical data remains unchanged.


def test_editorial_scores_do_not_replace_evidence_or_full_coverage():
    from app.services.marketing_content import validate_review
    value = {"title": "Campaign results", "body": QUALITY_POST}
    good = quality_review(value)
    assert validate_review(good, value, {"description": QUOTE})["passed"]
    bad = {**good, "claims": [{**good["claims"][0], "evidence_quote": "Invented supporting evidence that is not in the source."}]}
    with pytest.raises(ValueError, match="supporting source"): validate_review(bad, value, {"description": QUOTE})
    bad = {**good, "issues": ["An unsupported promise remains."]}
    with pytest.raises(ValueError, match="unsupported promise"): validate_review(bad, value, {"description": QUOTE})
    with pytest.raises(ValueError, match="omitted content units"):
        validate_review(good, {**value, "slides": [{"headline": "A new claim", "body": "This also needs an explicit review."}]}, {"description": QUOTE})


def test_editor_cannot_use_generated_positioning_as_proof():
    from app.services.marketing_content import validate_review
    value = {"title": "Campaign results", "body": QUALITY_POST}
    with pytest.raises(ValueError, match="supporting source"):
        validate_review(quality_review(value), value, {"source": "codebase", "description": QUOTE, "benefit": QUOTE})


def test_refresh_reports_marketing_failure(db, monkeypatch, tmp_path):
    from app.services import refresh
    monkeypatch.setattr(refresh, "run_pipeline", lambda *a, **k: SimpleNamespace(status="completed", error="", jira_count=1, cliq_count=1))
    monkeypatch.setattr(refresh, "sync_roadmap_statuses", lambda *a, **k: None)
    monkeypatch.setattr(refresh, "codebase_root", lambda: tmp_path)
    monkeypatch.setattr(refresh, "latest_snapshot", lambda db: None)
    monkeypatch.setattr(refresh, "update_index", lambda *a, **k: {})
    monkeypatch.setattr(refresh, "list_recent_branches", lambda **k: {"branches": []})
    monkeypatch.setattr("app.services.release_worker.detect_and_enqueue", lambda *a, **k: [])
    monkeypatch.setattr(manager, "refresh_marketing", lambda *a, **k: {"ok": False, "error": "Evidence needs repair"})
    result = refresh.refresh_platform(db)
    assert not result["ok"] and "marketing: Evidence needs repair" in result["error"]
    assert result["steps"]["jira"]["ok"]


def test_workspace_lists_campaigns_without_full_copy(client, db):
    feature = seed(db)
    db.add(MarketingCampaign(
        feature_id=feature.id,
        feature_revision=1,
        feature_snapshot={"name": feature.name, "id": feature.id},
        status="completed",
        content={"version": 2, "formats": {"article": {"status": "completed", "content": {"title": "Long", "body": "x" * 5000}}}},
        assets=[{"filename": "article.md", "channel": "article"}],
        error="",
    ))
    db.commit()
    payload = client.get("/marketing").json()
    campaign = payload["campaigns"][0]
    assert campaign["feature_snapshot"]["name"] == "AI campaigns"
    assert campaign["content"] == {"version": 2}
    assert "formats" not in campaign["content"]
    detail = client.get(f"/marketing/campaigns/{campaign['id']}").json()
    assert detail["content"]["formats"]["article"]["content"]["body"].startswith("x")

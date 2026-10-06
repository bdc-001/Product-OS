from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import ReleaseJob
from app.storage import from_stored

TOOL_MODULE = "src/components/analytics/ToolExecutionStatusSection.jsx"


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def _doc():
    return {
        "title": "Tool Execution Status",
        "sections": [
            {"heading": "Functional Overview", "blocks": [{"type": "para", "text": "You can see tool outcomes."}, {"type": "bullets", "items": ["x"]}]},
            {"heading": "How to Use", "blocks": [{"type": "h3", "text": "8.1 Open"}, {"type": "numbered", "items": ["Open Analytics."]}, {"type": "image", "ref": "8.1"}]},
            {"heading": "Outcome Analysis", "blocks": [{"type": "table", "headers": ["Output"], "rows": [["Success Rate"]]}, {"type": "image", "ref": "table"}, {"type": "image", "ref": "table"}]},
        ],
    }


def test_place_screenshots_keeps_known_refs_once_and_places_the_rest():
    from app.services.gdocs import place_screenshots

    catalog = [
        {"id": "table", "section": "Outcome Analysis"},
        {"id": "filters", "section": "How to Use"},
        {"id": "cards", "section": "How to Use"},
        {"id": "orphan", "section": "Configuration Options"},
    ]
    out = place_screenshots(_doc(), catalog)
    by = {s["heading"]: s["blocks"] for s in out["sections"]}
    refs = [b["ref"] for s in out["sections"] for b in s["blocks"] if b.get("type") == "image"]
    assert sorted(refs) == ["cards", "filters", "orphan", "table"]
    assert "8.1" not in refs
    how = [b.get("type") + ":" + (b.get("ref") or "") for b in by["How to Use"]]
    assert how == ["h3:", "numbered:", "image:filters", "image:cards"]
    assert by["Functional Overview"][1] == {"type": "image", "ref": "orphan"}
    assert [b.get("ref") for b in by["Outcome Analysis"] if b.get("type") == "image"] == ["table"]


def test_place_screenshots_with_empty_catalog_strips_placeholders():
    from app.services.gdocs import place_screenshots

    out = place_screenshots(_doc(), [])
    assert not [b for s in out["sections"] for b in s["blocks"] if b.get("type") == "image"]


def test_image_keeps_aspect_ratio_and_writes_caption():
    from app.services.gdocs import DOCS_THEME, DocBuilder, _write_blocks, image_size_pt, resolve_screenshot

    entry = {"uri": "https://drive.google.com/uc?export=view&id=a", "width": 1100, "height": 510, "caption": "Cards and table."}
    width, height = image_size_pt(entry, 420.0)
    assert width == 420.0
    assert height == pytest.approx(420 * 510 / 1100, abs=0.1)
    assert image_size_pt({"uri": "x", "width": 320, "height": 200}, 420.0) == (240.0, 150.0)
    assert resolve_screenshot({"table": entry}, "table") == entry["uri"]
    assert resolve_screenshot({"8.1": "https://u"}, "8.1.png") == "https://u"

    builder = DocBuilder("doc")
    _write_blocks(builder, [{"type": "image", "ref": "table"}], {"table": entry}, DOCS_THEME)
    image = next(r["insertInlineImage"] for r in builder.requests if "insertInlineImage" in r)
    assert image["objectSize"]["height"]["magnitude"] == pytest.approx(height, abs=0.1)
    texts = [r["insertText"]["text"] for r in builder.requests if "insertText" in r]
    assert "Cards and table.\n" in texts
    italic = [r["updateTextStyle"]["textStyle"] for r in builder.requests if "updateTextStyle" in r]
    assert any(style.get("italic") for style in italic)


def test_generate_doc_json_places_captures_the_model_skipped(monkeypatch):
    from app.services import gdocs

    seen = {}

    def fake_chat_json(surface, system, payload, **kwargs):
        seen.update(payload)
        return {"title": "Tool Execution Status", "sections": [{"heading": "Outcome Analysis", "blocks": [{"type": "para", "text": "Read the table."}]}]}

    monkeypatch.setattr(gdocs, "chat_json", fake_chat_json)
    catalog = [{"id": "table", "feature": "Tool Execution Status", "section": "Outcome Analysis", "caption": "Table.", "shows": "rows"}]
    doc = gdocs.generate_doc_json(title="t", features_in_short="Tool Execution Status — per-tool outcomes", screenshots=catalog)
    assert seen["screenshots"][0]["ref"] == "table"
    assert seen["screenshot_filenames"] == ["table"]
    outcome = next(s for s in doc["sections"] if s["heading"] == "Outcome Analysis")
    assert {"type": "image", "ref": "table"} in outcome["blocks"]
    assert not [b for s in doc["sections"] for b in s["blocks"] if b.get("type") == "image" and b["ref"] != "table"]


def test_mock_matching_and_component_filter():
    from app.services.release_shots import _is_component_file, _mock_for

    mocks = [
        {"method": "POST", "path": "/{tenant}/analytics/multi-campaign/tool-execution-status", "status": 200, "json": {"tools": []}},
        {"method": "GET", "path": "/*/campaigns", "status": 200, "json": []},
    ]
    assert _mock_for(mocks, "POST", "/v1/acme-demo/analytics/multi-campaign/tool-execution-status") is mocks[0]
    assert _mock_for(mocks, "GET", "/v1/acme-demo/analytics/multi-campaign/tool-execution-status") is None
    assert _mock_for(mocks, "GET", "/v1/acme-demo/campaigns") is mocks[1]
    assert _is_component_file("billing-service/static/src/components/analytics/ToolExecutionStatusSection.jsx")
    assert not _is_component_file("billing-service/static/src/features/x/__tests__/Thing.test.tsx")
    assert not _is_component_file("billing-service/static/src/styles/app.css")


def test_clean_shot_rejects_paths_outside_src(tmp_path):
    from app.services.release_shots import clean_shot

    (tmp_path / "src" / "components").mkdir(parents=True)
    (tmp_path / "src" / "contexts").mkdir(parents=True)
    (tmp_path / "src" / "components" / "Table.jsx").write_text("export default () => null")
    (tmp_path / "src" / "contexts" / "AuthContext.jsx").write_text("export const AuthProvider = () => null")
    base = {"id": "Tool Table!", "feature": "Tool Execution Status", "width": 9000, "section": "Nope"}
    assert clean_shot({**base, "module": "../secrets.js"}, tmp_path, 0, []) is None
    assert clean_shot({**base, "module": "src/components/Missing.jsx"}, tmp_path, 0, []) is None
    shot = clean_shot(
        {
            **base,
            "module": "src/components/Table.jsx",
            "providers": [{"module": "src/contexts/AuthContext.jsx", "export": "AuthProvider"}, {"module": "src/components/Table.jsx"}],
            "mocks": [{"path": "/{tenant}/x", "json": {"a": 1}}],
            "noop_props": ["onClose", "window.alert", "children"],
        },
        tmp_path,
        0,
        ["Tool Execution Status"],
    )
    assert shot["id"] == "tool-table"
    assert shot["noop_props"] == ["onClose"]
    assert shot["module"] == "/src/components/Table.jsx"
    assert shot["width"] == 1440
    assert shot["section"] == "Functional Overview"
    assert shot["providers"] == [{"module": "/src/contexts/AuthContext.jsx", "export": "AuthProvider"}]
    assert shot["mocks"][0]["method"] == "GET"
    assert shot["route"] == "/tenant/acme-demo"
    assert shot["route_path"] == "/tenant/:tenantId/*"


def test_clean_route_keeps_tenant_pages_and_drops_escapes():
    from app.services.release_shots import _clean_route

    page = _clean_route({"route": "/tenant/acme-demo/campaigns", "route_path": "/tenant/:tenantId/campaigns"})
    assert page == {"route": "/tenant/acme-demo/campaigns", "route_path": "/tenant/:tenantId/campaigns"}
    assert _clean_route({"route": "https://evil.test/", "route_path": "/admin"}) == {
        "route": "/tenant/acme-demo",
        "route_path": "/tenant/:tenantId/*",
    }
    assert _clean_route({"route": "/tenant/acme-demo/../x"})["route"] == "/tenant/acme-demo"


def test_local_pdf_draws_images_in_their_section(tmp_path):
    import fitz

    from app.services.pdf_notes import write_release_pdf

    png = tmp_path / "table.png"
    Image.new("RGB", (1100, 510), (26, 98, 242)).save(png)
    body = "## Functional Overview\nYou can see outcomes.\n## Outcome Analysis\nRead the table.\n## FAQs\nQ: Why?"
    dest = write_release_pdf(
        title="Tool Execution Status",
        branch="release/2026-09-26",
        sha="abc",
        body=body,
        dest=tmp_path / "notes.pdf",
        images=[{"path": str(png), "section": "Outcome Analysis", "caption": "Cards and table.", "width": 1100, "height": 510}],
    )
    with fitz.open(dest) as document:
        assert sum(len(page.get_images()) for page in document) >= 1
        text = "".join(page.get_text() for page in document)
    assert text.index("Cards and table.") < text.index("Q: Why?")


def test_worker_captures_then_places_shots(tmp_path, monkeypatch):
    from app.services import release_shots, release_worker

    png = release_shots.SHOTS_ROOT / "test-job" / "table.png"
    png.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (400, 200), (26, 98, 242)).save(png)
    from app.storage import to_stored

    rel = to_stored(png)
    assert rel == "release_shots/test-job/table.png"
    capture = {
        "status": "ok",
        "shots": [
            {"id": "table", "feature": "Tool Execution Status", "section": "Outcome Analysis", "caption": "Table.", "shows": "rows", "status": "ok", "path": rel, "width": 200, "height": 100, "sha": "s1"},
            {"id": "broken", "feature": "Tool Execution Status", "section": "How to Use", "caption": "Filters.", "status": "failed", "error": "Fixture data did not render"},
        ],
    }
    calls = {}
    monkeypatch.setattr(
        release_worker,
        "extract_features",
        lambda *a, **k: {
            "features": [
                {"name": "Tool Execution Status", "what": "per-tool outcomes", "confidence": "HIGH"},
                {"name": "Retry tweak", "what": "internal", "confidence": "LOW"},
            ]
        },
    )

    def fake_capture(**kwargs):
        calls["features"] = [f["name"] for f in kwargs["features"]]
        return capture

    monkeypatch.setattr(release_worker, "capture_release_shots", fake_capture)
    monkeypatch.setattr(release_worker, "generate_pack", lambda db, **k: {"id": 1, "title": "Release", "release_notes": "Read it."})
    monkeypatch.setattr(release_worker, "feature_evidence", lambda base, head, feature: {"commits": [{"subject": "feat"}], "files": []})

    def fake_note(feature, evidence, shots):
        from app.services.release_note import clean_note

        calls["shots"] = [s["id"] for s in shots]
        raw = {
            "title": feature["name"],
            "dek": "Tool Execution Status shows how each tool call ended.",
            "sections": [
                {"heading": "Navigation", "items": [{"text": "Open Analytics, then Tool Execution Status."}]},
                {"heading": "📌 Details Table", "items": [{"lead": "Rows", "text": "One row per tool."}], "screenshot": {"id": "table", "caption": "The table."}},
            ],
            "cta": "This feature is an effort towards faster triage.",
        }
        return clean_note(raw, feature, shots), ""

    from app.services import release_note

    monkeypatch.setattr(release_note, "support_email", lambda: "support@example.com")
    monkeypatch.setattr(release_worker, "generate_note", fake_note)
    monkeypatch.setattr(release_worker, "drive_configured", lambda: False)
    db = _db()
    job = ReleaseJob(branch="release/2026-09-26", sha="h", base_sha="b", status="extracting")
    db.add(job)
    db.commit()
    db.refresh(job)
    try:
        release_worker._stage_extract(db, job)
        assert calls["features"] == ["Tool Execution Status"]
        assert job.status == "writing"
        release_worker._stage_write(db, job)
        assert calls["shots"] == ["table"]
        out = release_worker.job_out(job)
        assert out["status"] == "generated"
        assert [n["feature"] for n in out["notes"]] == ["Tool Execution Status"]
        assert out["notes"][0]["sections"] == ["📌 Navigation", "📌 Details Table"]
        assert "support@example.com" in job.extraction["notes"][0]["content"]["cta"]
        shots = {s["id"]: s for s in out["shots"]}
        assert shots["table"]["in_doc"] is True
        assert shots["table"]["url"] == f"/api/comms/release-jobs/{job.id}/shots/table"
        assert shots["broken"]["url"] == ""
        assert shots["broken"]["error"]

        release_worker._stage_pdf(db, job)
        note = job.extraction["notes"][0]
        assert not Path(note["pdf_path"]).is_absolute() and from_stored(note["pdf_path"]).is_file()
        [image] = note["images"]
        assert (image["kind"], image["section"]) == ("shot", 1)
        with Image.open(from_stored(image["path"])) as framed:
            assert framed.size == (400 + 2 * 26, 200 + 2 * 26)
            assert framed.getpixel((0, 0)) == (17, 85, 204)
            assert framed.getpixel((3, 3)) == (255, 255, 255)
        assert release_worker.job_out(job)["notes"][0]["pdf_url"].endswith("/pdf?note=0")

        uploads = []
        monkeypatch.setattr(release_worker, "upload_screenshot", lambda path, branch: (uploads.append(path) or "f1", "https://drive/f1"))
        images = release_worker._upload_images(job.branch, note["images"])
        assert images[0]["uri"] == "https://drive/f1"
        release_worker._upload_images(job.branch, images)
        assert len(uploads) == 1

        release_worker._stage_doc(db, job)
        assert job.status == "pending_review"
        monkeypatch.setattr(release_worker, "upload_pdf", lambda *a, **k: {"file_id": "dryrun", "link": "", "dry_run": True})
        published = release_worker.approve_and_publish(db, job)
        assert published["status"] == "uploaded"
        assert published["error_detail"].startswith("dry-run")
    finally:
        png.unlink(missing_ok=True)


def test_harness_renders_real_activate_component(monkeypatch):
    """Mounts the shipped Tool Execution Status block from the product repository with fixture data."""
    from app.services import release_shots

    ready = release_shots.readiness()
    root = release_shots.ui_root()
    if not ready["ok"] or not root or not (root / TOOL_MODULE).is_file():
        pytest.skip(ready.get("reason") or "Tool Execution Status component not in this checkout")
    monkeypatch.setattr(release_shots, "review_shots", lambda results: {})
    tools = [
        {"tool_id": "t1", "tool_name": "fetch_customer_data", "tool_type": "custom_action", "executions": 1022, "success": 1022, "failed": 0, "running": 0, "avg_execution_time_ms": 833, "success_rate": 100.0},
        {"tool_id": "t2", "tool_name": "payment_link_sms", "tool_type": "sms_tool", "executions": 640, "success": 598, "failed": 42, "running": 0, "avg_execution_time_ms": 1210, "success_rate": 93.4},
    ]
    shot = release_shots.clean_shot(
        {
            "id": "tool-execution-status",
            "feature": "Tool Execution Status",
            "module": TOOL_MODULE,
            "props": {"tenantId": "acme-demo", "campaignIds": ["c1"], "campaignStatus": "all", "startDate": "2026-09-01", "endDate": "2026-09-30", "filters": {"filters": [], "logic": "AND"}},
            "mocks": [
                {
                    "method": "POST",
                    "path": "/{tenant}/analytics/multi-campaign/tool-execution-status",
                    "json": {"summary": {"total_executions": 1662, "success": 1620, "failed": 42, "running": 0, "success_rate": 97.5}, "tools": tools},
                }
            ],
            "expect_text": ["payment_link_sms", "97.5%"],
            "width": 1100,
            "section": "Outcome Analysis",
            "caption": "Tool Execution Status cards and details table.",
        },
        root,
        0,
        ["Tool Execution Status"],
    )
    out_dir = release_shots.SHOTS_ROOT / "pytest"
    results = release_shots.render_batch([shot], out_dir)
    assert results[0]["status"] == "ok", results[0]
    assert not results[0]["unmatched"]
    with Image.open(from_stored(results[0]["path"])) as image:
        assert image.width == 1100 * release_shots.DEVICE_SCALE

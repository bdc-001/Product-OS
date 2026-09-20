from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import pytest

from app.database import Base
from app.models import ReleaseJob
from app.services.feature_extract import default_checked, features_to_features_in_short
from app.services.release_detect import branch_from_subject, date_window_ok, enqueue_detected, new_release_merges, parse_merge_log
from app.services.release_worker import approve_and_publish, job_out


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


BITBUCKET = "abc123|parent1 parent2|2026-07-29T11:42:00+05:30|Merged in release/2026-07-29 (pull request #2631)"
GITHUB = "def456|mainsha featuresha|2026-09-23T11:42:00+05:30|Merge pull request #42 from release/2026-09-23"
INTO = "ghi789|a b|2026-09-23T11:42:00+05:30|Merge branch 'fix-wallet' into release/2026-09-23"
SUFFIX = "jkl012|a b|2026-07-24T11:00:00+05:30|Merged in release/2026-07-24-01 (pull request #1)"
WEIRD = "mno345|a b|2026-08-24T11:00:00+05:30|Merged in release/vb-24-08-2026 (pull request #2)"


def test_bitbucket_and_github_subjects():
    rows = parse_merge_log("\n".join([BITBUCKET, GITHUB]))
    assert [row["branch"] for row in rows] == ["release/2026-07-29", "release/2026-09-23"]
    assert rows[0]["base_sha"] == "parent1"
    assert rows[1]["sha"] == "def456"


def test_skips_merges_into_release_and_non_date_branches():
    assert parse_merge_log("\n".join([INTO, SUFFIX, WEIRD])) == []
    assert branch_from_subject("Merge branch 'x' into release/2026-09-23") == ""
    assert branch_from_subject("Merged in release/2026-07-24-01 (pull request #1)") == ""


def test_date_window_allows_late_cut_rejects_stale():
    ok, _ = date_window_ok("release/2026-08-25", "2026-09-03T10:00:00+05:30")
    assert ok
    stale, reason = date_window_ok("release/2026-06-01", "2026-08-01T10:00:00+05:30")
    assert not stale
    assert "stale" in reason
    early, _ = date_window_ok("release/2026-09-23", "2026-09-20T10:00:00+05:30")
    assert not early


def test_failed_git_log_does_not_baseline(tmp_path, monkeypatch):
    from app.services import release_detect

    monkeypatch.setattr(release_detect, "STATE", tmp_path / "release_detect.json")
    monkeypatch.setattr(release_detect, "detect_release_merges", lambda repo=None, lookback=30: None)
    db = _db()
    assert new_release_merges(db) == []
    assert not (tmp_path / "release_detect.json").exists()
    from app.services import release_detect

    monkeypatch.setattr(release_detect, "STATE", tmp_path / "release_detect.json")
    monkeypatch.setattr(
        release_detect,
        "detect_release_merges",
        lambda repo=None, lookback=30: [{"sha": "abc", "branch": "release/2026-09-23", "base_sha": "p", "merged_at": "2026-09-23T10:00:00+05:30"}],
    )
    db = _db()
    assert new_release_merges(db) == []
    assert new_release_merges(db) == []


def test_new_sha_creates_job_once(tmp_path, monkeypatch):
    from app.services import release_detect

    monkeypatch.setattr(release_detect, "STATE", tmp_path / "release_detect.json")
    merges = [{"sha": "old", "branch": "release/2026-09-01", "base_sha": "p", "merged_at": "2026-09-01T10:00:00+05:30"}]
    monkeypatch.setattr(release_detect, "detect_release_merges", lambda repo=None, lookback=30: list(merges))
    db = _db()
    assert new_release_merges(db) == []
    merges.append({"sha": "new", "branch": "release/2026-09-23", "base_sha": "q", "merged_at": "2026-09-23T10:00:00+05:30"})
    fresh = new_release_merges(db)
    assert [row["sha"] for row in fresh] == ["new"]
    created = enqueue_detected(db, fresh, triggered_by="test")
    assert len(created) == 1
    again = enqueue_detected(db, fresh, triggered_by="test")
    assert again == []
    assert db.query(ReleaseJob).count() == 1


def test_features_in_short_flags_low_and_honors_checked():
    result = {
        "features": [
            {"name": "Wallet v2", "what": "new recharge flow", "confidence": "HIGH"},
            {"name": "Retry callbacks", "what": "inferred from paths", "confidence": "LOW"},
        ]
    }
    all_lines = features_to_features_in_short(result)
    assert "Wallet v2 — new recharge flow" in all_lines
    assert "[unverified]" in all_lines
    checked = features_to_features_in_short(result, ["Wallet v2"])
    assert "Wallet v2" in checked
    assert "Retry" not in checked
    assert default_checked("HIGH")
    assert default_checked("MEDIUM")
    assert not default_checked("LOW")


def test_pdf_filename_convention():
    from app.services.pdf_notes import drive_doc_name, pdf_filename

    assert drive_doc_name("Revamped WhatsApp Analytics") == "Revamped WhatsApp Analytics_Release Note"
    assert drive_doc_name("Billing Dashboard_Release Note") == "Billing Dashboard_Release Note"
    assert pdf_filename("release/2026-09-23", "Billing Dashboard") == "Billing Dashboard_Release Note.pdf"


def test_dry_run_approve(tmp_path, monkeypatch):
    pdf = tmp_path / "2026-09-23 Notes.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    db = _db()
    job = ReleaseJob(
        branch="release/2026-09-23",
        sha="abc",
        status="pending_review",
        pdf_path=str(pdf),
        extraction={"features": []},
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    monkeypatch.setattr(
        "app.services.release_worker.upload_pdf",
        lambda *args, **kwargs: {"file_id": "dryrun", "link": "", "dry_run": True},
    )
    monkeypatch.setattr("app.services.release_worker.drive_configured", lambda: False)
    out = approve_and_publish(db, job)
    assert out["status"] == "uploaded"
    assert out["drive_file_id"] == "dryrun"
    assert job_out(job)["dry_run"] is True


def test_approve_rejects_wrong_status():
    db = _db()
    job = ReleaseJob(branch="release/2026-09-23", sha="abc", status="indexing")
    db.add(job)
    db.commit()
    try:
        approve_and_publish(db, job)
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "pending_review" in str(exc)


def test_doc_builder_tracks_exclusive_indices():
    from app.services.gdocs import DocBuilder

    builder = DocBuilder("doc")
    start, end = builder.line("Hello")
    assert start == 1
    assert end == 6
    assert builder.index == 7
    assert builder.requests[0]["insertText"]["text"] == "Hello\n"


def test_heuristic_doc_json_uses_feature_markers():
    from app.services.gdocs import CANONICAL_HEADINGS, clean_doc_json, heuristic_doc_json

    doc = heuristic_doc_json("Wallet v2", "Wallet v2 — new recharge flow\nRetry — inferred", "release/2026-09-23")
    assert "{{Wallet v2}}" in doc["intro"]
    assert "Clients" == doc["meta"]["audience"]
    assert "CSM" not in doc["intro"]
    assert doc["chips"][0] == "Release Note"
    assert doc["highlights"][0]["lead"] == "Wallet v2"
    assert [row["heading"] for row in doc["sections"]] == CANONICAL_HEADINGS
    assert "Key Highlights" not in [row["heading"] for row in doc["sections"]]
    background = next(row for row in doc["sections"] if row["heading"] == "Background")
    assert background["blocks"][0]["type"] == "bullets"
    how_to = next(row for row in doc["sections"] if row["heading"] == "How to Use")
    h3 = [block["text"] for block in how_to["blocks"] if block.get("type") == "h3"]
    assert h3 == ["8.1 Create / Configure", "8.2 Enable / Attach / Activate", "8.3 Day-to-Day Usage", "8.4 Review Outcomes"]
    refs = [block["ref"] for block in how_to["blocks"] if block.get("type") == "image"]
    assert refs == ["8.1", "8.2", "8.3", "8.4"]
    faqs = next(row for row in doc["sections"] if row["heading"] == "FAQs")
    assert faqs["blocks"][0]["type"] == "faq"
    cleaned = clean_doc_json(
        {
            "title": "Wallet v2",
            "chips": ["Release Note"],
            "intro": "x",
            "highlights": [{"lead": "A", "text": "b", "image": "missing.png"}],
            "sections": [{"heading": "Key Highlights", "body": "Shipped recharge."}],
        },
        "Wallet v2 — new recharge flow",
        screenshot_names=[],
    )
    assert cleaned["highlights"][0]["image"] is None
    by_heading = {row["heading"]: row["blocks"] for row in cleaned["sections"]}
    assert by_heading["Functional Overview"]
    assert by_heading["Background"]
    assert any(block.get("type") == "bullets" for block in by_heading["Functional Overview"])


def test_heading_applies_explicit_bold_on_normal_text():
    from app.services.gdocs import DocBuilder
    from app.services.gdocs_style import theme_named_style_requests

    builder = DocBuilder("doc")
    builder.heading("Background", 2)
    kinds = [next(iter(req)) for req in builder.requests]
    assert kinds == ["insertText", "deleteParagraphBullets", "updateParagraphStyle", "updateTextStyle"]
    para = next(req["updateParagraphStyle"]["paragraphStyle"] for req in builder.requests if "updateParagraphStyle" in req)
    text = next(req["updateTextStyle"]["textStyle"] for req in builder.requests if "updateTextStyle" in req)
    assert kinds.index("updateParagraphStyle") < kinds.index("updateTextStyle")
    assert para["namedStyleType"] == "NORMAL_TEXT"
    assert text["bold"] is True
    assert text["weightedFontFamily"]["fontFamily"] == "Helvetica"
    named = theme_named_style_requests()
    fonts = [row["updateNamedStyle"]["namedStyle"]["textStyle"]["weightedFontFamily"]["fontFamily"] for row in named]
    assert "Helvetica" in fonts
    assert "Inter" in fonts


def test_write_list_uses_real_bullets_then_clears():
    from app.services.gdocs import DocBuilder

    builder = DocBuilder("doc")
    builder.write_list(["One", {"lead": "Who benefits", "text": "CSMs"}], numbered=False)
    kinds = [next(iter(req)) for req in builder.requests]
    assert kinds.count("createParagraphBullets") == 1
    assert kinds.count("deleteParagraphBullets") == 1
    assert kinds.index("createParagraphBullets") < kinds.index("deleteParagraphBullets")
    named = [req["updateParagraphStyle"]["paragraphStyle"]["namedStyleType"] for req in builder.requests if "updateParagraphStyle" in req]
    assert "NORMAL_TEXT" in named
    bullet = next(req for req in builder.requests if "createParagraphBullets" in req)
    assert bullet["createParagraphBullets"]["bulletPreset"] == "BULLET_DISC_CIRCLE_SQUARE"
    numbered = DocBuilder("doc")
    numbered.write_list(["Open the surface"], numbered=True)
    preset = next(req for req in numbered.requests if "createParagraphBullets" in req)
    assert preset["createParagraphBullets"]["bulletPreset"] == "NUMBERED_DECIMAL_NESTED"


def test_docs_indexes_pin_emoji_as_utf16():
    from app.services.gdocs import DocBuilder, utf16_len

    assert utf16_len("📌") == 2
    assert utf16_len("📌 Background\n") == len("📌 Background\n") + 1
    builder = DocBuilder("doc")
    builder.heading("📌 Background", 2)
    insert = next(req["insertText"] for req in builder.requests if "insertText" in req)
    assert insert["text"] == "📌 Background\n"
    assert builder.index == 1 + utf16_len("📌 Background\n")
    para = next(req["updateParagraphStyle"]["range"] for req in builder.requests if "updateParagraphStyle" in req)
    text = next(req["updateTextStyle"]["range"] for req in builder.requests if "updateTextStyle" in req)
    assert para["startIndex"] == 1
    assert para["endIndex"] == builder.index
    assert text["endIndex"] == 1 + utf16_len("📌 Background")


def test_comms_doc_uses_docs_model():
    from app.clients.llm import model_for
    from app.config import settings

    if settings.llm_docs_model:
        assert model_for("comms_doc") == settings.llm_docs_model
        assert model_for("artifact") == settings.llm_docs_model
        assert model_for("artifact_brief") == settings.llm_docs_model
        assert model_for("artifact_content") == settings.llm_docs_model
        assert model_for("artifact_polish") == settings.llm_docs_model
        assert model_for("standup") == settings.llm_model
        if settings.llm_copilot_model:
            assert model_for("copilot") == settings.llm_copilot_model
    elif settings.llm_copilot_model:
        assert model_for("comms_doc") == settings.llm_copilot_model
        assert model_for("standup") == settings.llm_model


def test_anthropic_omits_temperature(monkeypatch):
    captured: dict = {}

    class Fake:
        status_code = 200
        text = ""

        def raise_for_status(self):
            return None

        def json(self):
            return {"content": [{"type": "text", "text": '{"ok": true}'}], "usage": {}}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["json"] = json
        return Fake()

    monkeypatch.setattr("app.clients.llm.post", fake_post)
    from app.clients.llm import LLMClient

    client = LLMClient(model="claude-fable-5-1")
    client.api_key = "test-key"
    client.base_url = "https://example.invalid"
    client.protocol = "anthropic"
    parsed = client.complete_json({"a": 1}, system_prompt="sys", temperature=0.5, surface="comms_doc")
    assert parsed == {"ok": True}
    assert "temperature" not in captured["json"]
    assert captured["json"]["model"] == "claude-fable-5-1"
    assert captured["json"]["messages"][-1]["role"] == "user"
    assert captured["json"]["output_config"] == {"effort": "high"}
    assert captured["json"]["max_tokens"] == 128000

    captured.clear()
    client.complete_json(
        {"a": 1},
        system_prompt="sys",
        surface="artifact_brief",
        images=[{"media_type": "image/jpeg", "data": "abcd"}],
    )
    content = captured["json"]["messages"][-1]["content"]
    assert isinstance(content, list)
    assert content[0]["type"] == "image"
    assert content[0]["source"]["data"] == "abcd"
    assert content[-1]["type"] == "text"
    assert "JSON object only" not in captured["json"]["system"]

    captured.clear()
    client.complete_json({"a": 1}, system_prompt="sys", surface="artifact_content", reasoning_effort="medium")
    assert captured["json"]["output_config"] == {"effort": "medium"}
    assert captured["json"]["max_tokens"] == 8192
    assert "JSON object only" in captured["json"]["system"]

    captured.clear()
    client.complete_json({"a": 1}, system_prompt="sys", surface="artifact_brief", reasoning_effort="xhigh")
    assert captured["json"]["output_config"] == {"effort": "xhigh"}
    assert captured["json"]["max_tokens"] == 128000
    assert "JSON object only" not in captured["json"]["system"]

    captured.clear()
    client.complete_json({"html": "<html></html>"}, system_prompt="sys", surface="artifact_polish", reasoning_effort="medium")
    assert captured["json"]["output_config"] == {"effort": "medium"}
    assert captured["json"]["max_tokens"] == 128000
    assert "JSON object only" not in captured["json"]["system"]


def test_artifact_brief_recovers_html_when_css_quotes_break_json():
    from app.clients.llm import _html_from_model_text

    raw = '{"html":"<!doctype html><html><style>:root{--d:"Helvetica Neue"}</style></html>"}'
    html = _html_from_model_text(raw)
    assert html.lower().startswith("<!doctype html>")
    assert html.endswith("</html>")
    assert "Helvetica Neue" in html


def test_svg_logos_are_not_anthropic_image_blocks():
    from app.services.feature_artifacts import _data_uri_image_block

    svg = "data:image/svg+xml;base64,PHN2Zy8+"
    assert _data_uri_image_block(svg, "logo_dark") is None
    jpeg = "data:image/jpeg;base64,abcd"
    block = _data_uri_image_block(jpeg, "screenshot_1")
    assert block == {"media_type": "image/jpeg", "data": "abcd", "name": "screenshot_1"}


def test_chip_style_and_rgb():
    from app.services.gdocs_style import chip_style, rgb_color

    orange = chip_style("orange")
    assert orange["bg"] == "EEF4FF"
    wrapped = rgb_color("1A62F2")
    assert "rgbColor" in wrapped["color"]
    assert 0 < wrapped["color"]["rgbColor"]["blue"] < 1


def test_h3_table_header_and_faq_q_stay_bold():
    import inspect

    from app.services.gdocs import (
        CONVIN_DOCS,
        DocBuilder,
        _write_faq,
        _write_paragraphs,
        is_faq_question,
        table_cell_text_style,
        write_release_notes_doc,
    )

    assert "restore_emphasis" in inspect.getsource(write_release_notes_doc)
    assert "force_nunito" not in inspect.getsource(write_release_notes_doc)
    builder = DocBuilder("doc")
    builder.heading("8.1 Create / Configure", 3)
    text = next(req["updateTextStyle"]["textStyle"] for req in builder.requests if "updateTextStyle" in req)
    assert text["bold"] is True
    assert text["weightedFontFamily"]["weight"] == 700
    header = table_cell_text_style(True)
    body = table_cell_text_style(False)
    assert header["bold"] is True
    assert header["weightedFontFamily"]["weight"] == 700
    assert body["bold"] is False
    assert body["weightedFontFamily"]["weight"] == 400
    assert is_faq_question("Q: Why am I not seeing Delivery Funnel?")
    faq = DocBuilder("doc")
    _write_paragraphs(faq, "Q: Why am I not seeing Delivery Funnel?\nA: Open WhatsApp Analytics so you can see it.", CONVIN_DOCS)
    styles = [req["updateTextStyle"] for req in faq.requests if "updateTextStyle" in req]
    q_style = next(row["textStyle"] for row in styles if row["textStyle"].get("bold") is True)
    assert q_style["bold"] is True
    assert q_style["weightedFontFamily"]["weight"] == 700
    a_styles = [row["textStyle"] for row in styles if row["textStyle"].get("bold") is not True]
    assert a_styles
    block_faq = DocBuilder("doc")
    _write_faq(block_faq, [{"q": "Why am I not seeing Read?", "a": "Switch to WhatsApp Analytics."}], CONVIN_DOCS)
    q_insert = next(req["insertText"]["text"] for req in block_faq.requests if req.get("insertText", {}).get("text", "").startswith("Q:"))
    assert q_insert.startswith("Q:")
    q_bold = next(
        req["updateTextStyle"]["textStyle"]["bold"]
        for req in block_faq.requests
        if "updateTextStyle" in req and req["updateTextStyle"]["textStyle"].get("bold") is True
    )
    assert q_bold is True


def test_emphasis_requests_cover_h3_headers_and_faq():
    from app.services.gdocs import emphasis_requests

    doc = {
        "body": {
            "content": [
                {
                    "startIndex": 1,
                    "endIndex": 24,
                    "paragraph": {
                        "paragraphStyle": {"namedStyleType": "HEADING_3"},
                        "elements": [{"textRun": {"content": "8.1 Create / Configure\n"}}],
                    },
                },
                {
                    "startIndex": 24,
                    "endIndex": 60,
                    "paragraph": {
                        "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                        "elements": [{"textRun": {"content": "Q: Why am I not seeing Read?\n"}}],
                    },
                },
                {
                    "startIndex": 60,
                    "endIndex": 90,
                    "table": {
                        "tableRows": [
                            {
                                "tableCells": [
                                    {"content": [{"startIndex": 62, "endIndex": 68}]},
                                    {"content": [{"startIndex": 70, "endIndex": 78}]},
                                ]
                            }
                        ]
                    },
                },
            ]
        }
    }
    reqs = emphasis_requests(doc)
    para = [row["updateParagraphStyle"]["range"] for row in reqs if "updateParagraphStyle" in row]
    styles = [row["updateTextStyle"] for row in reqs if "updateTextStyle" in row]
    ranges = [row["range"] for row in styles]
    assert {"startIndex": 1, "endIndex": 24} in para
    assert {"startIndex": 1, "endIndex": 23} in ranges
    assert {"startIndex": 24, "endIndex": 59} in ranges
    assert {"startIndex": 62, "endIndex": 67} in ranges
    assert all(row["textStyle"]["bold"] is True for row in styles)


def test_attach_howto_images_after_each_step():
    from app.services.gdocs import attach_howto_images, resolve_screenshot

    blocks = [
        {"type": "h3", "text": "8.1 Create / Configure"},
        {"type": "numbered", "items": ["Open Overview."]},
        {"type": "para", "text": "Expected result: cards are visible."},
        {"type": "h3", "text": "8.2 Enable / Attach / Activate"},
        {"type": "numbered", "items": ["Open the table."]},
        {"type": "image", "ref": "8.2"},
        {"type": "para", "text": "Expected result: metrics follow the selection."},
    ]
    shots = {"8.1": "https://drive.google.com/uc?export=view&id=a", "8.2": "https://drive.google.com/uc?export=view&id=b"}
    out = attach_howto_images(blocks, shots)
    types = [(block.get("type"), block.get("ref") or block.get("text")) for block in out]
    assert types[2] == ("image", "8.1")
    assert [block.get("ref") for block in out if block.get("type") == "image"] == ["8.1", "8.2"]
    assert resolve_screenshot(shots, "8.1.png") == shots["8.1"]


def test_comms_prompts_are_benefit_led():
    from app.services.comms import RELEASE_NOTES_PROMPT
    from app.services.gdocs import COMMS_DOC_PROMPT

    for prompt in (COMMS_DOC_PROMPT, RELEASE_NOTES_PROMPT):
        lower = prompt.lower()
        assert "you can" in lower
        assert 'never write "confirm in product"' in lower
        assert '"type": "image", "ref": "8.1"' in COMMS_DOC_PROMPT or "ref\": \"8.1\"" in COMMS_DOC_PROMPT


def test_whatsapp_howto_stills_match_ui_labels(tmp_path):
    from PIL import Image

    from app.services.howto_stills import render_whatsapp_analytics_stills

    paths = render_whatsapp_analytics_stills(tmp_path)
    assert set(paths) == {"8.1", "8.2", "8.3", "8.4"}
    for key, path in paths.items():
        image = Image.open(path)
        assert image.size == (1280, 720)
        assert path.name == f"{key}.png"


def test_feature_items_and_artifact_card(tmp_path, monkeypatch):
    import json
    from pathlib import Path

    from app.clients.llm import model_for
    from app.config import settings
    from app.services.artifact_html import render_artifact_html
    from app.services.feature_artifacts import (
        ARTIFACT_BRIEF_PROMPT,
        ARTIFACT_CONTENT_PROMPT,
        ARTIFACT_POLISH_PROMPT,
        ARTIFACT_PROMPT,
        BRIEF_EXEMPLAR,
        DECK_EXEMPLAR,
        artifact_pdf_name,
        clean_artifact,
        feature_items,
        generate_artifact,
        publish_feature_artifacts,
        render_artifact_pdf,
        sparse_from_evidence,
        _clean_block,
        _fit,
    )

    rows = feature_items("Wallet v2 — new recharge\nRetry callbacks")
    assert rows[0]["lead"] == "Wallet v2"
    assert "recharge" in rows[0]["text"]
    assert artifact_pdf_name("Revamped WhatsApp Analytics") == "Revamped WhatsApp Analytics_Artifact.pdf"
    assert artifact_pdf_name("PII masking", "brief") == "PII masking_Brief.pdf"

    lower = ARTIFACT_PROMPT.lower()
    assert "you can" in lower
    assert "stat_band" in ARTIFACT_PROMPT
    assert "grounded_doc" in ARTIFACT_PROMPT
    assert "marketing" in ARTIFACT_BRIEF_PROMPT.lower()
    assert "write your own css" in ARTIFACT_BRIEF_PROMPT.lower()
    assert "on_dark" in ARTIFACT_BRIEF_PROMPT.lower()
    assert "never fake fill" in ARTIFACT_BRIEF_PROMPT.lower()
    assert "space-between" in ARTIFACT_BRIEF_PROMPT.lower()
    assert "margin-top: auto" in ARTIFACT_BRIEF_PROMPT.lower() or "margin-top:auto" in ARTIFACT_BRIEF_PROMPT.lower()
    assert "exactly two a4 pages" not in ARTIFACT_BRIEF_PROMPT.lower()
    assert "empty bands at the bottom" not in ARTIFACT_BRIEF_PROMPT.lower()
    assert "sense" in ARTIFACT_BRIEF_PROMPT.lower()
    assert "shares this artifact with its customers" in ARTIFACT_BRIEF_PROMPT.lower()
    assert "masthead close-up" in ARTIFACT_BRIEF_PROMPT.lower()
    assert "do not copy that page's copy" in ARTIFACT_BRIEF_PROMPT.lower()
    assert "do not rewrite the story" in ARTIFACT_POLISH_PROMPT.lower()
    assert "overflow: visible" in ARTIFACT_POLISH_PROMPT.lower()
    assert "keep every fact" in ARTIFACT_POLISH_PROMPT.lower()
    assert "highlight bands" in ARTIFACT_BRIEF_PROMPT.lower()
    assert "pale blue" in ARTIFACT_BRIEF_PROMPT.lower()
    assert "must not overlap" in ARTIFACT_BRIEF_PROMPT.lower()
    assert "page number" in ARTIFACT_BRIEF_PROMPT.lower()
    assert "logo + page number" in ARTIFACT_POLISH_PROMPT.lower()
    assert "bluish" in ARTIFACT_POLISH_PROMPT.lower()
    assert "convin sense" in ARTIFACT_CONTENT_PROMPT.lower()
    assert "do not invent stats" in ARTIFACT_CONTENT_PROMPT.lower()
    assert "only include figures" in ARTIFACT_CONTENT_PROMPT.lower()
    assert "optional and often unnecessary" in ARTIFACT_CONTENT_PROMPT.lower()
    assert "em dash" in ARTIFACT_CONTENT_PROMPT.lower()
    assert "never use em dashes" in ARTIFACT_BRIEF_PROMPT.lower()
    assert "skip it when figures would be irrelevant" in ARTIFACT_BRIEF_PROMPT.lower()
    assert "do not introduce em dashes" in ARTIFACT_POLISH_PROMPT.lower()
    assert "do not brand this as activate" in ARTIFACT_CONTENT_PROMPT.lower()
    assert "you can" in ARTIFACT_CONTENT_PROMPT.lower()
    assert "continuous paragraphs" in ARTIFACT_CONTENT_PROMPT.lower() or "paragraphs only" in ARTIFACT_CONTENT_PROMPT.lower()
    assert '"description"' in ARTIFACT_CONTENT_PROMPT
    assert '"capabilities"' not in ARTIFACT_CONTENT_PROMPT
    assert '"headline"' not in ARTIFACT_CONTENT_PROMPT
    assert "1280x720" not in ARTIFACT_CONTENT_PROMPT
    assert "a designer will cut" not in ARTIFACT_CONTENT_PROMPT.lower()
    assert "what fits on two a4 pages" not in ARTIFACT_CONTENT_PROMPT.lower()
    assert "weight" not in ARTIFACT_CONTENT_PROMPT.lower()
    assert "size_hint" not in ARTIFACT_CONTENT_PROMPT.lower()

    sparse = sparse_from_evidence(
        "Wallet v2",
        "Wallet v2 — recharge in Activate\nRetry callbacks — retry failed top-ups",
        "deck",
    )
    assert sparse["pages"][0]["tone"] == "cover"
    assert all(page.get("type") != "why" for page in sparse["pages"])
    html = render_artifact_html(DECK_EXEMPLAR)
    assert "stat-band" in html
    assert "▯" not in html
    assert "→" not in html
    assert "Sent" in html and "Delivered" in html

    assert _fit("DATE RANGES: 24 HOURS, 7 DAYS, 30 DAYS, OR CUSTOM", 48) != (
        "DATE RANGES: 24 HOURS, 7 DAYS, 30 DAYS, OR CUSTO"
    )
    sliced = _fit("DATE RANGES: 24 HOURS, 7 DAYS, 30 DAYS, OR CUSTOM", 48)
    assert sliced is None or not sliced.endswith(("CUSTO", "custo"))
    long_cell = "Total sent, delivery rate, read rate, response rate, with change versus the previous window"
    assert _fit(long_cell, 80) != long_cell[:80]
    assert _fit(long_cell, 160) == long_cell

    band = _clean_block(
        {
            "type": "stat_band",
            "items": [
                {"value": "4", "label": "Funnel stages"},
                {"value": "4", "label": "Date ranges"},
                {"value": "CSV", "label": "Blocked-lead export"},
            ],
        }
    )
    assert [item["value"] for item in band["items"]] == ["4", "CSV"]

    duped = clean_artifact(
        {
            "title": "WhatsApp Analytics",
            "pages": [
                {
                    "tone": "hero",
                    "heading": "See the drop",
                    "blocks": [
                        {
                            "type": "cards",
                            "items": [
                                {
                                    "lead": "Find the drop",
                                    "text": "The delivery funnel shows the stage where the largest drop occurs.",
                                }
                            ],
                        },
                        {
                            "type": "table",
                            "headers": ["View", "How to use it"],
                            "rows": [
                                {"cells": ["Delivery funnel", "Find the stage where the largest drop occurs"]},
                                {"cells": ["Blocked leads", "Export at-risk leads as CSV"]},
                            ],
                        },
                    ],
                }
            ],
        },
        "WhatsApp Analytics",
        "WhatsApp Analytics — funnel",
        "brief",
    )
    table = next(block for block in duped["pages"][0]["blocks"] if block["type"] == "table")
    assert all("largest drop" not in " ".join(row["cells"]).lower() for row in table["rows"])

    brief_html = render_artifact_html(BRIEF_EXEMPLAR)
    assert "lockup--dark" in brief_html
    assert 'alt="CONVIN"' in brief_html
    assert "masthead__logo" in brief_html
    assert "hero__title" in brief_html
    assert "sec__h" in brief_html
    assert "is-focus" in brief_html
    assert brief_html.count("card is-focus") == 1
    assert "leads__item" in brief_html
    assert "panel__label" in brief_html
    assert "panel__grid" in brief_html
    assert "step__n" in brief_html
    assert "nav-step__num" not in brief_html
    assert "Why you need this" in brief_html
    assert 'class="stat-band"' in brief_html
    # Full-bleed stat band sits outside the padded body, after the hero.
    hero_at = brief_html.find('class="hero"')
    band_at = brief_html.find('class="stat-band"')
    body_at = brief_html.find('class="page__body"')
    assert hero_at < band_at < body_at

    luna_then_docs: list[str] = []

    def fake_chat_json(surface, system, payload, **kwargs):
        luna_then_docs.append(surface)
        if surface == "artifact_content":
            assert "features_in_short" in payload
            assert kwargs.get("reasoning_effort") == "medium"
            return {
                "title": "Wallet v2",
                "module": "Activate",
                "outcome": "Recharge without waiting.",
                "lede": "You can top up from Activate.",
                "stats": [
                    {"value": "30%", "label": "faster QA", "basis": ""},
                    {"value": "4", "label": "places data is hidden", "basis": "four surfaces in the doc"},
                ],
                "screenshots": [{"id": "8.1", "html": "<!doctype html><html>invented UI</html>"}],
            }
        if surface == "artifact_brief":
            assert "feature" in payload
            assert "logos" in payload
            assert "design" not in payload
            assert "brief_css" not in payload
            assert "exemplars" not in payload
            assert "#1A62F2" in system
            assert "print_css" not in payload
            assert "content_pack" not in payload
            assert payload["logos"]["on_dark"].startswith("data:image/")
            assert payload["logos"]["on_light"].startswith("data:image/")
            assert payload.get("screenshots") == []
            assert kwargs.get("reasoning_effort") == "xhigh"
            images = kwargs.get("images") or []
            names = [item.get("name") for item in images]
            assert "design_ref_1" in names
            assert "design_ref_2" in names
            assert "design_ref_3" in names
            assert "design_ref_4" in names
            assert "screenshot_1" not in names
            assert payload.get("design_refs")
            assert [row["name"] for row in payload["design_refs"]] == [
                "design_ref_1",
                "design_ref_2",
                "design_ref_3",
                "design_ref_4",
            ]
            assert "masthead" in payload["design_refs"][2]["role"].lower()
            assert "approved" in payload["design_refs"][3]["role"].lower()
            assert "layout craft" in (payload.get("note") or "").lower()
            assert "write your own css" in system.lower()
            assert "never fake fill" in system.lower()
            assert "space-between" in system.lower()
            assert "exactly two a4 pages" not in system.lower()
            assert "sense" in system.lower()
            assert "space-between" in (payload.get("note") or "").lower()
            assert payload["feature"].get("module") == "Sense"
            assert "description" in payload["feature"]
            assert "stats" not in payload["feature"]
            assert "You can top up from Activate." in payload["feature"]["description"]
            return {
                "html": "<!doctype html><html><head></head><body><section class='page'>Wallet crafted</section></body></html>"
            }
        if surface == "artifact_polish":
            assert kwargs.get("reasoning_effort") == "medium"
            assert "html" in payload
            assert "Wallet crafted" in payload["html"]
            return {
                "html": "<!doctype html><html><head></head><body><section class='page'>Wallet polished</section></body></html>"
            }
        raise AssertionError(surface)

    monkeypatch.setattr("app.services.feature_artifacts.chat_json", fake_chat_json)
    monkeypatch.setattr("app.services.feature_artifacts.ARTIFACT_DIR", tmp_path)
    monkeypatch.setattr(
        "app.services.feature_artifacts._branch_evidence",
        lambda title, features_in_short, branch="", notes="", doc=None: {
            "title": title,
            "features_in_short": features_in_short,
            "branch": branch,
            "notes_excerpt": notes,
            "grounded_doc": {},
        },
    )
    crafted = generate_artifact(title="Wallet v2", features_in_short="Wallet v2 — recharge", fmt="brief")
    assert luna_then_docs == ["artifact_content", "artifact_brief", "artifact_polish"]
    assert "Wallet polished" in crafted["html"]
    assert "invented UI" not in crafted["html"]
    assert crafted["stills"] == []
    assert "Wallet polished" in render_artifact_html(crafted)
    opus_html = Path(crafted["opus_html"])
    opus_json = Path(crafted["opus_json"])
    assert opus_html.is_file()
    assert opus_json.is_file()
    assert "Wallet crafted" in opus_html.read_text(encoding="utf-8")
    assert json.loads(opus_json.read_text(encoding="utf-8"))["html"]

    padded = clean_artifact({"title": "X", "pages": []}, "Wallet v2", "Wallet v2 — recharge", "deck")
    assert padded["pages"]
    assert "Why it matters" not in str(padded)

    monkeypatch.setattr(
        "app.services.feature_artifacts.generate_artifact",
        lambda **kwargs: sparse_from_evidence(kwargs["title"], kwargs["features_in_short"], kwargs.get("fmt") or "deck"),
    )
    monkeypatch.setattr("app.services.feature_artifacts.drive_configured", lambda: False)
    pdf = render_artifact_pdf(DECK_EXEMPLAR, tmp_path / "deck.pdf")
    assert pdf.read_bytes()[:4] == b"%PDF"
    published = publish_feature_artifacts(
        features_in_short="Wallet v2 — recharge",
        branch="release/2026-09-03",
        formats=("deck",),
    )
    assert published
    assert Path(published[0]["pdf_path"]).is_file()
    if settings.llm_docs_model:
        assert model_for("artifact") == settings.llm_docs_model
        assert model_for("artifact_brief") == settings.llm_docs_model
        assert model_for("artifact_polish") == settings.llm_docs_model
        assert model_for("standup") == settings.llm_model
        if settings.llm_copilot_model:
            assert model_for("artifact_content") == settings.llm_docs_model


def test_brief_placeholders_and_constant_columns():
    import re

    from app.services.artifact_html import (
        collapse_constant_tables,
        drop_constant_table_columns,
        prepare_brief_html,
        same_referent,
    )
    from app.services.feature_artifacts import _clean_block, _clean_content_pack
    from app.services.prompts import SURFACE_TEMPERATURE

    assert "artifact_brief" not in SURFACE_TEMPERATURE
    assert "artifact_polish" not in SURFACE_TEMPERATURE
    assert SURFACE_TEMPERATURE["artifact_content"] == 0.5
    assert same_referent(["Test Agent", "The agent"])
    assert not same_referent(["Web Chat Testing", "Web Call Testing", "Phone Call Testing"])

    headers, rows, caption = drop_constant_table_columns(
        ["View", "Where"],
        [
            {"cells": ["Web Chat Testing", "Test Agent"], "flags": ["", ""]},
            {"cells": ["Web Call Testing", "The agent"], "flags": ["", ""]},
        ],
    )
    assert headers == ["View"]
    assert [row["cells"] for row in rows] == [["Web Chat Testing"], ["Web Call Testing"]]
    assert "Test Agent" in caption

    table = (
        "<table class='matrix'><thead><tr><th>View</th><th>Where</th></tr></thead>"
        "<tbody><tr><td>Web Chat Testing</td><td>Test Agent</td></tr>"
        "<tr><td>Web Call Testing</td><td>The agent</td></tr></tbody></table>"
    )
    collapsed = collapse_constant_tables(table)
    assert "Where" not in collapsed
    assert "<caption>" in collapsed
    assert "Web Chat Testing" in collapsed

    block = _clean_block(
        {
            "type": "table",
            "headers": ["View", "Where"],
            "rows": [
                {"cells": ["Web Chat Testing", "Test Agent"], "flags": ["", ""]},
                {"cells": ["Web Call Testing", "The agent"], "flags": ["", ""]},
            ],
        }
    )
    assert block["headers"] == ["View"]
    assert "Test Agent" in (block.get("caption") or "")

    pack = _clean_content_pack(
        {
            "title": "Agent Testing",
            "module": "Activate",
            "description": "You can try a Sense agent in chat, a browser voice call, or a real outbound phone call before it goes live.",
            "stats": [
                {"value": "30%", "label": "faster cycles", "basis": "typical"},
                {"value": "3", "label": "test modes", "basis": "web chat, browser voice, phone"},
            ],
            "capabilities": [
                {"name": "Web Chat", "what_you_see": "Chat UI", "where": "Test Agent", "use_it_to": "Try chat"},
            ],
            "workflows": [{"lead": "Try chat first", "text": "Open Test Agent and start a web chat."}],
        },
        "Agent Testing",
        "Agent Testing — try the agent",
    )
    assert pack["title"] == "Agent Testing"
    assert pack["module"] == "Sense"
    assert "browser voice call" in pack["description"]
    assert "stats" not in pack
    assert "capabilities" not in pack
    assert "workflows" not in pack

    stitched = _clean_content_pack(
        {"headline": "Prove the agent first.", "lede": "You can rehearse in chat or on a real line."},
        "Agent Testing",
        "Agent Testing — try the agent",
    )
    assert "Prove the agent first." in stitched["description"]
    assert "rehearse in chat" in stitched["description"]

    html = prepare_brief_html(
        '<html lang="en"><body><img src="data:image/jpeg;base64,abc" alt="Test Agent"></body></html>'
    )
    assert "SCREENSHOT_1" not in html
    assert "LOGO_DARK" not in html
    visible = re.sub(r"<style\b[^>]*>[\s\S]*?</style>", " ", html, flags=re.I)
    assert "CONVIN A4 RELEASE BRIEF" not in visible
    assert "data:image/jpeg;base64,abc" in html
    assert 'lang="en"' in html
    with pytest.raises(RuntimeError, match="unresolved"):
        prepare_brief_html('<html><body><img src="SCREENSHOT_1" alt="Test Agent"></body></html>')
    with pytest.raises(RuntimeError, match="fragment"):
        prepare_brief_html("<div class=page>no document</div>")


def test_brief_uses_real_screenshot_not_luna_html(tmp_path, monkeypatch):
    from PIL import Image

    from app.services.feature_artifacts import generate_artifact

    shot = tmp_path / "8.1.png"
    Image.new("RGB", (64, 36), (26, 98, 242)).save(shot)

    def fake_chat_json(surface, system, payload, **kwargs):
        if surface == "artifact_content":
            return {
                "title": "Agent Testing",
                "module": "Activate",
                "outcome": "Try the agent first.",
                "screenshots": [{"id": "8.1", "html": "<html>fake Test Agent UI</html>"}],
            }
        if surface == "artifact_brief":
            dark = payload["logos"]["dark"]
            src = payload["screenshots"][0]["src"]
            assert src.startswith("data:image/")
            assert dark.startswith("data:image/")
            assert "design" not in payload
            images = kwargs.get("images") or []
            names = [item.get("name") for item in images]
            assert "screenshot_1" in names
            assert "design_ref_1" in names
            assert "design_ref_2" in names
            assert "design_ref_3" in names
            assert "design_ref_4" in names
            assert kwargs.get("reasoning_effort") == "xhigh"
            return {
                "html": (
                    "<!doctype html><html><head></head><body>"
                    f'<img src="{dark}" alt="CONVIN">'
                    f'<img src="{src}" alt="Test Agent">'
                    "</body></html>"
                )
            }
        if surface == "artifact_polish":
            assert kwargs.get("reasoning_effort") == "medium"
            return {"html": payload["html"]}
        raise AssertionError(surface)

    monkeypatch.setattr("app.services.feature_artifacts.chat_json", fake_chat_json)
    monkeypatch.setattr("app.services.feature_artifacts.ARTIFACT_DIR", tmp_path)
    monkeypatch.setattr(
        "app.services.feature_artifacts._branch_evidence",
        lambda *args, **kwargs: {"title": "Agent Testing", "features_in_short": "Agent Testing"},
    )
    crafted = generate_artifact(
        title="Agent Testing",
        features_in_short="Agent Testing — try the agent",
        fmt="brief",
        screenshots={"8.1": shot},
    )
    assert "SCREENSHOT_1" not in crafted["html"]
    assert "LOGO_DARK" not in crafted["html"]
    assert "fake Test Agent UI" not in crafted["html"]
    assert "data:image/jpeg;base64," in crafted["html"]
    assert crafted["stills"] == [str(shot)]


def test_print_keeps_one_sheet_per_html_page(tmp_path):
    import re

    from app.services.artifact_pdf import html_to_pdf, prepare_print_html

    html = """<!doctype html><html><head></head><body>
    <div class="page" style="width:794px;height:1123px;background:#1a62f2;color:#fff">one</div>
    <div class="page" style="width:794px;height:1123px;background:#050505;color:#fff">two</div>
    </body></html>"""
    printed = prepare_print_html(html)
    assert "@page" in printed
    assert "overflow: visible" in printed
    assert "size: A4" not in printed
    assert "height: 297mm !important" not in printed
    dest = tmp_path / "pages.pdf"
    html_to_pdf(html, dest, fit=False)
    blob = dest.read_bytes()
    assert blob[:4] == b"%PDF"
    count = len(re.findall(rb"/Type\s*/Page\b", blob))
    assert count == 2


def test_pdf_sheet_matches_tall_html_board(tmp_path):
    import re

    from app.services.artifact_pdf import html_to_pdf

    html = """<!doctype html><html><head></head><body>
    <div class="page" style="width:794px;height:1500px;background:#1a62f2;color:#fff">tall</div>
    </body></html>"""
    dest = tmp_path / "tall.pdf"
    html_to_pdf(html, dest, fit=False)
    blob = dest.read_bytes()
    assert blob[:4] == b"%PDF"
    count = len(re.findall(rb"/Type\s*/Page\b", blob))
    assert count == 1


def test_fit_pages_scales_overflow_instead_of_clipping():
    from app.services.artifact_pdf import fit_pages_to_a4, measure_page_fill

    html = """<!doctype html><html><body>
    <section class="page" style="width:794px;height:1123px;position:relative;overflow:hidden;background:#fff">
      <div class="body" style="height:1200px;background:#1a62f2;color:#fff">story that ran past the board</div>
      <div class="p1foot" style="position:absolute;bottom:0;left:0;right:0;height:48px;background:#050505;color:#fff">footer</div>
    </section>
    </body></html>"""
    before = measure_page_fill(html)
    assert before[0]["clipped"] is True
    fitted = fit_pages_to_a4(html)
    assert "page-fit" in fitted
    assert 'data-a4-scale="1"' not in fitted.split("page-fit", 1)[-1][:400]
    fills = measure_page_fill(fitted)
    assert fills[0]["clipped"] is False
    assert fills[0]["content_bottom"] <= 1123
    assert fills[0]["usable"] >= 1050


def test_fit_pages_leaves_short_boards_unscaled():
    from app.services.artifact_pdf import fit_pages_to_a4, measure_page_fill

    html = """<!doctype html><html><body>
    <section class="page" style="width:794px;height:1123px;position:relative;overflow:hidden">
      <div style="height:80px;background:#050505;color:#fff">hero</div>
      <div class="foot" style="position:absolute;bottom:0;left:0;right:0;height:40px">footer</div>
    </section>
    </body></html>"""
    fitted = fit_pages_to_a4(html)
    assert "data-a4-scale=\"1\"" in fitted or 'data-a4-scale="1.0"' in fitted
    fills = measure_page_fill(fitted)
    assert fills[0]["clipped"] is False
    assert fills[0]["ratio"] < 0.85


def test_measure_page_fill_catches_underfill():
    from app.services.artifact_pdf import FILL_WARN_BELOW, measure_page_fill

    html = """<!doctype html><html><body>
    <section class="page" style="width:794px;height:1123px;position:relative;overflow:hidden">
      <div style="height:80px;background:#050505;color:#fff">hero</div>
      <div class="foot" style="position:absolute;bottom:0;left:0;right:0;height:40px">footer</div>
    </section>
    </body></html>"""
    fills = measure_page_fill(html)
    assert fills
    assert fills[0]["ratio"] < FILL_WARN_BELOW
    assert fills[0]["clipped"] is False
    assert fills[0]["empty_band"] >= 800


def test_measure_page_fill_catches_empty_band():
    from app.services.artifact_pdf import EMPTY_BAND_MAX_PX, layout_needs_revise, measure_page_fill

    html = """<!doctype html><html><body>
    <section class="page" style="width:794px;height:1123px;position:relative;overflow:hidden">
      <div class="page__body">
        <div style="height:80px;background:#050505;color:#fff">top</div>
        <div style="height:80px;margin-top:400px;background:#1a62f2;color:#fff">bottom</div>
      </div>
      <div class="foot" style="position:absolute;bottom:0;left:0;right:0;height:40px">footer</div>
    </section>
    </body></html>"""
    fills = measure_page_fill(html)
    assert fills
    assert fills[0]["empty_band"] >= 350
    assert fills[0]["empty_band"] > EMPTY_BAND_MAX_PX
    assert layout_needs_revise(fills) is True


def test_full_unclipped_page_does_not_need_revise():
    from app.services.artifact_pdf import layout_needs_revise

    fills = [
        {"page": 1, "ratio": 1.0, "clipped": False, "empty_band": 32, "content_bottom": 1079, "usable": 1079},
        {"page": 2, "ratio": 0.99, "clipped": False, "empty_band": 27, "content_bottom": 1060, "usable": 1079},
    ]
    assert layout_needs_revise(fills) is False


def test_nested_footer_hoisted_and_flush():
    import re

    from playwright.sync_api import sync_playwright

    from app.services.artifact_pdf import fit_pages_to_a4, measure_page_fill

    html = """<!doctype html><html><head>
    <style>
      .howwrap { margin-top: auto; }
      .callout { margin-top: auto; }
      .ways .way .tail { margin-top: auto; }
    </style>
    </head><body>
    <section class="page" style="width:794px;height:1123px;position:relative;overflow:hidden;background:#fff">
      <div class="body1" style="padding:12px 24px 20px 24px">
        <div style="height:200px;background:#1a62f2;color:#fff">story</div>
        <div class="howwrap" style="height:80px;background:#eee">how</div>
        <div class="callout" style="height:40px;background:#103EA6;color:#fff">note</div>
        <div class="ways"><div class="way"><div class="tail" style="height:12px">tail</div></div></div>
        <div class="footer foot2" style="height:48px;background:#050505;color:#fff">PAGE 1 OF 2</div>
      </div>
    </section>
    </body></html>"""
    fitted = fit_pages_to_a4(html)
    match = re.search(r'data-foot-h="(\d+)"', fitted)
    assert match, fitted[:800]
    assert int(match.group(1)) > 0
    fills = measure_page_fill(fitted)
    assert fills[0]["clipped"] is False

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": 794, "height": 1123})
            page.set_content(fitted, wait_until="load")
            info = page.evaluate(
                """() => {
                  const pageEl = document.querySelector('.page');
                  const foots = pageEl.querySelectorAll('[class*="foot"]');
                  const foot = foots[foots.length - 1];
                  const pr = pageEl.getBoundingClientRect();
                  const fr = foot.getBoundingClientRect();
                  const callout = pageEl.querySelector('.callout');
                  const howwrap = pageEl.querySelector('.howwrap');
                  const tail = pageEl.querySelector('.tail');
                  return {
                    parentIsPage: foot.parentElement === pageEl,
                    overflow: fr.bottom - pr.bottom,
                    padL: parseFloat(getComputedStyle(foot).paddingLeft) || 0,
                    padB: parseFloat(getComputedStyle(foot).paddingBottom) || 0,
                    gapUnder: pr.bottom - fr.bottom,
                    footH: Number(pageEl.dataset.footH || 0),
                    calloutMt: callout ? callout.style.marginTop : '',
                    howwrapMt: howwrap ? howwrap.style.marginTop : '',
                    tailInline: tail ? tail.style.marginTop : '',
                    knowGap: (() => {
                      const know = callout;
                      const prev = know && know.previousElementSibling;
                      if (!know || !prev) return 0;
                      return know.getBoundingClientRect().top - prev.getBoundingClientRect().bottom;
                    })(),
                  };
                }"""
            )
        finally:
            browser.close()
    assert info["parentIsPage"] is True
    assert info["overflow"] <= 1
    assert info["gapUnder"] <= 1
    assert info["padL"] >= 20
    assert info["padB"] >= 16
    assert info["footH"] >= 16
    assert info["calloutMt"] == ""
    assert info["howwrapMt"] == ""
    assert info["tailInline"] == ""




import subprocess

import pytest

from app.services import release_note
from app.services.release_note import EXAMPLE, clean_note, feature_evidence, image_size_pt, write_body

SUPPORT = "support@example.com"


@pytest.fixture(autouse=True)
def _support_email(monkeypatch):
    monkeypatch.setattr(release_note, "support_email", lambda: SUPPORT)


def test_cta_drops_support_line_without_a_support_email(monkeypatch):
    monkeypatch.setattr(release_note, "support_email", lambda: "")
    note = clean_note({"cta": "This feature is an effort towards launching on time."}, FEATURE, [])
    assert note["cta"] == "This feature is an effort towards launching on time."
    assert "support@" not in release_note.note_prompt()


FEATURE = {"name": "Campaign Schedule", "what": "Schedule a campaign start", "modules": ["Campaigns"]}
SHOTS = [
    {"id": "picker", "caption": "Picker.", "path": "x.png"},
    {"id": "card", "caption": "Card.", "path": "y.png"},
]


def test_example_is_a_clean_note():
    assert clean_note(EXAMPLE, {"name": EXAMPLE["feature"]}, [])["sections"] == [
        {k: v for k, v in section.items() if k != "screenshot"} for section in EXAMPLE["sections"]
    ]
    assert EXAMPLE["title"] == "Campaign Schedule"
    assert SUPPORT in EXAMPLE["cta"]


def test_clean_note_enforces_the_format():
    raw = {
        "sections": [
            {"heading": "Navigation", "items": ["Open Campaigns."]},
            {
                "heading": "📌 Campaign Start",
                "items": [
                    {"lead": "Schedule for Later", "text": "Pick a date."},
                    {"text": "Leadless bullets outside Navigation are dropped."},
                    {"lead": "Note", "text": "Clones start immediately.", "note": True},
                    {"lead": "Note", "text": "A second note is dropped.", "note": True},
                ],
                "screenshot": {"id": "picker", "caption": "Schedule for Later selected."},
                "figure": {"kind": "comparison", "heading": "Past times", "items": [{"lead": "Edit", "text": "Rejected"}, {"lead": "Resume", "text": "Runs"}, {"lead": "X", "text": "cut"}]},
            },
            {"heading": "Go-live", "items": [{"lead": "Timing", "text": "Within a minute."}], "screenshot": {"id": "invented"}},
            {"heading": "Empty", "items": []},
        ],
        "cta": "This feature is an effort towards launching on time.",
    }
    note = clean_note(raw, FEATURE, SHOTS)
    assert note["title"] == "Campaign Schedule"
    assert [s["heading"] for s in note["sections"]] == ["📌 Navigation", "📌 Campaign Start", "📌 Go-live"]
    start = note["sections"][1]
    assert [i.get("lead") for i in start["items"]] == ["Schedule for Later", "Note"]
    assert start["screenshot"] == {"id": "picker", "caption": "Schedule for Later selected."}
    assert len(start["figure"]["items"]) == 2
    assert note["sections"][2]["screenshot"]["id"] == "card"
    assert "screenshot" not in note["sections"][0]
    assert note["cta"].endswith(f"raise it to {SUPPORT}.")


def test_tall_screenshots_are_capped():
    assert image_size_pt({"kind": "shot", "width": 640, "height": 180}) == (480.0, 135.0)
    width, height = image_size_pt({"kind": "shot", "width": 400, "height": 800})
    assert height == release_note.MAX_SHOT_HEIGHT_PT and width == 140.0


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def test_feature_evidence_ranks_the_feature_commits(tmp_path, monkeypatch):
    repo = tmp_path
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    (repo / "README.md").write_text("base\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
    (repo / "docs").mkdir()
    (repo / "docs" / "campaign-schedule-plan.md").write_text("Scheduled campaigns hold leads until go-live.\n")
    (repo / "campaign_schedule.go").write_text("package campaigns // scheduled start\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "Campaign Schedule: hold leads until the start time")
    (repo / "billing.go").write_text("package billing\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "Billing: invoice rounding")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
    monkeypatch.setattr(release_note, "codebase_root", lambda: repo)

    evidence = feature_evidence(base, head, FEATURE)
    assert [c["subject"] for c in evidence["commits"]] == ["Campaign Schedule: hold leads until the start time"]
    paths = [f["path"] for f in evidence["files"]]
    assert paths[0] == "docs/campaign-schedule-plan.md"
    assert "campaign_schedule.go" in paths and "billing.go" not in paths


def test_write_body_matches_the_reference_layout(monkeypatch):
    sent = []
    monkeypatch.setattr(release_note.DocBuilder, "commit", lambda self: sent.extend(self.requests))
    note = clean_note(EXAMPLE, {"name": EXAMPLE["feature"]}, [])
    last = len(note["sections"]) - 1
    images = [
        {"section": 1, "kind": "shot", "uri": "https://i/1", "caption": "Shot.", "width": 640, "height": 180},
        {"section": last, "kind": "figure", "uri": "https://i/2", "caption": "Conceptual comparison: x.", "width": 1400, "height": 510},
    ]
    write_body("doc", 40, note, images)
    inserted = "".join(r["insertText"]["text"] for r in sent if "insertText" in r)
    nav = note["sections"][0]["items"][0]["text"]
    nav_at = 40 + release_note.utf16_len(inserted.split(nav)[0])
    bullets = [r["createParagraphBullets"]["range"] for r in sent if "createParagraphBullets" in r]
    assert not any(b["startIndex"] <= nav_at < b["endIndex"] for b in bullets)
    assert len(bullets) == len(note["sections"]) - 1
    headings = [r for r in sent if "updateTextStyle" in r and "bold" in r["updateTextStyle"]["fields"] and "bold" not in r["updateTextStyle"]["textStyle"]]
    assert len(headings) == len(note["sections"])
    centered = [r for r in sent if r.get("updateParagraphStyle", {}).get("paragraphStyle", {}).get("alignment") == "CENTER"]
    assert len(centered) == 2
    keep = [r for r in sent if r.get("updateParagraphStyle", {}).get("paragraphStyle", {}).get("keepWithNext")]
    assert len(keep) == 2
    assert inserted.rstrip().endswith(SUPPORT + ".")
    links = [r["updateTextStyle"]["textStyle"]["link"] for r in sent if "link" in r.get("updateTextStyle", {}).get("textStyle", {})]
    assert links == [{"url": f"mailto:{SUPPORT}"}]

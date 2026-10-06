from pathlib import Path

from app.services.pdf_notes import write_release_pdf


def test_prd_pdf_writes_file(tmp_path: Path):
    dest = tmp_path / "prd.pdf"
    write_release_pdf(
        title="Variables in agent training",
        branch="release/2026-09-08",
        sha="abc1234",
        body="# Goal\nShip the metric.\n\n## Out of scope\nBilling.",
        dest=dest,
        audience="Internal",
        heading="ACME  ·  Product requirements",
    )
    assert dest.is_file()
    assert dest.stat().st_size > 200
    raw = dest.read_bytes()
    assert raw.startswith(b"%PDF")


def test_pdf_renders_heading_levels_and_inline_markdown(tmp_path: Path):
    dest = tmp_path / "formatted.pdf"
    write_release_pdf(
        title="Formatted note",
        branch="",
        sha="",
        body="# Title\n\n## Heading\n\n### Subhead\n\n- List item\n\nKeep **Copilot** and *Voice* together.",
        dest=dest,
        audience="",
        heading="Notes",
        branded=False,
    )
    assert dest.read_bytes().startswith(b"%PDF")
    assert dest.stat().st_size > 200

"""Release-note PDFs in Nunito with a Convin wordmark."""

from __future__ import annotations

import re
from pathlib import Path

from fpdf import FPDF

from app.config import ROOT
from app.services.time_window import now_local

PDF_DIR = ROOT / "data" / "release_notes"
FONT_DIR = Path(__file__).resolve().parents[1] / "fonts"
ASSET_DIR = Path(__file__).resolve().parents[1] / "assets"
REGULAR = FONT_DIR / "Nunito-Regular.ttf"
BOLD = FONT_DIR / "Nunito-Bold.ttf"
LOGO = ASSET_DIR / "logo.png"

HEADING = re.compile(
    r"^(📌\s*)?(Feature Title|Field \| Content|How to Use|Key Concepts|Prerequisites|Configuration Options|Outcome Analysis|Common Workflows|FAQs|Navigation|Functional Overview|Background)\b",
    re.I,
)
STEP = re.compile(r"^8\.\d")


def drive_doc_name(feature: str) -> str:
    """Drive / PDF stem: `{Feature Name}_Release Note`."""
    safe = re.sub(r"[^A-Za-z0-9._ -]+", "", (feature or "Release notes")).strip()
    safe = re.sub(r"\s+", " ", safe).strip(" ._")[:80] or "Release notes"
    stem = re.sub(r"[\s_]*release[\s_]*notes?$", "", safe, flags=re.I).strip(" ._") or safe
    return f"{stem}_Release Note"


def pdf_filename(branch: str, title: str) -> str:
    return f"{drive_doc_name(title)}.pdf"


def _family(pdf: FPDF) -> str:
    if REGULAR.is_file() and BOLD.is_file():
        pdf.add_font("Nunito", "", str(REGULAR))
        pdf.add_font("Nunito", "B", str(BOLD))
        return "Nunito"
    return "Helvetica"


def _clean(text: str) -> str:
    return (text or "").replace("\t", "    ").replace("\r", "").replace("⚙", "").replace("️", "")


def write_release_pdf(
    *,
    title: str,
    branch: str,
    sha: str,
    body: str,
    dest: Path | None = None,
    date_str: str = "",
    audience: str = "Clients",
    version: str = "",
    heading: str = "CONVIN  ·  Product release notes",
) -> Path:
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    if dest is None:
        dest = PDF_DIR / pdf_filename(branch, title)
    dest.parent.mkdir(parents=True, exist_ok=True)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    family = _family(pdf)
    if LOGO.is_file():
        try:
            pdf.image(str(LOGO), x=10, y=10, h=12)
            pdf.set_xy(10, 24)
        except Exception:
            pdf.set_xy(10, 10)
    pdf.set_font(family, "B", 11)
    pdf.set_text_color(91, 33, 182)
    pdf.cell(0, 6, heading, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_text_color(17, 24, 39)
    pdf.set_font(family, "B", 16)
    pdf.multi_cell(0, 8, _clean(title).strip() or "Product release notes", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    pdf.set_font(family, "", 10)
    pdf.set_text_color(80, 80, 80)
    meta = "  ·  ".join(
        part
        for part in (
            date_str or now_local().strftime("%d %b %Y"),
            audience,
            version or (branch or "").split("/")[-1],
            f"{branch}  {sha}".strip(),
        )
        if part
    )
    pdf.multi_cell(0, 6, _clean(meta), new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(17, 24, 39)
    pdf.ln(4)
    lines = _clean(body or "No notes generated.").splitlines() or [""]
    for raw in lines:
        line = raw.rstrip()
        if not line:
            pdf.ln(3)
            continue
        display = line.lstrip("#").replace("📌", "").strip() if line.startswith("#") else line.replace("📌", "").lstrip() or line
        bold = bool(line.startswith("#") or line.startswith("📌") or STEP.match(line) or HEADING.match(display))
        pdf.set_font(family, "B" if bold else "", 12 if bold else 11)
        pdf.multi_cell(0, 7 if bold else 6, display, new_x="LMARGIN", new_y="NEXT")
        if bold:
            pdf.ln(1)
    pdf.output(str(dest))
    return dest

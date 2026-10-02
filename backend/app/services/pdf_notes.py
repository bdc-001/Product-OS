"""Release-note PDFs in Nunito with the workspace wordmark."""

from __future__ import annotations

import re
from pathlib import Path

from fpdf import FPDF

from app.config import ROOT
from app.services.time_window import now_local
from app.storage import WorkspaceDir

PDF_DIR = WorkspaceDir("release_notes")
FONT_DIR = Path(__file__).resolve().parents[1] / "fonts"
ASSET_DIR = Path(__file__).resolve().parents[1] / "assets"
REGULAR = FONT_DIR / "Nunito-Regular.ttf"
BOLD = FONT_DIR / "Nunito-Bold.ttf"

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
        pdf.add_font("Nunito", "I", str(REGULAR))
        pdf.add_font("Nunito", "BI", str(BOLD))
        return "Nunito"
    return "Helvetica"


def _clean(text: str) -> str:
    return (text or "").replace("\t", "    ").replace("\r", "").replace("⚙", "").replace("️", "")


def _has_markdown(text: str) -> bool:
    return bool(re.search(r"\*\*[^*].+?\*\*", text) or re.search(r"(?<!\*)\*(?!\*)[^*]+\*(?!\*)", text))


def _cell(pdf: FPDF, family: str, style: str, size: float, height: float, text: str) -> None:
    pdf.set_font(family, style, size)
    marked = _has_markdown(text)
    try:
        pdf.multi_cell(0, height, text, new_x="LMARGIN", new_y="NEXT", markdown=marked)
    except Exception:
        pdf.set_font(family, style, size)
        pdf.multi_cell(0, height, text, new_x="LMARGIN", new_y="NEXT")


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
    heading: str = "",
    branded: bool = True,
    images: list[dict] | None = None,
) -> Path:
    """`images`: [{path, section, caption, width, height}] drawn at the end of their section."""
    from app.services.brand import pdf_heading, pdf_wordmark

    heading = heading or pdf_heading()
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    if dest is None:
        dest = PDF_DIR / pdf_filename(branch, title)
    dest.parent.mkdir(parents=True, exist_ok=True)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    family = _family(pdf)
    logo = pdf_wordmark() if branded else None
    if logo is not None:
        try:
            pdf.image(str(logo), x=10, y=10, h=12)
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
    pending = [item for item in images or [] if item.get("path") and Path(item["path"]).is_file()]
    section = ""

    def flush(name: str) -> None:
        for item in [i for i in pending if _section_key(i.get("section")) == name]:
            pending.remove(item)
            _image(pdf, family, item)

    lines = _clean(body or "No notes generated.").splitlines() or [""]
    for raw in lines:
        line = raw.rstrip()
        if not line:
            pdf.ln(3)
            continue
        hashes = len(re.match(r"^#+", line).group(0)) if line.startswith("#") else 0
        bullet = bool(re.match(r"^[-*•]\s+", line))
        display = line.lstrip("#").replace("📌", "").strip() if hashes else re.sub(r"^[-*•]\s+", "", line).replace("📌", "").lstrip() or line
        marked = HEADING.match(display) or STEP.match(line) or line.startswith("📌")
        named = HEADING.match(display)
        if (named or hashes == 2 or line.startswith("📌")) and not STEP.match(line):
            flush(section)
            section = _section_key(named.group(2) if named else display)
        if hashes == 1:
            _cell(pdf, family, "B", 18, 9, display)
            pdf.ln(2)
        elif hashes == 2 or marked:
            _cell(pdf, family, "B", 14, 8, display)
            pdf.ln(1)
        elif hashes >= 3:
            _cell(pdf, family, "B", 12, 7, display)
            pdf.ln(1)
        else:
            _cell(pdf, family, "", 11, 6, f"•  {display}" if bullet else display)
    flush(section)
    for item in list(pending):
        _image(pdf, family, item)
    pdf.output(str(dest))
    return dest


def _section_key(name) -> str:
    return re.sub(r"[^a-z]+", " ", str(name or "").lower()).strip()


def _image(pdf: FPDF, family: str, item: dict) -> None:
    usable = pdf.w - pdf.l_margin - pdf.r_margin
    width_px = float(item.get("width") or 0)
    height_px = float(item.get("height") or 0)
    width = min(usable, width_px * 0.2646) if width_px else usable
    height = width * height_px / width_px if width_px and height_px else 0
    if height and pdf.get_y() + height + 12 > pdf.h - pdf.b_margin:
        pdf.add_page()
    pdf.ln(2)
    pdf.image(str(item["path"]), x=pdf.l_margin + (usable - width) / 2, w=width, h=height)
    caption = _clean(str(item.get("caption") or "")).strip()
    if caption:
        pdf.set_text_color(100, 100, 100)
        pdf.set_font(family, "I", 9)
        pdf.multi_cell(0, 5, caption, align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(17, 24, 39)
    pdf.ln(3)

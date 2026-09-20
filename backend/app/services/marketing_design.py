"""Reference-led artifact design for approved marketing copy.

Uses the artifact pipeline's actual references, design contract, logo/font assets,
HTML composition and polish workflow instead of the former paragraph/Pillow templates.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from app.clients.llm import chat_json, model_for
from app.config import ROOT
from app.services.artifact_html import logo_data_uri, prepare_brief_html, _font_css
from app.services.feature_artifacts import _design_ref_blocks


def approved_text(key, content):
    if key == "linkedin_carousel":
        return [text for slide in content["slides"] for text in
                [slide["headline"], slide["body"], *slide.get("points", [])] if text]
    texts = [content.get("title", ""), content.get("dek", "")]
    for stat in content.get("stats") or []:
        texts += [stat.get("value", ""), stat.get("label", "")]
    for block in content.get("blocks") or []:
        texts += [block.get("heading", ""), block.get("risk", "")]
        for item in block.get("items") or []:
            texts += [item.get("lead", ""), item.get("text", "")]
    for section in content.get("sections") or []:
        texts += [section.get("heading", ""), section.get("body", "")]
    texts.append(content.get("cta", ""))
    return [text for text in texts if text]


def display_content(value):
    """Designers need approved display content, not the editor's internal evidence audit."""
    if isinstance(value, dict):
        return {key: display_content(item) for key, item in value.items() if key not in {"review", "model", "evidence", "customer_evidence", "outcome_evidence"}}
    if isinstance(value, list):
        return [display_content(item) for item in value]
    return value


def prepare_design(raw, *, embed_fonts=False):
    raw = raw.replace("{{brand_on_dark}}", logo_data_uri(dark=True)).replace(
        "{{brand_on_light}}", logo_data_uri(dark=False))
    try:
        raw = prepare_brief_html(raw)
    except RuntimeError as exc:
        raise ValueError("Design must be self-contained with complete HTML and embedded image assets.") from exc
    # Fonts are embedded by the renderer; remote font/style dependencies are unnecessary.
    raw = re.sub(r"<link\b[^>]*>", "", raw, flags=re.I)
    raw = re.sub(r"@import\s+[^;]+;", "", raw, flags=re.I)
    if re.search(r"<(?:iframe|object|embed|video|audio)\b|(?:src|href)\s*=\s*['\"]\s*(?:https?:|file:|//)", raw, re.I):
        raise ValueError("Design must be self-contained, with embedded assets only.")
    if not re.search(r"</head>", raw, re.I):
        raise ValueError("Design requires a complete head and body.")
    raw = re.sub(r'<style data-marketing-fonts>.*?</style>', '', raw, flags=re.S)
    if embed_fonts:
        raw = re.sub(r"</head>", lambda _: "<style data-marketing-fonts>" + _font_css() + "</style></head>", raw, count=1, flags=re.I)
    return raw


class DesignQualityError(RuntimeError):
    """A layout needs repair; approved copy must remain intact for a retry."""


FORMAT_DESIGN = {
    "release_notes": "RELEASE NOTES: a concise buyer update. Lead with what changed, show the approved use case and workflow, and keep prerequisites visible. Use clear sections and a compact editorial layout. No invented dates or release badges.",
    "case_study": "CASE STUDY: build an editorial customer story with the approved challenge, approach and documented outcome. Distinguish observed results from interpretation. Do not add quotes, figures, company logos or charts absent from approved copy.",
    "feature_brief": """FEATURE BRIEF: the approved copy is a visual pack, not a document. Every block already
names the device it has to become. why is a risk statement with the reasons to care beside it; cards are
parallel arguments; flow and steps are a connected sequence with visible order; comparison is a two sided
split panel; panel is the quieter dark caveat grid. Build a stat band from stats when they exist and leave
it out entirely when they do not. One dense A4 page is the target, and a second page only when the pack
cannot fit at readable sizes. The copy is deliberately short, so carry the page with structure, scale and
colour: an oversized headline, one real diagram, connected nodes, generous cards. Never expand the short
items back into paragraphs, and never restate a block's heading as body copy to fill space.""",
    "linkedin_carousel": """CAROUSEL: every slide names its visual treatment. statement is a full bleed type
slide; contrast is a split panel holding the two supplied labels against each other; steps is a numbered
connected sequence; spotlight is one dominant device with its supporting label; stat is an oversized figure
with its qualifier. Compose the treatments differently so consecutive slides never look alike. The headline
is the dominant element at phone scale, roughly 64 to 96px, the body sits as one quiet supporting line, and
points belong inside the visual as labels rather than as a bulleted list. Fill each slide with its device,
not with stacked text cards.""",
}


def compose_design(key, content, folder, *, repair="", previous_html=""):
    design = (ROOT / "backend/app/static/artifacts/marketing-design.md").read_text()
    refs = _design_ref_blocks()
    if not refs:
        raise RuntimeError("Approved artifact design references are missing.")
    aspect = "1080x1350 social portrait, one .page per approved slide" if key == "linkedin_carousel" else "794x1123 A4 portrait"
    prompt = design + """\nMARKETING ADAPTATION: These rules override the original output/input contract above.
You are designing already-approved copy, not rewriting or researching a feature. Return JSON {html:string}.
Preserve all approved display copy verbatim, including qualifications. Do not invent additional claims,
statistics, charts, quotes, navigation, availability, testimonials or product screenshots. The reference
images establish design quality, not product facts. Turn the supplied workflow/points into meaningful
visual relationships using CSS or inline SVG: connected flows for ordered steps, split panels for real
contrasts, labelled evidence groups, decision branches when the copy describes alternatives. Do not
default to a paragraph report or identical cards. Keep one dominant visual anchor per page/slide.
Match the artifact pipeline's full-bleed navy masthead, actual Convin lockup, large display typography,
white interior, selective dark/blue emphasis, fine strokes and footer band. Reference craft must remain
recognizable at the channel size. Carousel slides need social-sized text and varied compositions;
do not squeeze an A4 page into each slide. A4 documents should use the fewest well-composed pages that
hold the approved copy, usually one or two. No filler to manufacture density.
All display copy must live inside .page elements (210mm wide, height auto, overflow visible). No positioning content beyond its page,
hidden copy or font shrinking to evade overflow. Footer stays in flow. No JavaScript, no Google Fonts, and no other external assets.
Use <img src="{{brand_on_dark}}"> on dark backgrounds and {{brand_on_light}} on light backgrounds.
Before choosing a generated field, check lockup polarity: a black or dark masthead only sits on a solid light band you own; a white lockup only sits on navy, black or brand. Never place a black header on a pale photographic or generated wash.
Use Inter for body and Helvetica Neue for display; local font embedding is supplied afterward.
Do not include the carousel upload caption on its slides; it is a separate deliverable.
""" + FORMAT_DESIGN.get(key, "")
    fingerprint = hashlib.sha256(json.dumps({"version": 3, "format": key, "content": content,
        "repair": repair, "previous_html": previous_html,
        "contract": prompt, "references": [r["data"] for r in refs], "model": model_for("marketing_design")}, sort_keys=True).encode()).hexdigest()
    work = folder / "design" / key / fingerprint
    work.mkdir(parents=True, exist_ok=True)
    final = work / "approved.html"
    if final.is_file():
        return final.read_text()
    payload = {"format": key, "page_size": aspect, "approved_copy": display_content(content),
               "repair": repair, "previous_html": previous_html,
               "reference_roles": [{"name": r["name"], "role": r["role"]} for r in refs]}
    raw = chat_json("marketing_design", prompt, payload, images=refs,
                    max_chars=len(json.dumps(payload)) + 1000, timeout=900, max_retries=0, reasoning_effort="xhigh")
    source = str(raw.get("html") or "")
    (work / "composed.html").write_text(source)
    # Like artifact_polish, focus a separate call on layout. Rendering verifies that
    # neither designer nor polish silently removed approved copy.
    for attempt in range(3):
        request = {"html": source, "format": key, "page_size": aspect,
                   "approved_copy": display_content(content),
                   "instruction": "Preserve every word of approved copy. Improve hierarchy, composition and visual usefulness to match the references. Return JSON {html:string}.",
                   "repair": repair}
        raw = chat_json("marketing_design_polish", prompt, request, images=refs,
                       max_chars=len(json.dumps(request)) + 1000, timeout=900, max_retries=0, reasoning_effort="high")
        source = str(raw.get("html") or "")
        try:
            source = prepare_design(source)
            render_design(key, content, source, work, export=False)
            final.write_text(source)
            return source
        except ValueError as exc:
            repair = str(exc)[:2500]
    raise DesignQualityError("Artifact design needs repair: " + repair)


def render_design(key, content, source, folder: Path, *, export=True):
    """Chromium board rendering, with no page scripts or outbound resource requests."""
    from playwright.sync_api import sync_playwright
    from app.services.artifact_pdf import _merge_pdf_blobs
    width, height = (1080, 1350) if key == "linkedin_carousel" else (794, 1123)
    source = prepare_design(source, embed_fonts=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context(viewport={"width": width, "height": height}, java_script_enabled=False)
            context.route("**/*", lambda route: route.abort())
            page = context.new_page()
            page.set_content(source, wait_until="load")
            page.evaluate("() => document.fonts.ready")
            boards = page.locator(".page")
            count = boards.count()
            if not count or (key == "linkedin_carousel" and count != len(content["slides"])):
                raise ValueError("Each approved slide needs exactly one page; documents need at least one page.")
            def normalized(text):
                return " ".join(text.split())
            visible = normalized(" ".join(boards.all_inner_texts()))
            missing = [text[:90] for text in approved_text(key, content) if normalized(text) not in visible]
            if missing:
                raise ValueError("Design omitted or rewrote approved copy: " + "; ".join(missing[:4]))
            sizes = boards.evaluate_all("""els => els.map(el => {
                const b=el.getBoundingClientRect();
                const outside=[...el.querySelectorAll('*')].filter(child => {
                    const r=child.getBoundingClientRect();
                    return r.width && r.height && (r.right>b.right+1 || r.bottom>b.bottom+1 || r.left<b.left-1 || r.top<b.top-1);
                }).map(child=>child.textContent.slice(0,70));
                return {width:b.width,height:b.height,scrollWidth:el.scrollWidth,scrollHeight:el.scrollHeight,outside};
            })""")
            for i, size in enumerate(sizes):
                if (abs(size["width"]-width)>2 or abs(size["height"]-height)>2 or
                    size["scrollHeight"]>height+2 or size["scrollWidth"]>width+2 or size["outside"]):
                    raise ValueError(f"Page {i+1} exceeds its {width}x{height} board: {size['outside'][:3]}. Recompose without clipping or shrinking the text.")
            if not export:
                return []
            folder.mkdir(parents=True, exist_ok=True)
            (folder / f"{key}.html").write_text(source)
            files, blobs = [(f"{key}.html", "text/html")], []
            for index in range(count):
                if key == "linkedin_carousel":
                    name = f"{key}-{index+1:02}.png"
                    boards.nth(index).screenshot(path=str(folder / name))
                    files.append((name, "image/png"))
                boards.evaluate_all("(els,index)=>els.forEach((el,i)=>i===index?el.style.removeProperty('display'):el.style.setProperty('display','none'))", index)
                blobs.append(page.pdf(width=f"{width}px", height=f"{height}px", print_background=True,
                                      prefer_css_page_size=False, margin={"top":"0","bottom":"0","left":"0","right":"0"}))
                boards.evaluate_all("els=>els.forEach(el=>el.style.removeProperty('display'))")
            _merge_pdf_blobs(blobs, folder / f"{key}.pdf")
            files.append((f"{key}.pdf", "application/pdf"))
            return files
        finally:
            browser.close()

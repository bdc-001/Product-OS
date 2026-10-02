"""Reference-led artifact design for approved marketing copy.

Uses the artifact pipeline's actual references, design contract, logo/font assets,
HTML composition and polish workflow instead of the former paragraph/Pillow templates.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path

from app.clients.llm import chat_json, model_for
from app.config import ROOT
from app.services.brand import artifact_path
from app.services.artifact_html import logo_data_uri, prepare_brief_html, _font_css
from app.services.feature_artifacts import _design_ref_blocks

DESIGN_VERSION = 6


def approved_text(key, content):
    if key == "linkedin_carousel":
        return [text for slide in content["slides"] for text in
                [slide["headline"], slide["body"], *slide.get("points", [])] if text]
    if key == "feature_brief":
        from app.services.marketing_onepager import onepager_text
        return onepager_text(content)
    texts = [content.get("title", ""), content.get("dek", "")]
    for stat in content.get("stats") or []:
        texts += [stat.get("value", ""), stat.get("label", "")]
    for block in content.get("blocks") or []:
        texts += [block.get("heading", ""), block.get("risk", "")]
        for item in block.get("items") or []:
            texts += [item.get("lead", ""), item.get("text", "")]
    for section in content.get("sections") or []:
        if key != "release_notes" or section.get("role") != "overview":
            texts.append(section.get("heading", ""))
        if key == "release_notes":
            texts.extend(re.sub(r"^\s*(?:\d+[.)]|[-•*]|#{2,4})\s+", "", line)
                         for line in section.get("body", "").splitlines() if line.strip())
        else:
            texts.append(section.get("body", ""))
    texts.append(content.get("cta", ""))
    texts.append(content.get("illustration_label", ""))
    return [text for text in texts if text]


def display_content(value):
    """Designers need approved display content, not the editor's internal evidence audit."""
    if isinstance(value, dict):
        return {key: display_content(item) for key, item in value.items() if key not in {"review", "model", "evidence", "customer_evidence", "outcome_evidence"}}
    if isinstance(value, list):
        return [display_content(item) for item in value]
    return value


def brand_tokens() -> dict[str, str]:
    from html import escape

    from app.services.brand import brand_name
    from app.services.profile import load_profile, product_modules

    profile = load_profile()
    product = profile.get("product_name") or product_modules()[0]
    return {
        "{{brand_name}}": escape(brand_name(), quote=True),
        "{{brand_product}}": escape(product, quote=True),
        "{{brand_module}}": escape(product_modules()[0], quote=True),
    }


def prepare_design(raw, *, embed_fonts=False):
    raw = raw.replace("{{brand_on_dark}}", logo_data_uri(dark=True)).replace(
        "{{brand_on_light}}", logo_data_uri(dark=False))
    for token, value in brand_tokens().items():
        raw = raw.replace(token, value)
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


def normalized_copy(text):
    # CSS uppercase and PDF ligatures are typography, not editorial changes.
    text = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "-", str(text))
    return " ".join(unicodedata.normalize("NFKC", str(text)).replace("\u00ad", "").casefold().split())


def missing_pdf_copy(key, content, visible):
    # Chromium/PDF extraction inserts spaces between tracked display glyphs.
    # DOM checks still require the exact words; PDF checks preserve every glyph.
    text = normalized_copy(visible)
    compact = text.replace(" ", "")
    return [part[:90] for part in approved_text(key, content)
            if normalized_copy(part) not in text
            and normalized_copy(part).replace(" ", "") not in compact]


FORMAT_DESIGN = {
    "feature_image": "FEATURE IMAGE: exactly one 1600x900 landscape .page board. A dominant connected diagram, large short labels, the company logo and strong blue/navy visual hierarchy. Include the approved Conceptual workflow label. Body is alt text, not drawn copy. Never invent a screenshot or use decorative stock cards.",
    "release_notes": "RELEASE NOTES: A detailed operator manual. Use semantic h1/h2, ordered lists for numbered workflow actions and paragraphs. Normal document flow with page breaks that preserve reading order; no fixed boards, clipping, absolute positioning or oversized poster mastheads. Set A4 print margins to 16mm and body to at least 11pt.  a buyer document, not a poster. Flow the approved sections in reading order across the fewest exact A4 pages the copy needs. Keep the artifact masthead, type ramp, hairlines and footer. Lead with what changed, then the use case and workflow, and keep prerequisites visible. No invented dates or release badges.",
    "case_study": "CASE STUDY: build an editorial customer story with the approved challenge, approach and documented outcome. Distinguish observed results from interpretation. Do not add quotes, figures, company logos or charts absent from approved copy.",
    "article": """ARTICLE: Exactly two A4 pages in the artifact system. Four approved visual blocks,
two per page. No prose sections. Page one owns the outcome and dominant mechanism diagram; page two
owns the decision/offer and next step. Compose items INSIDE their visual device, never a paragraph above
a second diagram repeating it. Preserve each approved label and short sentence once. Use large readable
type and meaningful illustrated relationships for at least half the usable page area. Build workflow nodes,
before/after panels and decision branches with genuine supported content. Do not add boilerplate, labels,
benefits, statistics or an invented example to fill space. Navy masthead, white interior, precise grid,
hairlines, generous visual scale and a full-bleed navy footer containing only the white lockup and page number. Do not collapse to one page or add a third.""",
    "linkedin_carousel": """CAROUSEL: every slide names its visual treatment. statement is a full bleed type
slide; contrast is a split panel holding the two supplied labels against each other; steps is a numbered
connected sequence; spotlight is one dominant device with its supporting label; stat is an oversized figure
with its qualifier. Compose the treatments differently so consecutive slides never look alike. The headline
is the dominant element at phone scale, roughly 64 to 96px, the body sits as one quiet supporting line, and
points belong inside the visual as labels rather than as a bulleted list. Fill each slide with its device,
not with stacked text cards. Use a strict 64px horizontal grid, 24/32/48px vertical rhythm, 80-100px
headlines and 32-40px labels. Align nodes, arrows, captions and baselines precisely. Vary scale and
composition: typography-led cover, full-bleed offer, connected mechanism, contrasting decision, clear CTA.
Never enlarge empty cards, draw placeholder bars, or add floating chips to fill space. Give diagrams
real feature meaning. No unsupported quantitative bars. Keep the composition deliberately balanced,
with no accidental empty bands or objects stranded between the copy and footer.
If a headline names a total but the approved points supply only a subset,
label the points as Examples; do not imply that the subset is the complete set or invent missing items.""",
}


def compose_design(key, content, folder, *, repair="", previous_html=""):
    design = artifact_path("marketing-design.md").read_text()
    refs = _design_ref_blocks()
    if not refs:
        raise RuntimeError("Approved artifact design references are missing.")
    aspect = "1080x1350 social portrait, one .page per approved slide" if key == "linkedin_carousel" else "1600x900 landscape" if key == "feature_image" else "794x1123 A4 portrait"
    prompt = design + """\nMARKETING ADAPTATION: These rules override the original output/input contract above.
You are designing already-approved copy, not rewriting or researching a feature. Return JSON {html:string}.
Preserve all approved display copy verbatim, including qualifications. Do not invent additional claims,
statistics, charts, quotes, navigation, availability, testimonials or product screenshots.
Do not invent missing category names from a stated count, treat severity as measured frequency, or add
release dates from reference artwork. Extra diagram labels must be supported by approved_copy itself.
Conceptual diagram labels may identify the visualization as conceptual. Never draw invented pass/fail
grids, fake results tables or sample screen rows. Show pass/fail as possible outcomes in a branch,
not a made-up sequence of actual results. Do not encode unspecified lead limits as counted dots,
quantitative bars or ratios. Use labelled relationships for sampling and selection instead.
The reference images establish design quality, not product facts. Turn the supplied workflow/points into meaningful
visual relationships using CSS or inline SVG: connected flows for ordered steps, split panels for real
contrasts, labelled evidence groups, decision branches when the copy describes alternatives. Do not
default to a paragraph report or identical cards. Keep one dominant visual anchor per page/slide.
Match the artifact pipeline's full-bleed navy masthead, actual company lockup, large display typography,
white interior, selective dark/blue emphasis, fine strokes and footer band. Reference craft must remain
recognizable at the channel size. Carousel slides need social-sized text and varied compositions;
do not squeeze an A4 page into each slide. A4 documents should use the fewest well-composed pages that
hold the approved copy, usually one or two. No filler to manufacture density.
For fixed boards (article, feature_brief, carousel and feature_image), all display copy must live inside .page elements at the EXACT supplied pixel dimensions, height fixed, overflow visible. This overrides the reference height:auto rule. Use @page margin:0 and body margin:0. No positioning content beyond its page,
hidden copy or font shrinking to evade overflow. Footer stays in flow. No JavaScript, no Google Fonts, and no other external assets.
Use <img src="{{brand_on_dark}}"> on dark backgrounds and {{brand_on_light}} on light backgrounds.
Before choosing a generated field, check lockup polarity: a black or dark masthead only sits on a solid light band you own; a white lockup only sits on navy, black or brand. Never place a black header on a pale photographic or generated wash.
Use Inter for body and Helvetica Neue for display; local font embedding is supplied afterward.
Do not include the carousel upload caption on its slides; it is a separate deliverable.
""" + FORMAT_DESIGN.get(key, "")
    if key in {"release_notes", "case_study"}:
        prompt += "\nThis is a flowing document. Do not use fixed-height .page elements. Preserve paragraphs and numbered steps. The page size is A4 with readable body text and normal pagination."
    fingerprint = hashlib.sha256(json.dumps({"version": DESIGN_VERSION, "format": key, "content": content,
        "repair": repair, "previous_html": previous_html,
        "contract": prompt, "references": [r["data"] for r in refs], "model": model_for("marketing_design")}, sort_keys=True).encode()).hexdigest()
    work = folder / "design" / key / fingerprint
    work.mkdir(parents=True, exist_ok=True)
    (work / "contract-version.txt").write_text(str(DESIGN_VERSION))
    final = work / "approved.html"
    if final.is_file():
        return final.read_text()
    payload = {"format": key, "page_size": aspect, "approved_copy": display_content(content),
               "repair": repair, "previous_html": previous_html,
               "reference_roles": [{"name": r["name"], "role": r["role"]} for r in refs]}
    composed = work / "composed.html"
    if composed.is_file():
        source = composed.read_text()
    elif key == "linkedin_carousel":
        from app.services.marketing_compositions import carousel_seed
        source = carousel_seed(content)
        composed.write_text(source)
    else:
        raw = chat_json("marketing_design", prompt, payload, images=refs,
                        max_chars=len(json.dumps(payload)) + 1000, timeout=900, max_retries=0, reasoning_effort="xhigh")
        source = str(raw.get("html") or "")
        composed.write_text(source)
    try:
        if key not in {"release_notes", "case_study"}:
            render_design(key, content, prepare_design(source), work, export=False)
    except ValueError as exc:
        repair = str(exc)[:2500]
    # Like artifact_polish, focus a separate call on layout. Rendering verifies that
    # neither designer nor polish silently removed approved copy.
    for attempt in range(3):
        request = {"html": source, "format": key, "page_size": aspect,
                   "approved_copy": display_content(content),
                   "instruction": "Preserve every word of approved copy. Art-direct the composition against the supplied approved references: full-bleed navy masthead with white lockup, product pill, document label, large headline; a dense white interior with feature-specific connected visual devices; a full-bleed navy footer with white lockup and page number. Correct generic composition, weak visual hierarchy and alignment, not just geometry. Every diagram must communicate an actual relationship in the approved copy. Avoid repeating icon cards and empty boxes. Return JSON {html:string}.",
                   "repair": repair}
        raw = chat_json("marketing_design_polish", prompt, request, images=refs,
                       max_chars=len(json.dumps(request)) + 1000, timeout=900, max_retries=0, reasoning_effort="high")
        source = str(raw.get("html") or "")
        (work / f"polished-{attempt + 1}.html").write_text(source)
        try:
            source = prepare_design(source)
            if key in {"release_notes", "case_study"}:
                render_flowing_document(key, content, source, work)
            else:
                render_design(key, content, source, work, export=False)
            final.write_text(source)
            return source
        except ValueError as exc:
            repair = str(exc)[:2500]
            (work / "layout-error.txt").write_text(repair)
    raise DesignQualityError("Artifact design needs repair: " + repair)


def render_flowing_document(key, content, source, folder: Path):
    """Release notes and case studies print as documents, not fixed boards."""
    from playwright.sync_api import sync_playwright
    import fitz

    source = prepare_design(source, embed_fonts=True)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{key}.html").write_text(source, encoding="utf-8")
    pdf_path = folder / f"{key}.pdf"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context(java_script_enabled=False)
            context.route("**/*", lambda route: route.abort())
            page = context.new_page()
            page.set_content(source, wait_until="load")
            page.evaluate("() => document.fonts.ready")
            options = {}
            if key == "release_notes":
                from app.services.marketing_manual import manual_header
                options = {"display_header_footer": True, "header_template": manual_header(),
                           "footer_template": "<span></span>"}
            page.pdf(path=str(pdf_path), format="A4", print_background=True, prefer_css_page_size=True, **options)
        finally:
            browser.close()
    with fitz.open(pdf_path) as document:
        visible = " ".join(page.get_text() for page in document)
        pages = document.page_count
    missing = missing_pdf_copy(key, content, visible)
    if missing:
        raise ValueError("Design omitted or rewrote approved copy: " + "; ".join(missing[:4]))
    if pages < 1:
        raise ValueError("Release document did not produce a page.")
    return [(f"{key}.html", "text/html"), (f"{key}.pdf", "application/pdf")]


def render_artifact_design(key, content, folder: Path, set_step=lambda *a: None):
    """Reference-led compose -> polish -> layout validation -> visual review, per format."""
    from app.services.marketing_quality import review_rendered
    if key == "release_notes":
        from app.services.marketing_manual import manual_design, render_manual_figures
        try:
            files = render_manual_figures(content, folder)
            files += render_flowing_document(key, content, manual_design(content, folder), folder)
            return files + review_rendered(key, content, folder, files)
        except ValueError as exc:
            raise DesignQualityError(str(exc)) from exc
    if key == "feature_brief":
        # Sales one-pagers use the locked design-system template: copy is placed verbatim
        # and density steps down until it fits, so there is no designer model to repair.
        from app.services.marketing_onepager import render_onepager
        files = render_onepager(content, folder, set_step)
        try:
            return files + review_rendered(key, content, folder, files)
        except ValueError as exc:
            raise DesignQualityError(str(exc)) from exc
    # Visual formats require the reference-led composition and independent polish
    # below. Fixed generic cards bypass design repair and leave large empty panels.
    repair, source = "", ""
    # Resume a composed/polished board after a provider outage. Revalidate against
    # this copy before using it; visual review still runs on the actual new export.
    if key not in {"release_notes", "case_study"}:
        candidates = list((folder / "design" / key).glob("*/approved.html")) + list((folder / "design" / key).glob("*/polished-*.html"))
        for candidate in sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True):
            version = candidate.parent / "contract-version.txt"
            if not version.is_file() or version.read_text().strip() != str(DESIGN_VERSION):
                continue
            try:
                draft = candidate.read_text()
                render_design(key, content, draft, folder, export=False)
                source = draft
                break
            except ValueError:
                continue
    for attempt in range(3):
        try:
            if not source or attempt:
                source = compose_design(key, content, folder, repair=repair, previous_html=source)
            files = (render_flowing_document(key, content, source, folder)
                     if key in {"release_notes", "case_study"} else render_design(key, content, source, folder))
            return files + review_rendered(key, content, folder, files)
        except (ValueError, DesignQualityError) as exc:
            repair = str(exc)[:3000]
            set_step(key, {"status": "running", "design_repair_attempt": attempt + 1, "detail": repair[:400]})
    raise DesignQualityError(repair)


def render_design(key, content, source, folder: Path, *, export=True):
    """Chromium board rendering, with no page scripts or outbound resource requests."""
    from playwright.sync_api import sync_playwright
    from app.services.artifact_pdf import _merge_pdf_blobs
    width, height = (1080, 1350) if key == "linkedin_carousel" else (1600, 900) if key == "feature_image" else (794, 1123)
    source = prepare_design(source, embed_fonts=True)
    # add_style_tag waits on a page script event that never fires with scripts
    # disabled. Embed print overrides before loading, after reference styles.
    source = re.sub(r"</head>", lambda _: (
        f"<style>@page {{ size: {width}px {height}px !important; margin: 0 !important; }} "
        "html,body { margin:0 !important; padding:0 !important; }"
        ".page { margin:0 !important; break-before:auto !important; break-after:auto !important; }</style></head>"
    ), source, count=1, flags=re.I)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context(viewport={"width": width, "height": height}, java_script_enabled=False)
            context.route("**/*", lambda route: route.abort())
            page = context.new_page()
            page.set_content(source, wait_until="load")
            page.evaluate("() => document.fonts.ready")
            # Reference @page A4 rules must never resize a social/landscape board.
            page.emulate_media(media="screen")
            boards = page.locator(".page")
            count = boards.count()
            if not count or (key == "linkedin_carousel" and count != len(content["slides"])):
                raise ValueError("Each approved slide needs exactly one page; documents need at least one page.")
            expected = {"feature_brief": 1, "article": 2, "feature_image": 1}.get(key)
            if expected and count != expected:
                raise ValueError(f"{key} requires exactly {expected} pages, received {count}.")
            visible = normalized_copy(" ".join(boards.all_inner_texts()))
            missing = [text[:90] for text in approved_text(key, content) if normalized_copy(text) not in visible]
            if missing:
                raise ValueError("Design omitted or rewrote approved copy: " + "; ".join(missing[:4]))
            sizes = boards.evaluate_all("""els => els.map(el => {
                const b=el.getBoundingClientRect();
                const footers=[...el.querySelectorAll('footer,.footer,.page-footer')];
                const outside=[...el.querySelectorAll('*')].filter(child => {
                    // Decorative glows may intentionally extend beyond a clipped band.
                    // Measure actual text/image boxes and their clipping ancestors.
                    const hasText=[...child.childNodes].some(n=>n.nodeType===3 && n.textContent.trim());
                    if (!hasText && child.tagName!=='IMG' && !child.matches('.cta,.callout')) return false;
                    const r=child.getBoundingClientRect();
                    if (!r.width || !r.height) return false;
                    const exceeds=p=>r.right>p.right+2 || r.bottom>p.bottom+2 || r.left<p.left-2 || r.top<p.top-2;
                    if (exceeds(b)) return true;
                    if (footers.some(footer=>{
                        if(footer===child || footer.contains(child) || child.contains(footer)) return false;
                        const f=footer.getBoundingClientRect();
                        return Math.min(r.right,f.right)-Math.max(r.left,f.left)>2 && Math.min(r.bottom,f.bottom)-Math.max(r.top,f.top)>2;
                    })) return true;
                    for(let parent=child.parentElement;parent && parent!==el;parent=parent.parentElement){
                        const style=getComputedStyle(parent);
                        if (/(hidden|clip)/.test(style.overflow+style.overflowX+style.overflowY) && exceeds(parent.getBoundingClientRect())) return true;
                    }
                    return false;
                }).map(child=>`${child.tagName}.${child.className}: ${child.textContent.slice(0,90)}`);
                return {width:b.width,height:b.height,scrollWidth:el.scrollWidth,scrollHeight:el.scrollHeight,outside};
            })""")
            for i, size in enumerate(sizes):
                if (abs(size["width"]-width)>2 or abs(size["height"]-height)>2 or size["outside"]):
                    raise ValueError(f"Page {i+1} exceeds its {width}x{height} board or has text covered by its footer: {size['outside'][:3]}. Reserve footer space and recompose without clipping or shrinking the text.")
            if not export:
                return []
            folder.mkdir(parents=True, exist_ok=True)
            (folder / f"{key}.html").write_text(source)
            files, blobs = [(f"{key}.html", "text/html")], []
            original_styles = boards.evaluate_all("els=>els.map(el=>el.getAttribute('style'))")
            for index in range(count):
                if key in {"linkedin_carousel", "feature_image"}:
                    name = f"{key}-{index+1:02}.png"
                    boards.nth(index).screenshot(path=str(folder / name))
                    files.append((name, "image/png"))
                boards.evaluate_all("(els,index)=>els.forEach((el,i)=>i===index?el.style.removeProperty('display'):el.style.setProperty('display','none'))", index)
                # A board is a canvas, not a flowing document. Fixed positioning
                # prevents print fragmentation from moving an intact CTA to a
                # second page even when screen geometry is within its board.
                boards.nth(index).evaluate("el=>{el.style.setProperty('position','fixed','important');el.style.setProperty('left','0','important');el.style.setProperty('top','0','important');}")
                blob = page.pdf(width=f"{width}px", height=f"{height}px", print_background=True,
                                prefer_css_page_size=True, margin={"top":"0","bottom":"0","left":"0","right":"0"})
                import fitz
                with fitz.open(stream=blob, filetype="pdf") as printed:
                    if len(printed) != 1 or abs(printed[0].rect.width - width * .75) > 2 or abs(printed[0].rect.height - height * .75) > 2:
                        (folder / f"{key}-export-check.pdf").write_bytes(blob)
                        raise ValueError(f"PDF board {index + 1} produced {len(printed)} pages at {printed[0].rect.width:.1f}x{printed[0].rect.height:.1f}pt; expected one {width * .75:.1f}x{height * .75:.1f}pt page. Check outer overflow and print CSS.")
                blobs.append(blob)
                boards.evaluate_all("(els,styles)=>els.forEach((el,i)=>styles[i]===null?el.removeAttribute('style'):el.setAttribute('style',styles[i]))", original_styles)
            _merge_pdf_blobs(blobs, folder / f"{key}.pdf")
            with fitz.open(folder / f"{key}.pdf") as printed:
                text = " ".join(p.get_text() for p in printed)
            missing = missing_pdf_copy(key, content, text)
            if missing:
                raise ValueError("PDF export lost approved copy: " + "; ".join(missing[:4]))
            files.append((f"{key}.pdf", "application/pdf"))
            return files
        finally:
            browser.close()

"""Locked layouts for marketing formats.

Copy is placed verbatim. A designer model cannot rewrite a headline and then fail the format.
LinkedIn posts stay messages. Release notes and case studies are flowing documents.
A feature brief is one A4 page. An article is a two-page artifact. A carousel is one board per slide.
"""
from __future__ import annotations

import html
from pathlib import Path

from app.services.brand import artifact_path
from app.services.marketing_design import approved_text


PAGE = {"feature_brief": (794, 1123, 1), "article": (794, 1123, 2), "linkedin_carousel": (1080, 1350, None)}
DOCUMENTS = {"release_notes", "case_study"}


def _product() -> str:
    from app.services.marketing_video import product_label

    return product_label()


def _module() -> str:
    from app.services.marketing_video import module_label

    return module_label()


def _e(value) -> str:
    return html.escape(str(value or ""), quote=True)


def _page(inner: str, width: int, height: int, size: int) -> str:
    return (
        f'<section class="page" style="width:{width}px;height:{height}px;box-sizing:border-box;'
        f'overflow:hidden;background:#fff;color:#151515;padding:36px 40px;font:400 {size}px/1.35 Inter,Arial,sans-serif">'
        f"{inner}</section>"
    )


def _shell(title: str, pages: list[str]) -> str:
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>{_e(title)}</title>
<style>
body{{margin:0;background:#fff}}
h1{{font:700 28px/1.15 Helvetica,Arial,sans-serif;margin:12px 0}}
h2{{font:700 16px/1.25 Helvetica,Arial,sans-serif;margin:14px 0 4px}}
p{{margin:0 0 8px}}
.brand img{{height:22px}}
</style></head><body>
{''.join(pages)}
</body></html>"""


def _blocks(content) -> str:
    parts = []
    for stat in content.get("stats") or []:
        parts.append(f"<p><strong>{_e(stat.get('value'))}</strong> {_e(stat.get('label'))}</p>")
    for block in content.get("blocks") or []:
        parts.append(f"<h2>{_e(block.get('heading'))}</h2>")
        if block.get("risk"):
            parts.append(f"<p>{_e(block.get('risk'))}</p>")
        for item in block.get("items") or []:
            parts.append(f"<p><strong>{_e(item.get('lead'))}</strong> {_e(item.get('text'))}</p>")
    return "".join(parts)


def _sections(sections) -> str:
    return "".join(f"<h2>{_e(section.get('heading'))}</h2><p>{_e(section.get('body'))}</p>" for section in sections)


def layout_html(key: str, content: dict, size: int = 13) -> str:
    """Fixed boards whose visible text is the approved copy."""
    title = content.get("title") or ""
    if key == "feature_brief":
        width, height, _ = PAGE[key]
        inner = (
            f'<p class="brand"><img src="{{{{brand_on_dark}}}}" alt="{{{{brand_name}}}}"></p>'
            f"<h1>{_e(title)}</h1><p>{_e(content.get('dek'))}</p>{_blocks(content)}<p>{_e(content.get('cta'))}</p>"
        )
        return _shell(title, [_page(inner, width, height, size)])
    if key == "article":
        width, height, _ = PAGE[key]
        sections = list(content.get("sections") or [])
        split = max(1, (len(sections) + 1) // 2)
        first = (
            f'<p class="brand"><img src="{{{{brand_on_dark}}}}" alt="{{{{brand_name}}}}"></p>'
            f"<h1>{_e(title)}</h1><p>{_e(content.get('dek'))}</p>{_sections(sections[:split])}"
        )
        second = f"{_sections(sections[split:])}<p>{_e(content.get('cta'))}</p>"
        return _shell(title, [_page(first, width, height, size), _page(second, width, height, size)])
    if key == "linkedin_carousel":
        width, height, _ = PAGE[key]
        pages = []
        for slide in content.get("slides") or []:
            points = "".join(
                f'<p style="margin:0 0 10px;font-size:{max(size - 4, 18)}px">{_e(point)}</p>'
                for point in slide.get("points") or []
            )
            inner = (
                f'<div style="height:10px;background:#FCED02"></div>'
                f'<div style="padding:56px 64px;height:{height - 10}px;box-sizing:border-box;'
                f'background:linear-gradient(165deg,#0A2E7A 0%,#103EA6 55%,#144ECF 100%);color:#F7FAFF">'
                f'<p style="margin:0 0 28px;font-size:18px;letter-spacing:1.4px;color:#FCED02">{_e(_product().upper())}</p>'
                f'<h1 style="font-size:{size + 16}px;line-height:1.08;margin:0 0 22px">{_e(slide.get("headline"))}</h1>'
                f'<p style="font-size:{size}px;line-height:1.35;margin:0 0 18px">{_e(slide.get("body"))}</p>'
                f"{points}</div>"
            )
            pages.append(
                f'<section class="page" style="width:{width}px;height:{height}px;box-sizing:border-box;'
                f'overflow:hidden;margin:0;padding:0">{inner}</section>'
            )
        return _shell(title, pages)
    raise ValueError(f"{key} does not use a fixed board.")


def document_html(content: dict, label: str = "Release notes") -> str:
    """A flowing A4 document. The approved title and sections are not rewritten."""
    sections = _sections(content.get("sections") or [])
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>{_e(content.get('title'))}</title>
<style>
@page {{ size: A4; margin: 18mm; }}
body {{ margin: 0; color: #151515; font: 400 12pt/1.45 Inter, Arial, sans-serif; }}
header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 8px solid #0A2E7A; padding-bottom: 10px; }}
header img {{ height: 22px; }}
.label {{ color: #0A2E7A; font: 600 10pt/1.2 Inter, Arial, sans-serif; letter-spacing: .4px; }}
h1 {{ font: 700 22pt/1.15 Helvetica, Arial, sans-serif; margin: 16px 0 8px; color: #0A2E7A; }}
h2 {{ font: 700 13pt/1.25 Helvetica, Arial, sans-serif; margin: 16px 0 4px; color: #103EA6; }}
p {{ margin: 0 0 8px; }}
</style></head><body>
<header><img src="{{{{brand_on_dark}}}}" alt="{{{{brand_name}}}}"><span class="label">{_e(label)}</span></header>
<h1>{_e(content.get('title'))}</h1>
<p>{_e(content.get('dek'))}</p>
{sections}
<p>{_e(content.get('cta'))}</p>
</body></html>"""


def _missing_copy(key, content, visible: str) -> list[str]:
    def normalized(text):
        return " ".join(str(text).split())
    haystack = normalized(visible)
    return [text[:90] for text in approved_text(key, content) if normalized(text) not in haystack]


def _artifact_css() -> str:
    from app.config import ROOT
    return artifact_path("brief.css").read_text(encoding="utf-8")


def _hero(title: str, dek: str, label: str) -> str:
    return (
        f'<header class="hero"><div class="masthead">'
        f'<img class="masthead__logo" src="{{{{brand_on_dark}}}}" alt="{{{{brand_name}}}}">'
        f'<span class="masthead__label">{_e(label)}</span></div>'
        f'<h1 class="hero__title">{_e(title)}</h1>'
        f'<p class="hero__lede">{_e(dek)}</p></header>'
    )


def _foot(note: str, page: int, total: int) -> str:
    return (
        f'<footer class="foot"><img src="{{{{brand_on_light}}}}" alt="{{{{brand_name}}}}" style="height:16px">'
        f'<span class="foot__note">{_e(note)}</span><span>{page} / {total}</span></footer>'
    )


def _block(block: dict) -> str:
    items = "".join(
        f'<div class="leads__item"><b>{_e(item.get("lead"))}</b> {_e(item.get("text"))}</div>'
        for item in block.get("items") or []
    )
    risk = f'<p class="prose">{_e(block.get("risk"))}</p>' if block.get("risk") else ""
    return (
        f'<section><div class="block-head"><h2 class="block-head__h">{_e(block.get("heading"))}</h2></div>'
        f"{risk}<div class=\"leads\">{items}</div></section>"
    )


def _section(section: dict) -> str:
    return (
        f'<section><div class="block-head"><h2 class="block-head__h">{_e(section.get("heading"))}</h2></div>'
        f'<p class="prose">{_e(section.get("body"))}</p></section>'
    )


def branded_artifact_html(key: str, content: dict) -> str:
    """Approved copy inside the release-artifact page system."""
    css = _artifact_css()
    title = content.get("title") or ""
    dek = content.get("dek") or ""
    cta = content.get("cta") or ""
    if key == "feature_brief":
        body = "".join(_block(block) for block in content.get("blocks") or [])
        stats = "".join(
            f'<div class="stat"><div class="stat__value">{_e(stat.get("value"))}</div>'
            f'<div class="stat__label">{_e(stat.get("label"))}</div></div>'
            for stat in content.get("stats") or []
        )
        band = f'<div class="stat-band">{stats}</div>' if stats else ""
        page = (
            f'<section class="page page--hero page--dense">{_hero(title, dek, "Feature brief")}'
            f"{band}<div class=\"page__body\">{body}<p class=\"prose\">{_e(cta)}</p></div>{_foot(cta, 1, 1)}</section>"
        )
    elif key == "article":
        sections = list(content.get("sections") or [])
        split = max(1, (len(sections) + 1) // 2)
        first = "".join(_section(section) for section in sections[:split])
        second = "".join(_section(section) for section in sections[split:])
        page = (
            f'<section class="page page--hero page--dense">{_hero(title, dek, "Artifact")}'
            f'<div class="page__body">{first}</div>{_foot(cta, 1, 2)}</section>'
            f'<section class="page page--plain page--dense"><div class="page__body">'
            f'<div class="masthead"><img class="masthead__logo" src="{{{{brand_on_light}}}}" alt="{{{{brand_name}}}}">'
            f'<span class="masthead__label">Artifact</span></div>{second}'
            f'<p class="prose">{_e(cta)}</p></div>{_foot(cta, 2, 2)}</section>'
        )
    else:
        sections = "".join(_section(section) for section in content.get("sections") or [])
        label = "Release notes" if key == "release_notes" else "Case study"
        css += ".page{height:auto;min-height:1123px;overflow:visible}.page__body{overflow:visible;flex:none}"
        page = (
            f'<section class="page page--hero page--dense">{_hero(title, dek, label)}'
            f'<div class="page__body">{sections}<p class="prose">{_e(cta)}</p></div>{_foot(cta, 1, 1)}</section>'
        )
    return (
        f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>{_e(title)}</title>'
        f"<style>{css}.page--dense .hero{{padding:24px 40px 18px}}"
        f".page--dense .hero__title{{font-size:28px;line-height:32px}}"
        f".page--dense .hero__lede{{margin-top:8px}}"
        f".page--dense .block-head{{margin-bottom:4px}}"
        f".page--dense .leads{{gap:8px 18px}}"
        f".page--dense .prose{{font-size:12px;line-height:17px}}</style></head><body>{page}</body></html>"
    )


def carousel_html(content: dict) -> str:
    """Phone-scale LinkedIn boards with a shared grid, tight type, and filled visual zone."""
    slides = list(content.get("slides") or [])
    total = max(len(slides), 1)
    pages = []
    for index, slide in enumerate(slides, start=1):
        pages.append(_carousel_slide(slide, index, total))
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\"><style>"
        "*{box-sizing:border-box}html,body{margin:0;padding:0;background:#fff}"
        ".page{width:1080px;height:1350px;overflow:hidden;display:flex;flex-direction:column;"
        "font-family:Inter,Helvetica Neue,Arial,sans-serif}"
        ".page.is-dark{background:linear-gradient(165deg,#071533 0%,#0a2e7a 42%,#144ecf 100%);color:#fff}"
        ".page.is-light{background:#f4f7fc;color:#102342}"
        ".chrome{display:flex;align-items:center;justify-content:space-between;padding:36px 56px 0;flex:0 0 auto}"
        ".chrome img{height:26px;width:auto;display:block}"
        ".kicker{font-size:13px;font-weight:700;letter-spacing:1.8px;text-transform:uppercase}"
        ".page.is-dark .kicker{color:#9ec0ff}.page.is-light .kicker{color:#1a62f2}"
        ".copy{padding:22px 56px 0;flex:0 0 auto}"
        "h1{margin:0;font-size:58px;line-height:1.06;letter-spacing:-1.4px;font-weight:700;max-width:940px}"
        ".dek{margin:14px 0 0;font-size:22px;line-height:1.3;font-weight:400;max-width:880px}"
        ".page.is-dark .dek{color:#d7e4ff}.page.is-light .dek{color:#435772}"
        ".visual{flex:1 1 auto;min-height:0;margin:22px 56px 20px;display:flex}"
        ".foot{flex:0 0 68px;display:flex;align-items:center;justify-content:space-between;"
        "padding:0 56px;background:#050b18;color:#fff;font-size:15px;font-weight:600;letter-spacing:.4px}"
        ".foot img{height:18px}"
        ".fill{flex:1;display:flex;min-height:0;width:100%}"
        ".quote{flex:0 1 auto;max-width:100%;padding:4px 0 4px 28px;border-left:8px solid #1a62f2}"
        ".page.is-dark .quote{border-left-color:#fced02}"
        ".quote strong{display:block;font-size:44px;line-height:1.12;letter-spacing:-.9px;font-weight:700}"
        ".fill.is-quote{align-items:center}"
        ".chips{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin-top:28px}"
        ".chip{padding:14px 18px;border-radius:16px;font-size:20px;font-weight:650;background:#fff;"
        "border:1px solid #d6deea;color:#102342}"
        ".page.is-dark .chip{background:rgba(255,255,255,.12);border-color:rgba(255,255,255,.2);color:#fff}"
        ".steps-h,.cols{display:grid;gap:16px;width:100%;height:100%;align-content:stretch}"
        ".steps-h{grid-template-columns:repeat(var(--n,3),minmax(0,1fr))}"
        ".cols{grid-template-columns:repeat(var(--cols,2),minmax(0,1fr))}"
        ".item,.tile{display:flex;flex-direction:column;min-height:0;height:100%;border-radius:20px;"
        "padding:24px 22px 22px;background:#fff;border:1px solid #d6deea}"
        ".page.is-dark .item,.page.is-dark .tile{background:rgba(255,255,255,.1);border-color:rgba(255,255,255,.16)}"
        ".tile.is-on,.item.is-on{background:#1a62f2;border-color:#1a62f2;color:#fff}"
        ".idx{font-size:15px;font-weight:700;letter-spacing:1.4px;text-transform:uppercase;color:#1a62f2}"
        ".page.is-dark .idx,.tile.is-on .idx,.item.is-on .idx{color:#9ec0ff}"
        ".mark{margin-top:auto;font-size:92px;line-height:.9;font-weight:700;letter-spacing:-3px;opacity:.14}"
        ".item h2,.tile h2{margin:12px 0 0;font-size:28px;line-height:1.15;letter-spacing:-.35px}"
        ".bars{margin-top:22px;flex:1;display:flex;flex-direction:column;justify-content:space-evenly;gap:10px}"
        ".bar{height:11px;border-radius:999px;background:#d6deea;width:100%;flex:0 0 11px}"
        ".bar:nth-child(2n){width:86%}.bar:nth-child(3n){width:72%}.bar:nth-child(4n){width:78%}"
        ".tile.is-on .bar,.item.is-on .bar,.page.is-dark .bar{background:rgba(255,255,255,.28)}"
        "</style></head><body>" + "".join(pages) + "</body></html>"
    )


def _carousel_slide(slide: dict, index: int, total: int) -> str:
    visual = (slide.get("visual") or "statement").strip()
    dark = visual == "statement" or (slide.get("layout") == "cta")
    tone = "is-dark" if dark else "is-light"
    logo = "{{brand_on_dark}}" if dark else "{{brand_on_light}}"
    kicker = {
        "hook": "Agent Monitoring",
        "problem": "The gap",
        "steps": "How it works",
        "proof": "What you get",
        "benefit": "Why it matters",
        "cta": "Get started",
    }.get(slide.get("layout") or "", _module())
    points = [p for p in (slide.get("points") or []) if str(p).strip()]
    visual_html = _carousel_visual(visual, slide.get("body") or "", points, slide.get("headline") or "")
    return (
        f'<section class="page {tone}">'
        f'<div class="chrome"><img src="{logo}" alt="{{{{brand_name}}}}"><span class="kicker">{_e(kicker)}</span></div>'
        f'<div class="copy"><h1>{_e(slide.get("headline"))}</h1>'
        f'<p class="dek">{_e(slide.get("body"))}</p></div>'
        f'<div class="visual">{visual_html}</div>'
        f'<footer class="foot"><img src="{{{{brand_on_dark}}}}" alt="{{{{brand_name}}}}"><span>{index} / {total}</span></footer>'
        f"</section>"
    )


BARS = "".join('<div class="bar"></div>' for _ in range(8))


def _carousel_visual(kind: str, body: str, points: list[str], headline: str) -> str:
    if kind == "steps" and points:
        n = min(len(points), 3)
        items = []
        for i, point in enumerate(points[:n], start=1):
            on = " is-on" if i == 2 else ""
            filler = f'<div class="bars">{BARS}</div>' if "prompt" in headline.casefold() else f'<div class="mark">{i:02d}</div>'
            items.append(
                f'<div class="item{on}"><div class="idx">{i:02d}</div><h2>{_e(point)}</h2>{filler}</div>'
            )
        return f'<div class="fill"><div class="steps-h" style="--n:{n}">{"".join(items)}</div></div>'
    if kind in {"contrast", "spotlight"} and points:
        cols = min(len(points), 3)
        tiles = []
        for i, point in enumerate(points, start=1):
            on = " is-on" if i == (2 if cols > 1 else 1) else ""
            filler = f'<div class="bars">{BARS}</div>' if "prompt" in headline.casefold() else f'<div class="mark">{i:02d}</div>'
            tiles.append(
                f'<div class="tile{on}"><div class="idx">{i:02d}</div><h2>{_e(point)}</h2>{filler}</div>'
            )
        return f'<div class="fill"><div class="cols" style="--cols:{cols}">{"".join(tiles)}</div></div>'
    pull = points[0] if points else body
    chips = "".join(f'<div class="chip">{_e(point)}</div>' for point in points)
    return (
        f'<div class="fill is-quote"><div class="quote"><strong>{_e(pull)}</strong>'
        f'{f"<div class=chips>{chips}</div>" if chips else ""}</div></div>'
    )


def render_locked(key: str, content: dict, folder: Path, set_step=lambda *a: None):
    folder.mkdir(parents=True, exist_ok=True)
    if key in DOCUMENTS:
        return _render_document(key, content, folder)
    if key not in PAGE:
        raise ValueError(f"{key} has no locked layout.")
    from app.services.marketing_design import render_design
    last = "Layout could not fit the approved copy."
    sizes = (13, 12, 11, 10) if key != "linkedin_carousel" else (28, 24, 22, 18)
    for attempt, size in enumerate(sizes):
        source = layout_html(key, content, size)
        try:
            return render_design(key, content, source, folder)
        except ValueError as exc:
            last = str(exc)
            if "omitted or rewrote" in last:
                raise
            set_step(key, {"status": "running", "design_repair_attempt": attempt + 1})
    raise ValueError(last)


def _render_document(key: str, content: dict, folder: Path):
    from playwright.sync_api import sync_playwright
    from app.services.marketing_design import prepare_design
    import fitz

    source = prepare_design(document_html(content, "Release notes" if key == "release_notes" else "Case study"), embed_fonts=True)
    (folder / f"{key}.html").write_text(source, encoding="utf-8")
    pdf_path = folder / f"{key}.pdf"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_content(source, wait_until="load")
            page.pdf(path=str(pdf_path), format="A4", print_background=True, prefer_css_page_size=True)
        finally:
            browser.close()
    with fitz.open(pdf_path) as document:
        visible = "\n".join(page.get_text() for page in document)
    missing = _missing_copy(key, content, visible)
    if missing:
        raise ValueError("Document omitted approved copy: " + "; ".join(missing[:4]))
    return [(f"{key}.html", "text/html"), (f"{key}.pdf", "application/pdf")]

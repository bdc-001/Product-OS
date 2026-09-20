"""JSON component library → HTML for artifact PDFs."""

from __future__ import annotations

import base64
import html
import re
from pathlib import Path

PLACEHOLDER_RE = re.compile(r"LOGO_DARK|LOGO_LIGHT|SCREENSHOT_[A-Za-z0-9._-]+")
_STOPWORDS = {"the", "a", "an", "this", "that", "your"}

FONT_DIR = Path(__file__).resolve().parents[1] / "fonts"
STATIC = Path(__file__).resolve().parents[1] / "static" / "artifacts"
LOGO_DIR = STATIC / "logos"
BLOCK_TYPES = (
    "stat_band",
    "cards",
    "table",
    "flow",
    "steps",
    "callout",
    "quote",
    "comparison",
    "why",
    "bold_lead_list",
    "panel",
)
STATUS = {"success", "warning", "error", "info"}


def render_artifact_html(deck: dict) -> str:
    raw_html = str((deck or {}).get("html") or "").strip()
    if raw_html:
        return prepare_brief_html(raw_html)
    fmt = str((deck or {}).get("format") or "deck").strip().lower()
    if fmt == "brief":
        return _brief(deck)
    return _deck(deck)


def logo_data_uri(*, dark: bool) -> str:
    name = "convin-lockup-dark.svg" if dark else "convin-lockup-light.svg"
    path = LOGO_DIR / name
    if not path.is_file():
        return ""
    return "data:image/svg+xml;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def file_data_uri(path: Path, *, max_side: int = 960) -> str:
    """JPEG data URI for a real product capture (print + Anthropic)."""
    from io import BytesIO

    from PIL import Image

    img = Image.open(path).convert("RGB")
    img.thumbnail((max_side, int(max_side * 9 / 16) or max_side))
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=82)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def ref_data_uri(path: Path, *, max_side: int = 1400) -> str:
    """JPEG data URI for a portrait A4 craft reference. Keep the page aspect."""
    from io import BytesIO

    from PIL import Image

    img = Image.open(path).convert("RGB")
    img.thumbnail((max_side, max_side))
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=86)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def cell_tokens(text: str) -> tuple[str, ...]:
    raw = html.unescape(re.sub(r"<[^>]+>", " ", str(text or "")))
    return tuple(tok for tok in re.findall(r"[a-z0-9]+", raw.lower()) if tok not in _STOPWORDS)


def same_referent(values: list[str]) -> bool:
    """True when every cell names the same thing, including 'Test Agent' vs 'The agent'."""
    stripped = [str(v or "").strip() for v in values]
    if len(stripped) < 2:
        return False
    if all(not v for v in stripped):
        return True
    keys = [cell_tokens(v) for v in stripped]
    if any(not k for k in keys):
        return False
    uniq = set(keys)
    if len(uniq) == 1:
        return True
    longest = max(uniq, key=len)
    if not longest:
        return False
    return all(k == longest[-len(k) :] or longest == k[-len(longest) :] for k in uniq)


def drop_constant_table_columns(
    headers: list[str],
    rows: list[dict],
) -> tuple[list[str], list[dict], str]:
    """Drop columns whose cells are the same referent. Fold the constant into a caption."""
    if not headers or len(rows) < 2:
        return headers, rows, ""
    width = len(headers)
    drop: list[int] = []
    folded: list[str] = []
    for idx in range(width):
        values = []
        for row in rows:
            cells = list(row.get("cells") or [])
            values.append(str(cells[idx] if idx < len(cells) else ""))
        if not same_referent(values):
            continue
        drop.append(idx)
        representative = next((v.strip() for v in values if str(v).strip()), headers[idx])
        folded.append(representative)
    keep = [i for i in range(width) if i not in set(drop)]
    if not drop or not keep:
        return headers, rows, ""
    new_headers = [headers[i] for i in keep]
    new_rows = []
    for row in rows:
        cells = list(row.get("cells") or [])
        flags = list(row.get("flags") or [])
        new_rows.append(
            {
                "cells": [cells[i] if i < len(cells) else "" for i in keep],
                "flags": [flags[i] if i < len(flags) else "" for i in keep],
            }
        )
    caption = "From " + " · ".join(folded)
    return new_headers, new_rows, caption


def collapse_constant_tables(markup: str) -> str:
    def repl(match: re.Match[str]) -> str:
        table = match.group(0)
        th_tags = re.findall(r"<th\b[^>]*>[\s\S]*?</th>", table, flags=re.I)
        trs = re.findall(r"<tr\b[^>]*>([\s\S]*?)</tr>", table, flags=re.I)
        body_tds: list[list[str]] = []
        for tr in trs:
            if re.search(r"<th\b", tr, flags=re.I):
                continue
            tds = re.findall(r"<td\b[^>]*>[\s\S]*?</td>", tr, flags=re.I)
            if tds:
                body_tds.append(tds)
        headers = [_strip_tags(tag) for tag in th_tags]
        if not headers or len(body_tds) < 2:
            return table
        rows = [{"cells": [_strip_tags(td) for td in tds], "flags": []} for tds in body_tds]
        _, _, caption = drop_constant_table_columns(headers, rows)
        if not caption:
            return table
        keep = []
        dropped = set()
        for idx in range(len(headers)):
            values = [str((row.get("cells") or [""])[idx] if idx < len(row.get("cells") or []) else "") for row in rows]
            if same_referent(values):
                dropped.add(idx)
            else:
                keep.append(idx)
        if not keep:
            return table
        new_thead = "".join(th_tags[i] for i in keep if i < len(th_tags))
        body_out = []
        for tds in body_tds:
            body_out.append("<tr>" + "".join(tds[i] for i in keep if i < len(tds)) + "</tr>")
        open_tag = re.match(r"<table\b[^>]*>", table, flags=re.I)
        start = open_tag.group(0) if open_tag else "<table>"
        cap = f"<caption>{html.escape(caption)}</caption>"
        return f"{start}{cap}<thead><tr>{new_thead}</tr></thead><tbody>{''.join(body_out)}</tbody></table>"

    return re.sub(r"<table\b[\s\S]*?</table>", repl, markup, flags=re.I)


def _strip_tags(markup: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", markup or "")).strip()


def assert_placeholders_resolved(markup: str) -> None:
    stripped = re.sub(r"<style\b[^>]*>[\s\S]*?</style>", " ", markup or "", flags=re.I)
    leftover = sorted(set(PLACEHOLDER_RE.findall(stripped)))
    if leftover:
        raise RuntimeError(f"unresolved placeholders: {leftover}")
    bad = []
    for src in re.findall(r"<img\b[^>]*?\ssrc=['\"]([^'\"]+)['\"]", stripped, flags=re.I):
        if not str(src).startswith("data:"):
            bad.append(src)
    if bad:
        raise RuntimeError(f"unresolved img src: {bad}")


TOKENS_CSS = """
:root{--s1:8px;--s2:12px;--s3:16px;--s4:24px;--s5:32px;--s6:48px;--radius:16px;--border:1px solid #3F3F3F}
.steps{grid-auto-rows:1fr}
.ways{align-items:stretch}
.ways .way{display:flex;flex-direction:column}
.ways .way .tail{margin-top:auto}
""".strip()


def _inject_style(html: str, css: str, marker: str = "data-brief-tokens") -> str:
    if not css or marker in (html or ""):
        return html
    snippet = f"<style {marker}>{css}</style>"
    lower = (html or "").lower()
    at = lower.rfind("</head>")
    if at >= 0:
        return html[:at] + snippet + html[at:]
    at = lower.find("<body")
    if at >= 0:
        return html[:at] + snippet + html[at:]
    return snippet + html


def prepare_brief_html(raw: str, placeholders: dict[str, str] | None = None) -> str:
    """Sanitize Opus HTML. Do not rewrite markup or inject a stylesheet."""
    _ = placeholders
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:html)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    text = re.sub(r"<script[\s\S]*?</script>", "", text, flags=re.I)
    text = re.sub(r"\son\w+\s*=", " data-dropped=", text, flags=re.I)
    if "<html" not in text.lower():
        raise RuntimeError("docs compose returned an HTML fragment, not a document")
    assert_placeholders_resolved(text)
    return text


def prepare_fable_html(raw: str, placeholders: dict[str, str] | None = None) -> str:
    return prepare_brief_html(raw, placeholders=placeholders)


def _font_css() -> str:
    faces = []
    for weight, name in ((400, "Inter-Regular.ttf"), (500, "Inter-Medium.ttf")):
        path = FONT_DIR / name
        if not path.is_file():
            continue
        b64 = base64.b64encode(path.read_bytes()).decode("ascii")
        faces.append(
            f'@font-face{{font-family:"Inter";src:url(data:font/ttf;base64,{b64}) format("truetype");'
            f"font-weight:{weight};font-display:block;}}"
        )
    return "\n".join(faces)


def _sheet(name: str) -> str:
    path = STATIC / name
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _logo_img(*, dark: bool, cls: str = "lockup") -> str:
    name = "convin-lockup-dark.svg" if dark else "convin-lockup-light.svg"
    path = LOGO_DIR / name
    if not path.is_file():
        return '<span class="lockup">CONVIN</span>'
    uri = "data:image/svg+xml;base64," + base64.b64encode(path.read_bytes()).decode("ascii")
    variant = "dark" if dark else "light"
    return f'<img class="{cls} lockup--{variant}" src="{uri}" alt="CONVIN">'


def _esc(text) -> str:
    return html.escape(_safe(text), quote=True)


def _safe(text) -> str:
    raw = str(text or "")
    return (
        raw.replace("→", " / ")
        .replace("▸", " / ")
        .replace("►", " / ")
        .replace("▯", " / ")
        .replace("•", " / ")
        .strip()
    )


def _inline(text) -> str:
    """Escape text, turning slash-paths into CSS chevrons so arrows are not tofu."""
    raw = _safe(text)
    parts = [part.strip() for part in raw.split(" / ") if part.strip()]
    if 2 <= len(parts) <= 6 and all(len(part) <= 42 for part in parts):
        chev = '<i class="chev" aria-hidden="true"></i>'
        return chev.join(html.escape(part) for part in parts)
    return html.escape(raw)


def _deck(deck: dict) -> str:
    pages = list((deck or {}).get("pages") or [])
    total = max(len(pages), 1)
    module = _esc((deck or {}).get("module") or "Activate")
    slides = []
    for i, page in enumerate(pages, start=1):
        tone = str(page.get("tone") or "light").lower()
        if tone not in {"cover", "light", "close"}:
            tone = "light"
        heading_tag = "h1" if tone in {"cover", "close"} else "h2"
        heading = _esc(page.get("heading") or "")
        lede = _esc(page.get("lede") or "")
        eyebrow = _esc(page.get("eyebrow") or "")
        blocks = "".join(_block_html(block, "deck") for block in (page.get("blocks") or []) if isinstance(block, dict))
        head = (
            f'{f"<div class=eyebrow>{eyebrow}</div>" if eyebrow else ""}'
            f'{f"<{heading_tag}>{heading}</{heading_tag}>" if heading else ""}'
            f'{"<div class=rule></div>" if heading else ""}'
            f'{f"<p class=lede>{lede}</p>" if lede else ""}'
        )
        slides.append(
            f'<section class="slide slide--{tone}">'
            f'<div class="pagenum">{i:02d}  /  {total:02d}</div>'
            f'<div class="canvas">{head}{blocks}</div>'
            f'<div class="footer">{_logo_img(dark=tone in {"cover", "close"}, cls="lockup lockup--foot")}'
            f'<span class="footer__module">{module}</span></div>'
            f"</section>"
        )
    return _wrap("deck.css", "".join(slides) or '<section class="slide slide--light"></section>')


def _brief(deck: dict) -> str:
    pages = list((deck or {}).get("pages") or [])
    total = max(len(pages), 1)
    module = _esc((deck or {}).get("module") or "Sense")
    title = _esc((deck or {}).get("title") or "")
    out = []
    for i, page in enumerate(pages, start=1):
        tone = str(page.get("tone") or "light").lower()
        heading = _esc(page.get("heading") or "")
        lede = _esc(page.get("lede") or "")
        eyebrow = _esc(page.get("eyebrow") or "")
        kicker = _esc(page.get("kicker") or "")
        is_hero = tone in {"cover", "hero"} or i == 1
        raw_blocks = [block for block in (page.get("blocks") or []) if isinstance(block, dict)]
        bleed = ""
        body_blocks = list(raw_blocks)
        if is_hero and body_blocks and str(body_blocks[0].get("type") or "").lower() == "stat_band":
            bleed = _block_html(body_blocks.pop(0), "brief")
        focused = False
        body_html = []
        if heading and not is_hero:
            body_html.append(
                f'<div class="sec"><div class="sec__h">{heading}</div>'
                f'{f"<div class=sec__note>{kicker or eyebrow}</div>" if (kicker or eyebrow) else ""}</div>'
            )
            if lede:
                body_html.append(f'<p class="prose">{lede}</p>')
        for block in body_blocks:
            kind = str(block.get("type") or "").strip().lower()
            use_focus = (not focused) and kind in {"why", "cards"}
            body_html.append(_block_html(block, "brief", focus=use_focus))
            if use_focus:
                focused = True
        masthead = (
            f'<div class="masthead">{_logo_img(dark=is_hero, cls="masthead__logo")}'
            f'<span class="masthead__label">{eyebrow or module.upper() + " BRIEF"}</span></div>'
        )
        hero = ""
        if is_hero:
            hero = (
                f'<div class="hero">{masthead}'
                f'<div class="hero__badges"><span class="pill">{module.upper()}</span>'
                f'<span class="hero__released">{_esc(page.get("released") or "")}</span></div>'
                f'{f"<h1 class=hero__title>{heading}</h1>" if heading else ""}'
                f'{f"<p class=hero__lede>{lede}</p>" if lede else ""}'
                f"</div>"
            )
            masthead = ""
        page_cls = "page page--hero" if is_hero else "page page--plain"
        out.append(
            f'<section class="{page_cls}">{hero}{bleed}'
            f'<div class="page__body">{masthead}{"".join(body_html)}</div>'
            f'<div class="foot"><span class="foot__note">{module} — {title}</span>'
            f"<span>Page {i} of {total}</span></div></section>"
        )
    return _wrap("brief.css", "".join(out) or '<section class="page page--plain"></section>')


def _wrap(css_name: str, body: str) -> str:
    return (
        "<!doctype html><html lang=en><head><meta charset=utf-8>"
        f"<style>{_font_css()}\n{_sheet(css_name)}</style></head>"
        f"<body>{body}</body></html>"
    )


def _block_html(block: dict, fmt: str, focus: bool = False) -> str:
    kind = str(block.get("type") or "").strip().lower()
    if kind == "stat_band":
        items = [item for item in (block.get("items") or []) if isinstance(item, dict)]
        if not items:
            return ""
        cells = "".join(
            f'<div class="stat"><div class="stat__value">{_esc(item.get("value"))}</div>'
            f'<div class="stat__label">{_esc(item.get("label"))}</div></div>'
            for item in items[:4]
        )
        return f'<div class="stat-band">{cells}</div>'
    if kind == "cards":
        items = [item for item in (block.get("items") or []) if isinstance(item, dict) and (_safe(item.get("lead")) or _safe(item.get("text")))]
        if not items:
            return ""
        cols = int(block.get("columns") or (3 if len(items) == 3 else 2))
        cols = 4 if cols not in {2, 3, 4} else cols
        cards = []
        for i, item in enumerate(items[:4]):
            accent = " is-focus" if i == 0 and fmt == "brief" and focus else ""
            rule = "" if fmt == "brief" else '<div class="rule rule--sm"></div>'
            cards.append(
                f'<article class="card{accent}">'
                f'<div class="card__lead">{_esc(item.get("lead"))}</div>{rule}'
                f'<p class="card__text">{_inline(item.get("text"))}</p></article>'
            )
        return f'<div class="cards cards--{min(cols, len(items))}">{"".join(cards)}</div>'
    if kind == "table":
        headers = [str(h) for h in (block.get("headers") or []) if _safe(h)]
        rows = [row for row in (block.get("rows") or []) if isinstance(row, dict)]
        caption = str(block.get("heading") or block.get("caption") or "").strip()
        headers, rows, folded = drop_constant_table_columns(headers, rows)
        if folded:
            caption = f"{caption} — {folded}".strip(" —") if caption else folded
        if not headers or not rows:
            return ""
        head = "".join(f"<th>{_esc(h)}</th>" for h in headers)
        body = []
        for row in rows[:8]:
            cells = list(row.get("cells") or [])
            flags = list(row.get("flags") or [])
            tds = []
            for idx, cell in enumerate(cells[: len(headers)]):
                flag = str(flags[idx] if idx < len(flags) else "").lower()
                if fmt == "brief":
                    mapped = {"success": "v-yes", "error": "v-no", "warning": "v-mid", "info": "tok"}.get(flag, "")
                    cls = f' class="{mapped}"' if mapped else ""
                else:
                    cls = f' class="is-{flag}"' if flag in STATUS else ""
                tds.append(f"<td{cls}>{_inline(cell)}</td>")
            body.append(f"<tr>{''.join(tds)}</tr>")
        cap = f"<caption>{_esc(caption)}</caption>" if caption else ""
        return f'<table class="matrix">{cap}<thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table>'
    if kind == "flow":
        items = [item for item in (block.get("items") or []) if isinstance(item, dict)]
        if len(items) < 2:
            return ""
        bits = []
        for i, item in enumerate(items[:5], start=1):
            bits.append(
                f'<div class="flow__item"><div class="flow__dot">{i}</div>'
                f'<div class="flow__lead">{_esc(item.get("lead"))}</div>'
                f'<p class="flow__text">{_inline(item.get("text"))}</p></div>'
            )
        return f'<div class="flow">{"".join(bits)}</div>'
    if kind == "steps":
        items = [_safe(item) for item in (block.get("items") or [])]
        items = [item for item in items if item]
        if not items:
            return ""
        if fmt == "brief":
            rows = "".join(
                f'<div class="step"><div class="step__n">{i + 1:02d}</div>'
                f'<div class="step__t">{_inline(item)}</div></div>'
                for i, item in enumerate(items[:6])
            )
            return f'<div class="steps">{rows}</div>'
        rows = "".join(
            f'<div class="nav-step"><div class="nav-step__num">{i + 1:02d}</div>'
            f'<div class="nav-step__text">{_inline(item)}</div></div>'
            for i, item in enumerate(items[:6])
        )
        return f'<div class="nav-steps">{rows}</div>'
    if kind == "callout":
        statement = _esc(block.get("statement") or block.get("lead") or "")
        support_raw = block.get("support") or block.get("text") or ""
        if not statement:
            return ""
        kicker = _esc(block.get("kicker") or "")
        if fmt == "brief":
            return (
                f'<aside class="panel">{f"<div class=panel__label>{kicker}</div>" if kicker else ""}'
                f'<div class="panel__grid"><p><b>{statement}</b>'
                f'{f" {_inline(support_raw)}" if _safe(support_raw) else ""}</p></div></aside>'
            )
        return (
            f'<aside class="callout">{f"<div class=callout__kicker>{kicker}</div>" if kicker else ""}'
            f'<div class="callout__statement">{statement}</div>'
            f'{f"<p class=callout__support>{_inline(support_raw)}</p>" if _safe(support_raw) else ""}</aside>'
        )
    if kind == "quote":
        text = _esc(block.get("text") or "")
        return f'<p class="quote">{text}</p>' if text else ""
    if kind == "comparison":
        left = block.get("left") if isinstance(block.get("left"), dict) else {}
        right = block.get("right") if isinstance(block.get("right"), dict) else {}
        return f'<div class="split">{_split_col(left)}{_split_col(right)}</div>'
    if kind == "why":
        heading = _esc(block.get("heading") or "Why you need this")
        risk = _inline(block.get("risk") or block.get("text") or "")
        items = [item for item in (block.get("items") or []) if isinstance(item, dict) and (_safe(item.get("lead")) or _safe(item.get("text")))]
        if fmt == "brief":
            cards = []
            for i, item in enumerate(items[:3]):
                accent = " is-focus" if i == 0 and focus else ""
                cards.append(
                    f'<article class="card{accent}">'
                    f'<div class="card__lead">{_esc(item.get("lead"))}</div>'
                    f'<p class="card__text">{_inline(item.get("text"))}</p></article>'
                )
            cols = min(len(items), 3) or 1
            card_row = f'<div class="cards cards--{cols}">{"".join(cards)}</div>' if cards else ""
            return (
                f'<div class="sec"><div class="sec__h">{heading}</div></div>'
                f'{f"<p class=prose>{risk}</p>" if risk else ""}'
                f"{card_row}"
            )
        cards = "".join(
            f'<article class="card"><div class="card__lead">{_esc(item.get("lead"))}</div>'
            f'<div class="rule rule--sm"></div>'
            f'<p class="card__text">{_inline(item.get("text"))}</p></article>'
            for item in items[:3]
        )
        cols = min(len(items), 3) or 1
        card_row = f'<div class="cards cards--{cols}">{cards}</div>' if cards else ""
        return (
            f'<section class="why"><div class="why__heading">{heading}</div>'
            f'{f"<p class=why__risk>{risk}</p>" if risk else ""}'
            f"{card_row}"
            f"</section>"
        )
    if kind == "bold_lead_list":
        items = [item for item in (block.get("items") or []) if isinstance(item, dict) and (_safe(item.get("lead")) or _safe(item.get("text")))]
        if not items:
            return ""
        cols = int(block.get("columns") or (2 if len(items) >= 4 else 1))
        cols = 2 if cols != 1 else 1
        if fmt == "brief":
            kicker = _esc(block.get("kicker") or block.get("heading") or "")
            rows = "".join(
                f'<div class="leads__item"><b>{_esc(item.get("lead"))}</b> {_inline(item.get("text"))}</div>'
                for item in items[:8]
            )
            cls = "leads" if cols == 2 else "leads leads--1"
            head = f'<div class="leads__head">{kicker}</div>' if kicker else ""
            return f"{head}<div class=\"{cls}\">{rows}</div>"
        rows = "".join(
            f'<div class="lead-item"><div class="lead-item__lead">{_esc(item.get("lead"))}</div>'
            f'<p class="lead-item__text">{_inline(item.get("text"))}</p></div>'
            for item in items[:8]
        )
        return f'<div class="lead-list lead-list--{cols}">{rows}</div>'
    if kind == "panel":
        items = [item for item in (block.get("items") or []) if isinstance(item, dict) and (_safe(item.get("lead")) or _safe(item.get("text")))]
        kicker = _esc(block.get("kicker") or "")
        statement = _esc(block.get("statement") or "")
        if not items and not statement:
            return ""
        cols = int(block.get("columns") or (2 if len(items) >= 2 else 1))
        if cols not in {1, 2, 4}:
            cols = 2 if len(items) >= 2 else 1
        if fmt == "brief":
            cells = "".join(
                f"<p><b>{_esc(item.get('lead'))}</b> {_inline(item.get('text'))}</p>"
                for item in items[:4]
            )
            grid = "panel__grid" if cols != 1 and len(items) > 1 else "panel__grid panel__grid--1"
            label = f'<div class="panel__label">{kicker}</div>' if kicker else ""
            grid_html = f'<div class="{grid}">{cells}</div>' if cells else ""
            extra = f"<p><b>{statement}</b></p>" if statement and not cells else ""
            return f'<aside class="panel">{label}{grid_html}{extra}</aside>'
        cells = "".join(
            f'<div class="panel__cell"><div class="panel__lead">{_esc(item.get("lead"))}</div>'
            f'<p class="panel__text">{_inline(item.get("text"))}</p></div>'
            for item in items[:4]
        )
        return (
            f'<aside class="panel panel--{cols}">'
            f'{f"<div class=panel__kicker>{kicker}</div>" if kicker else ""}'
            f'{f"<div class=panel__statement>{statement}</div>" if statement else ""}'
            f'{f"<div class=panel__grid>{cells}</div>" if cells else ""}'
            f"</aside>"
        )
    return ""


def _split_col(col: dict) -> str:
    items = [item for item in (col.get("items") or []) if isinstance(item, dict)]
    body = "".join(
        f'<div class="split__lead">{_esc(item.get("lead"))}</div>'
        f'<p class="split__text">{_inline(item.get("text"))}</p>'
        for item in items[:6]
    )
    kicker = _esc(col.get("heading") or "")
    return f'<div>{f"<div class=split__kicker>{kicker}</div>" if kicker else ""}{body}</div>'

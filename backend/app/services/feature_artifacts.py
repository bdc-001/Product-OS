"""Per-feature marketing artifacts.

A4 brief: Opus (medium) writes a prose description, Opus (xhigh) designs
HTML, then Opus (medium) polishes spacing and UI. Python sanitizes scripts
and prints the HTML to PDF without clipping page height.
"""

from __future__ import annotations

import json
import logging
import re
from difflib import SequenceMatcher
from pathlib import Path

from app.clients.llm import LLMJsonError, chat_json, model_for
from app.config import ROOT
from app.services.artifact_html import (
    BLOCK_TYPES,
    drop_constant_table_columns,
    file_data_uri,
    logo_data_uri,
    prepare_brief_html,
    ref_data_uri,
    render_artifact_html,
    _sheet,
)
from app.services.artifact_pdf import html_to_pdf, log_page_fill, measure_page_fill
from app.services.gdrive import drive_configured, upload_pdf
from app.services.prompts import with_preamble

log = logging.getLogger(__name__)
ARTIFACT_DIR = ROOT / "data" / "feature_artifacts"
_DESIGN_REF_DIR = Path(__file__).resolve().parents[1] / "static" / "artifacts" / "references"

DECK_EXEMPLAR = {
    "title": "Revamped WhatsApp Analytics",
    "module": "Activate",
    "format": "deck",
    "pages": [
        {
            "tone": "cover",
            "eyebrow": "Activate  ·  Release artifact",
            "heading": "See whether WhatsApp campaigns are actually landing.",
            "lede": "You can read delivery, reads, replies, and at-risk leads in one Activate view.",
            "blocks": [],
        },
        {
            "tone": "light",
            "eyebrow": "Release artifact",
            "heading": "Why it matters",
            "lede": "",
            "blocks": [
                {
                    "type": "stat_band",
                    "items": [
                        {"value": "4", "label": "Funnel stages"},
                        {"value": "Rates", "label": "Vs previous window"},
                        {"value": "CSV", "label": "Blocked-lead export"},
                    ],
                },
                {
                    "type": "cards",
                    "columns": 3,
                    "items": [
                        {"lead": "The blind spot", "text": "Messages go out, but you cannot see where delivery stalls."},
                        {"lead": "Who it is for", "text": "Campaign managers and operations running WhatsApp in Activate."},
                        {"lead": "What changes", "text": "Funnel, rates, templates, and at-risk leads sit in one view."},
                    ],
                },
            ],
        },
        {
            "tone": "light",
            "heading": "How engagement reads",
            "blocks": [
                {
                    "type": "flow",
                    "items": [
                        {"lead": "Sent", "text": "Messages that left the campaign."},
                        {"lead": "Delivered", "text": "Messages that reached the lead."},
                        {"lead": "Read", "text": "Messages the lead opened."},
                        {"lead": "Responded", "text": "Leads who replied."},
                    ],
                }
            ],
        },
        {
            "tone": "light",
            "heading": "Where to open it",
            "blocks": [
                {
                    "type": "steps",
                    "items": [
                        "Open Campaign Analytics or Analytics in Activate.",
                        "Open WhatsApp Analytics.",
                        "Pick a date range and read the funnel.",
                    ],
                }
            ],
        },
        {
            "tone": "close",
            "heading": "One view. The drop-off is visible.",
            "lede": "Judge reach, then act on blocked and degraded leads.",
            "blocks": [],
        },
    ],
}

BRIEF_EXEMPLAR = {
    "title": "PII masking",
    "module": "Sense",
    "format": "brief",
    "pages": [
        {
            "tone": "hero",
            "eyebrow": "Security & data privacy brief",
            "released": "Released 2026",
            "heading": "Hide customer details from anyone who doesn't need to see them.",
            "lede": "Mask names, numbers, and other PII on screen, in reports, in transcripts, and in call audio.",
            "blocks": [
                {
                    "type": "stat_band",
                    "items": [
                        {"value": "4", "label": "Places data is hidden"},
                        {"value": "Field by field", "label": "You pick what gets hidden"},
                        {"value": "Nobody", "label": "Can unhide it, at any role"},
                    ],
                },
                {
                    "type": "why",
                    "heading": "Why you need this",
                    "risk": "If the wrong people can still see customer details, a single export becomes an incident.",
                    "items": [
                        {"lead": "Fewer people, less risk", "text": "Only the roles that need PII still see it."},
                        {"lead": "Audits ask for proof", "text": "You can show where hiding is on, and where it is permanent."},
                        {"lead": "Vendors keep working", "text": "Outside QA can review without taking home customer details."},
                    ],
                },
                {
                    "type": "table",
                    "headers": ["Surface", "What happens", "Applied at", "Can be undone?"],
                    "rows": [
                        {"cells": ["On screen", "Fields are hidden in the product UI", "View time", "Yes"], "flags": ["", "", "", "success"]},
                        {"cells": ["In reports", "Exports ship without the chosen fields", "Export time", "Yes"], "flags": ["", "", "", "success"]},
                        {"cells": ["In transcripts", "Tokens replace the original text", "Write time", "No"], "flags": ["", "", "", "error"]},
                        {"cells": ["In call audio", "Speech is masked in the recording", "Write time", "No"], "flags": ["", "", "", "error"]},
                    ],
                },
            ],
        },
        {
            "tone": "light",
            "heading": "Hiding data is one of four protections.",
            "kicker": "Defence in depth",
            "blocks": [
                {
                    "type": "steps",
                    "items": [
                        "Hiding data on screen, in files and in recordings",
                        "Encryption for data sent to and from Convin",
                        "Roles that limit who can do what",
                        "Controlled sign-in",
                    ],
                },
                {
                    "type": "bold_lead_list",
                    "columns": 2,
                    "items": [
                        {"lead": "Banking & insurance.", "text": "Reviewers see outcomes without taking home identities."},
                        {"lead": "Healthcare.", "text": "Clinical detail stays with people who need it."},
                        {"lead": "A real control, not a policy.", "text": "Masking is enforced in product."},
                        {"lead": "Safer exports.", "text": "Reports leave without the fields you hid."},
                    ],
                },
                {
                    "type": "panel",
                    "kicker": "What to know before you switch it on",
                    "columns": 2,
                    "items": [
                        {"lead": "Masking does not delete data.", "text": "Hidden fields still exist for roles that are allowed to see them."},
                        {"lead": "Nothing is on by default.", "text": "Switch it on per tenant, then set it up under Settings."},
                        {"lead": "Some hiding is permanent.", "text": "Transcript and audio masking cannot be undone later."},
                        {"lead": "Screen hiding can be reversed.", "text": "Turn the view-time control off if a role needs the fields again."},
                    ],
                },
            ],
        },
    ],
}

_RULES = """
You are the designer. You pick which components the evidence can support.
Do not fill a frozen slide list. Omit a component when evidence is missing. Do not pad.
Never invent metrics, percentages, screens, or product names. Prefer "you can".
Never write "confirm in product", "under the hood", APIs, git, flags, or engineering.
If `grounded_doc` is present, treat it as the source of truth. features_in_short is the feature list only.
Do not restate the same fact in two blocks on one page.

Allowed block types: stat_band, cards, table, flow, steps, callout, quote, comparison, why, bold_lead_list, panel.
A page is {tone, eyebrow, heading, lede, kicker, released, blocks[]}.
stat_band items: {value, label}. No two stats may share a value. Prefer three different claim types: a count, a mechanism, and an absolute. Each label completes the value into a sentence. Do not put table enumerations in the label. Do not use a file format as a stat unless that format is the argument.
cards items: {lead, text}. columns 2, 3, or 4. Cards argue why, never restating the table.
table: {headers, rows:[{cells, flags}]}. flags are success|warning|error|info|"". Table is what it does, not why it matters.
flow items: {lead, text} for a real sequence only.
steps items: strings. Write locations in prose ("Open WhatsApp Analytics, then set a date range"), never slash-separated click paths.
comparison: {left:{heading, items[]}, right:{...}}.
why: {heading, risk, items[{lead,text}]}. heading like "Why you need this". risk is the cost of doing nothing. items are reasons to care.
bold_lead_list: {columns: 1|2, items[{lead,text}]}. Bold lead, then a sentence. Two columns when you have 4 items.
panel: {kicker, columns: 1|2, items[{lead,text}]}. Dark caveat grid. columns=2 with 4 items is a 2x2.
callout: {kicker, statement, support}. quote: {text}.
ASCII only. Do not use arrows or missing-glyph symbols.
"""

ARTIFACT_PROMPT = with_preamble(
    "You write a customer-facing 16:9 Convin release artifact (widescreen PDF).\n"
    "This is NOT a Google Doc, NOT a how-to manual, NOT CSM training.\n"
    f"{_RULES}\n"
    "format must be \"deck\". 3 to 6 pages. First page tone=cover, last page tone=close, middle pages tone=light.\n"
    "Cover heading is an outcome sentence, not the feature name alone.\n"
    "The .canvas flex-centers blocks. Put a stat_band or table on a page when the evidence supports it.\n"
    "EXEMPLAR (copy this density and component mix; replace with THIS feature's facts):\n"
    f"{json.dumps(DECK_EXEMPLAR, indent=2)}\n"
)

ARTIFACT_CONTENT_PROMPT = """You write marketing copy for a Convin Sense feature.
Sense is the product. Do not brand this as Activate. The reader is a customer. Prefer "you can".

Write one detailed explanation of the feature from the evidence: what it is, why it matters, who it is for, how it works, how you use it, what to watch out for, and any facts you can ground. Be thorough. A later design pass will turn this prose into a layout.

Write continuous paragraphs only. No headings, no bullets, no numbered lists, no labeled sections, no JSON keys inside the description.

Do not invent stats, screens, or product names. Figures, counts, and percentages are optional and often unnecessary. Only include figures, counts, or percentages when they are in the evidence and they actually describe this feature. If they would be decorative, or the feature is about controls, rules, tools, or workflow rather than measured results, write without decorative numbers.

Never use em dashes (the long dash) or en dashes in the description. Use a comma, a colon, or a new sentence instead.

Return JSON:
{
  "title": "",
  "module": "Sense",
  "description": "detailed continuous explanation, paragraphs only"
}
"""

DESIGN_INSTRUCTIONS = _sheet("marketing-design.md")
ARTIFACT_BRIEF_PROMPT = DESIGN_INSTRUCTIONS

ARTIFACT_POLISH_PROMPT = """You finish a Convin Sense client marketing artifact. The reader is the customer.

You receive a complete HTML document. Keep every fact, sentence, logo data URI, and screenshot. Do not rewrite the story. Do not add claims. Do not drop sections.

Do not introduce em dashes or en dashes. If copy already uses a comma or colon, leave it.

Fix spacing and UI so it matches the design system below:
- Even vertical rhythm from one spacing scale. Never use justify-content: space-between, space-around, space-evenly, or margin-top: auto to eat leftover height.
- Each .page is 210mm wide, height: auto, overflow: visible. Never clip with overflow: hidden or a locked 1123px / 297mm height.
- Footer stays in document flow, with ≥40px of page background or a hard color change above it. Footer chrome is logo + page number only.
- Pale-blue wash highlights one important section. Parallel boxes keep their own opaque fills; bluish tones must not overlap across the gutter.
- Hairline strokes, 16–20px radius, Elevation 1 on most cards, one featured surface per page.
- Inter for body; display stack for headlines and stats.

Return a complete HTML document only. No JSON wrapper, no markdown fences, no commentary.

""" + DESIGN_INSTRUCTIONS

HOWTO_CAPTIONS = {
    "8.1": "Create / Configure",
    "8.2": "Enable / Attach / Activate",
    "8.3": "Day-to-Day Usage",
    "8.4": "Review Outcomes",
}


def feature_items(features_in_short: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for line in (features_in_short or "").splitlines():
        clean = line.replace("  [unverified]", "").strip()
        if not clean:
            continue
        if " — " in clean:
            lead, text = clean.split(" — ", 1)
        elif " - " in clean:
            lead, text = clean.split(" - ", 1)
        else:
            lead, text = clean, ""
        items.append({"lead": lead[:80].strip(), "text": text[:400].strip()})
    return items


def artifact_pdf_name(feature: str, fmt: str = "deck") -> str:
    safe = re.sub(r"[^A-Za-z0-9._ -]+", "", (feature or "Feature")).strip()
    safe = re.sub(r"\s+", " ", safe).strip(" ._")[:80] or "Feature"
    stem = re.sub(r"[\s_]*(artifact|brief)$", "", safe, flags=re.I).strip(" ._") or safe
    return f"{stem}_Brief.pdf" if fmt == "brief" else f"{stem}_Artifact.pdf"


def store_opus_compose(title: str, raw: dict | None, html: str) -> dict[str, str]:
    """Write Opus's compose JSON/HTML before sanitize or PDF print."""
    dest = Path(ARTIFACT_DIR)
    dest.mkdir(parents=True, exist_ok=True)
    stem = Path(artifact_pdf_name(title or "Feature", "brief")).stem
    json_path = dest / f"{stem}.opus.json"
    html_path = dest / f"{stem}.opus.html"
    payload = raw if isinstance(raw, dict) else {"html": html}
    json_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    html_path.write_text(html or "", encoding="utf-8")
    log.info("artifact opus stored json=%s html=%s chars=%s", json_path, html_path, len(html or ""))
    return {"json": str(json_path), "html": str(html_path)}


def grounded_from_doc(doc: dict | None) -> dict:
    if not isinstance(doc, dict):
        return {}
    sections = []
    for item in doc.get("sections") or []:
        if not isinstance(item, dict):
            continue
        heading = str(item.get("heading") or "").strip()
        blocks = []
        for block in item.get("blocks") or []:
            if not isinstance(block, dict):
                continue
            kind = str(block.get("type") or "").strip().lower()
            if kind in {"para", "h3"}:
                text = str(block.get("text") or "").strip()
                if text:
                    blocks.append({"type": kind, "text": text})
            elif kind in {"bullets", "numbered", "faq"}:
                items = block.get("items") or []
                if items:
                    blocks.append({"type": kind, "items": items})
            elif kind == "table":
                headers = block.get("headers") or []
                rows = block.get("rows") or []
                if headers and rows:
                    blocks.append({"type": "table", "headers": headers, "rows": rows})
        if heading and blocks:
            sections.append({"heading": heading, "blocks": blocks})
    return {
        "title": doc.get("title"),
        "intro": doc.get("intro"),
        "meta": doc.get("meta"),
        "highlights": doc.get("highlights"),
        "sections": sections,
    }


def sparse_from_evidence(title: str, features_in_short: str, fmt: str, doc: dict | None = None) -> dict:
    rows = feature_items(features_in_short)
    heading = (title or (rows[0]["lead"] if rows else "Feature")).strip()[:120]
    outcome = (rows[0]["text"] if rows else "").strip()
    module = "Activate" if any(tok in f"{heading} {features_in_short}".lower() for tok in ("activate", "whatsapp", "campaign")) else "Sense"
    cards = [{"lead": row["lead"], "text": row["text"]} for row in rows[:4] if row.get("lead")]
    blocks = [{"type": "cards", "columns": min(3, len(cards)) or 1, "items": cards}] if cards else []
    if fmt == "brief":
        pages = [
            {
                "tone": "hero",
                "eyebrow": f"{module} brief",
                "heading": outcome or heading,
                "lede": outcome,
                "blocks": blocks,
            }
        ]
    else:
        pages = [
            {"tone": "cover", "eyebrow": f"{module}  ·  Release artifact", "heading": outcome or heading, "lede": outcome, "blocks": []},
        ]
        if blocks:
            pages.append({"tone": "light", "heading": "What shipped", "blocks": blocks})
        pages.append({"tone": "close", "heading": heading, "lede": outcome, "blocks": []})
    _ = doc
    return {"title": heading, "module": module, "format": fmt, "pages": pages}


def clean_artifact(raw: dict, title: str, features_in_short: str, fmt: str) -> dict:
    heading = _must_fit(str((raw or {}).get("title") or title), 160) or (title or "Feature")
    module = _must_fit(str((raw or {}).get("module") or ""), 40)
    if module.lower() not in {"activate", "sense"}:
        module = "Activate" if "activate" in f"{heading} {features_in_short}".lower() else "Sense"
    pages = []
    for page in (raw or {}).get("pages") or []:
        if not isinstance(page, dict):
            continue
        tone = str(page.get("tone") or "light").strip().lower()
        if fmt == "brief" and tone in {"cover"}:
            tone = "hero"
        if fmt == "deck" and tone not in {"cover", "light", "close"}:
            tone = "light"
        blocks = [_clean_block(block) for block in (page.get("blocks") or [])]
        blocks = [block for block in blocks if block]
        blocks = _dedupe_page_blocks(blocks)
        cleaned = {
            "tone": tone,
            "eyebrow": _must_fit(str(page.get("eyebrow") or ""), 96),
            "heading": _must_fit(str(page.get("heading") or ""), 180),
            "lede": _must_fit(str(page.get("lede") or ""), 420),
            "kicker": _must_fit(str(page.get("kicker") or ""), 96),
            "released": _must_fit(str(page.get("released") or ""), 48),
            "blocks": blocks,
        }
        if cleaned["heading"] or cleaned["lede"] or cleaned["blocks"]:
            pages.append(cleaned)
    if not pages:
        return sparse_from_evidence(heading, features_in_short, fmt)
    return {"title": heading, "module": module, "format": fmt, "pages": pages[:8]}


def generate_artifact(
    *,
    title: str,
    features_in_short: str,
    branch: str = "",
    notes: str = "",
    doc: dict | None = None,
    fmt: str = "brief",
    screenshots: dict | list | None = None,
) -> dict:
    fmt = "brief" if fmt == "brief" else "deck"
    if fmt == "deck":
        return _generate_deck_artifact(
            title=title,
            features_in_short=features_in_short,
            branch=branch,
            notes=notes,
            doc=doc,
        )
    pack = _compose_content_pack(
        title=title,
        features_in_short=features_in_short,
        branch=branch,
        notes=notes,
        doc=doc,
    )
    shots = _real_screenshot_paths(screenshots)
    html, opus_files = _compose_brief_html(pack, shots)
    html = _polish_brief_html(html, str(pack.get("title") or title or "Feature"))
    heading = str(pack.get("title") or title or "Feature")[:160]
    module = "Sense"
    return {
        "title": heading,
        "module": module,
        "format": "brief",
        "html": html,
        "content": _feature_for_compose(pack),
        "stills": [str(path) for _, path in shots],
        "pages": [],
        "opus_json": opus_files.get("json") or "",
        "opus_html": opus_files.get("html") or "",
    }


def _generate_deck_artifact(
    *,
    title: str,
    features_in_short: str,
    branch: str,
    notes: str,
    doc: dict | None,
) -> dict:
    sparse = sparse_from_evidence(title, features_in_short, "deck", doc)
    try:
        raw = chat_json(
            surface="artifact",
            system=ARTIFACT_PROMPT,
            payload={
                "title": title,
                "branch": branch,
                "format": "deck",
                "features_in_short": features_in_short,
                "notes_excerpt": (notes or "")[:2000],
                "grounded_doc": grounded_from_doc(doc),
            },
            max_chars=24000,
            timeout=300,
            reasoning_effort="high",
        )
        log.info("artifact docs ok format=deck title=%s pages=%s", title, len((raw or {}).get("pages") or []))
        return clean_artifact(raw, title, features_in_short, "deck")
    except LLMJsonError as exc:
        log.exception("artifact heuristic fired format=deck title=%s err=%s", title, exc)
        return sparse
    except Exception as exc:
        log.exception("artifact heuristic fired format=deck title=%s err=%s", title, exc)
        return sparse


def _branch_evidence(
    title: str,
    features_in_short: str,
    branch: str,
    notes: str,
    doc: dict | None,
) -> dict:
    snap = None
    try:
        from app.database import SessionLocal
        from app.services.codebase import latest_snapshot

        db = SessionLocal()
        try:
            snap = latest_snapshot(db)
        finally:
            db.close()
    except Exception:
        log.exception("artifact content: could not load codebase snapshot")
    product = ""
    if snap is not None:
        live = f"{snap.live_summary or ''} {snap.branch or ''}"
        product = "Activate" if "activate" in live.lower() else "Sense"
    return {
        "title": title,
        "branch": branch or (getattr(snap, "branch", "") if snap else ""),
        "features_in_short": features_in_short,
        "notes_excerpt": (notes or "")[:3000],
        "product": product,
        "live_summary": (getattr(snap, "live_summary", None) or "")[:4000] if snap else "",
        "commits": (getattr(snap, "live_commits", None) or [])[:20] if snap else [],
        "files": (getattr(snap, "live_files", None) or [])[:30] if snap else [],
        "grounded_doc": grounded_from_doc(doc),
    }


def _compose_content_pack(
    *,
    title: str,
    features_in_short: str,
    branch: str,
    notes: str,
    doc: dict | None,
) -> dict:
    evidence = _branch_evidence(title, features_in_short, branch, notes, doc)
    try:
        raw = chat_json(
            surface="artifact_content",
            system=ARTIFACT_CONTENT_PROMPT,
            payload=evidence,
            max_chars=32000,
            timeout=180,
            reasoning_effort="medium",
        )
        pack = _clean_content_pack(raw, title, features_in_short)
        invented = len((raw or {}).get("screenshots") or []) if isinstance(raw, dict) else 0
        if invented:
            log.warning("artifact content dropped %s invented screenshot(s) title=%s", invented, title)
        log.info(
            "artifact content ok model=%s effort=medium title=%s description_chars=%s invented_shots_dropped=%s",
            model_for("artifact_content"),
            title,
            len(pack.get("description") or ""),
            invented,
        )
        return pack
    except LLMJsonError as exc:
        log.exception("artifact content failed title=%s err=%s", title, exc)
        return _sparse_content_pack(title, features_in_short)
    except Exception as exc:
        log.exception("artifact content failed title=%s err=%s", title, exc)
        return _sparse_content_pack(title, features_in_short)


def _prose_description(data: dict, title: str, features_in_short: str) -> str:
    text = str(
        data.get("description") or data.get("copy") or data.get("body") or data.get("narrative") or ""
    ).strip()
    if not text:
        bits = []
        for key in ("headline", "outcome", "lede", "story", "problem", "what_changes"):
            bit = str(data.get(key) or "").strip()
            if bit and bit not in bits:
                bits.append(bit)
        text = "\n\n".join(bits)
    if not text:
        rows = feature_items(features_in_short)
        parts = [f"{row['lead']}. {row['text']}".strip(". ").strip() for row in rows if row.get("lead") or row.get("text")]
        text = " ".join(parts) or title
    return text[:16000]


def _clean_content_pack(raw: dict, title: str, features_in_short: str) -> dict:
    data = raw if isinstance(raw, dict) else {}
    heading = str(data.get("title") or title).strip()[:160] or title
    return {
        "title": heading,
        "module": "Sense",
        "description": _prose_description(data, heading, features_in_short),
    }


def _sparse_content_pack(title: str, features_in_short: str) -> dict:
    heading = (title or "Feature").strip()[:120]
    return {
        "title": heading,
        "module": "Sense",
        "description": _prose_description({}, heading, features_in_short),
        "not_enough_evidence": "Content pass did not return a pack; using the feature list only.",
    }


def _feature_for_compose(pack: dict) -> dict:
    return dict(pack or {})


def _real_screenshot_paths(screenshots) -> list[tuple[str, Path]]:
    if not screenshots:
        return []
    rows: list[tuple[str, Path]] = []
    if isinstance(screenshots, dict):
        items = screenshots.items()
    else:
        items = [(Path(path).stem, path) for path in screenshots]
    for ref, raw in items:
        path = Path(raw)
        if not path.is_file():
            log.warning("artifact screenshot missing ref=%s path=%s", ref, path)
            continue
        rows.append((str(ref), path))
        if len(rows) >= 4:
            break
    return rows


def _data_uri_image_block(uri: str, name: str) -> dict | None:
    raw = str(uri or "").strip()
    if not raw.startswith("data:"):
        return None
    header, _, data = raw.partition(",")
    data = data.strip()
    if not data:
        return None
    lower = header.lower()
    if "svg" in lower:
        return None
    if "jpeg" in lower or "jpg" in lower:
        media = "image/jpeg"
    elif "png" in lower:
        media = "image/png"
    elif "gif" in lower:
        media = "image/gif"
    elif "webp" in lower:
        media = "image/webp"
    else:
        return None
    return {"media_type": media, "data": data, "name": name}


def _design_ref_sort_key(path: Path) -> tuple:
    stem = path.stem.lower()
    if "page-1" in stem:
        return (0, stem)
    if "page-2" in stem:
        return (1, stem)
    if "masthead" in stem:
        return (2, stem)
    if "approved" in stem:
        return (3, stem)
    return (9, stem)


def _design_ref_role(path: Path) -> str:
    stem = path.stem.lower()
    if "masthead" in stem:
        return (
            "Top masthead / dark hero close-up. Logo left, document label right, product pill, "
            "large left-aligned headline, lede, and audience line on a navy gradient. "
            "Do not copy that page's copy or dates."
        )
    if "approved" in stem:
        return (
            "Approved live A4 page 1 (Agent Testing). Match this density, type hierarchy, "
            "color blocking, card layout, footer, and visual weight. "
            "Do not copy that page's copy, dates, or claims."
        )
    page = "1" if "page-1" in stem else "2" if "page-2" in stem else path.stem
    return (
        f"A4 layout craft, page {page} of the reference spread. "
        "Match hero, split band, table, side-by-side panels, numbered flow, type, and whitespace. "
        "Do not copy that page's copy."
    )


def _design_ref_blocks() -> list[dict]:
    """Portrait A4 craft shots for compose. Vision only — not product screenshots."""
    folder = _DESIGN_REF_DIR
    if not folder.is_dir():
        return []
    paths = sorted(
        (
            path
            for path in folder.iterdir()
            if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
        ),
        key=_design_ref_sort_key,
    )
    rows: list[dict] = []
    for i, path in enumerate(paths[:4], start=1):
        try:
            uri = ref_data_uri(path)
        except Exception:
            log.exception("could not attach design reference %s", path)
            continue
        block = _data_uri_image_block(uri, f"design_ref_{i}")
        if not block:
            continue
        block["role"] = _design_ref_role(path)
        block["file"] = path.name
        rows.append(block)
    if rows:
        log.info("artifact design refs=%s", [(item["name"], item.get("file")) for item in rows])
    return rows


def _compose_brief_html(pack: dict, shots: list[tuple[str, Path]]) -> tuple[str, dict[str, str]]:
    feature = _feature_for_compose(pack)
    dark = logo_data_uri(dark=True)
    light = logo_data_uri(dark=False)
    shot_meta = []
    images: list[dict] = list(_design_ref_blocks())
    for i, (ref, path) in enumerate(shots[:4], start=1):
        try:
            uri = file_data_uri(path)
        except Exception:
            log.exception("could not attach screenshot %s", path)
            continue
        block = _data_uri_image_block(uri, f"screenshot_{i}")
        if block:
            images.append(block)
        caption = HOWTO_CAPTIONS.get(str(ref), "") or path.stem
        shot_meta.append({"src": uri, "ref": str(ref), "caption": caption})
    payload = {
        "feature": feature,
        "logos": {"on_dark": dark, "on_light": light, "dark": dark, "light": light},
        "screenshots": shot_meta,
        "design_refs": [
            {
                "name": item["name"],
                "file": item.get("file") or "",
                "role": item.get("role")
                or "A4 layout craft. Do not copy that page's copy.",
            }
            for item in images
            if str(item.get("name") or "").startswith("design_ref_")
        ],
        "note": (
            "logos.on_dark is the white lockup for dark surfaces. logos.on_light is the dark lockup for light surfaces. "
            "Both are data URIs — put them on <img src>. Design from feature.description. "
            "Attached design_ref_* images are layout craft — match structure and density, not that page's copy. "
            "The masthead close-up is the top-of-page contract: logo left, label right, pill, headline, lede. "
            "The approved live page shows the shipped Agent Testing brief — match that density and chrome. "
            "Never justify-content:space-between (or margin-top:auto) to eat leftover height. "
            "Keep the footer in flow, with ≥40px gap or a hard color change above it. "
            "Footer is logo + page number only. Pale-blue highlight on one important section — "
            "sibling boxes must not share or overlap that wash. "
            "Return the finished HTML document."
        ),
    }
    model = model_for("artifact_brief")
    dumped = json.dumps(payload, default=str)
    log.info(
        "artifact compose start title=%s payload_chars=%s images=%s effort=xhigh",
        pack.get("title"),
        len(dumped),
        len(images),
    )
    try:
        raw = chat_json(
            surface="artifact_brief",
            system=ARTIFACT_BRIEF_PROMPT,
            payload=payload,
            max_chars=96000,
            timeout=900,
            max_retries=0,
            reasoning_effort="xhigh",
            images=images or None,
        )
    except LLMJsonError as exc:
        raise RuntimeError(f"docs compose failed ({model}): {exc}") from exc
    html = str((raw or {}).get("html") or "").strip()
    opus_files = store_opus_compose(str(pack.get("title") or "Feature"), raw, html)
    if not html:
        keys = list((raw or {}).keys()) if isinstance(raw, dict) else []
        raise RuntimeError(
            f"docs compose failed ({model}): JSON had no html field (keys={keys!r}) title={pack.get('title')}"
        )
    prepared = prepare_brief_html(html)
    log.info(
        "artifact docs html ok title=%s chars=%s model=%s",
        pack.get("title"),
        len(prepared),
        model,
    )
    return prepared, opus_files


def _polish_brief_html(html: str, title: str) -> str:
    source = (html or "").strip()
    if "<html" not in source.lower():
        return source
    model = model_for("artifact_polish")
    log.info("artifact polish start title=%s chars=%s effort=medium", title, len(source))
    try:
        raw = chat_json(
            surface="artifact_polish",
            system=ARTIFACT_POLISH_PROMPT,
            payload={
                "html": source,
                "note": (
                    "Keep copy and data URIs. Fix spacing and UI from the design system. "
                    "Pages may grow with content — do not clip. "
                    "Footer is logo + page number only. Pale-blue highlight must not overlap sibling boxes. "
                    "Return the finished HTML document."
                ),
            },
            max_chars=200000,
            timeout=900,
            max_retries=0,
            reasoning_effort="medium",
        )
    except Exception as exc:
        log.exception("artifact polish failed title=%s err=%s", title, exc)
        return source
    polished = str((raw or {}).get("html") or "").strip()
    if not polished:
        log.warning("artifact polish empty title=%s; keeping compose HTML", title)
        return source
    try:
        prepared = prepare_brief_html(polished)
    except Exception:
        log.exception("artifact polish returned unusable HTML title=%s", title)
        return source
    log.info("artifact polish ok title=%s chars=%s model=%s", title, len(prepared), model)
    return prepared


def _pack_to_grid(pack: dict) -> dict:
    """Unused grid path. Kept for the dormant deck helper; briefs must not fall back here."""
    heading = str(pack.get("outcome") or pack.get("title") or "Feature")
    why = pack.get("why") if isinstance(pack.get("why"), dict) else {}
    blocks = []
    if pack.get("stats"):
        blocks.append({"type": "stat_band", "items": [{"value": s.get("value"), "label": s.get("label")} for s in pack["stats"]]})
    if why.get("risk") or why.get("reasons"):
        blocks.append({"type": "why", "heading": "Why you need this", "risk": why.get("risk") or "", "items": why.get("reasons") or []})
    if pack.get("capabilities"):
        blocks.append(
            {
                "type": "table",
                "headers": ["View", "What you see", "Where", "Use it to"],
                "rows": [
                    {
                        "cells": [c.get("name"), c.get("what_you_see"), c.get("where"), c.get("use_it_to")],
                        "flags": ["", "", "", ""],
                    }
                    for c in pack["capabilities"]
                ],
            }
        )
    page1 = {
        "tone": "hero",
        "eyebrow": f"{pack.get('module') or 'Sense'} brief",
        "released": pack.get("released") or "",
        "heading": heading,
        "lede": pack.get("lede") or "",
        "blocks": blocks,
    }
    page2_blocks = []
    if pack.get("how_to"):
        page2_blocks.append({"type": "steps", "items": pack["how_to"]})
    if pack.get("workflows"):
        page2_blocks.append({"type": "bold_lead_list", "columns": 2, "items": pack["workflows"]})
    if pack.get("caveats"):
        page2_blocks.append({"type": "panel", "kicker": "What to know", "columns": 2, "items": pack["caveats"]})
    pages = [page1]
    if page2_blocks:
        pages.append({"tone": "light", "heading": heading, "kicker": "How to use it", "lede": "", "blocks": page2_blocks})
    return {"title": pack.get("title"), "module": pack.get("module"), "format": "brief", "pages": pages}


def render_artifact_pdf(deck: dict, dest: Path) -> Path:
    html = render_artifact_html(deck)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.with_suffix(".html").write_text(html, encoding="utf-8")
    fills: list[dict] = []
    try:
        fills = measure_page_fill(html)
        log_page_fill(fills, title=str((deck or {}).get("title") or dest.stem))
    except Exception:
        log.exception("artifact fill measure failed dest=%s", dest)
    if isinstance(deck, dict):
        deck["html"] = html
        deck["fill"] = fills
    dest.with_suffix(".json").write_text(json.dumps(deck, indent=2), encoding="utf-8")
    return html_to_pdf(html, dest, fit=False)


def publish_feature_artifacts(
    *,
    features_in_short: str,
    branch: str,
    items: list[dict] | None = None,
    notes: str = "",
    doc: dict | None = None,
    formats: tuple[str, ...] | list[str] | None = None,
    screenshots: dict | list | None = None,
) -> list[dict]:
    rows = [item for item in (items or feature_items(features_in_short)) if item.get("lead")]
    if not rows:
        return []
    dest_dir = Path(ARTIFACT_DIR)
    dest_dir.mkdir(parents=True, exist_ok=True)
    wanted = [item for item in (formats or ("brief",)) if item in {"deck", "brief"}] or ["brief"]
    published: list[dict] = []
    for row in rows[:8]:
        lead = str(row.get("lead") or "").strip()
        if not lead:
            continue
        for fmt in wanted:
            deck = generate_artifact(
                title=lead,
                features_in_short=features_in_short,
                branch=branch,
                notes=notes,
                doc=doc,
                fmt=fmt,
                screenshots=screenshots,
            )
            pdf = render_artifact_pdf(deck, dest_dir / artifact_pdf_name(lead, fmt))
            result = {
                "feature": lead,
                "format": fmt,
                "pdf_path": str(pdf),
                "file_id": "",
                "url": "",
                "fill": deck.get("fill") or [],
                "opus_json": deck.get("opus_json") or "",
                "opus_html": deck.get("opus_html") or "",
            }
            if drive_configured():
                try:
                    uploaded = upload_pdf(pdf, branch or "release", filename=artifact_pdf_name(lead, fmt))
                    result["file_id"] = str(uploaded.get("file_id") or "")
                    result["url"] = str(uploaded.get("link") or "")
                except Exception:
                    log.exception("could not upload artifact PDF for %s %s", lead, fmt)
            published.append(result)
    return published


def _normalize(text: str) -> str:
    raw = re.sub(r"\s+", " ", (text or "").replace("\r", "")).strip()
    return (
        raw.replace("→", " / ")
        .replace("▸", " / ")
        .replace("►", " / ")
        .replace("▯", " / ")
    )


def _fit(text: str, limit: int) -> str | None:
    """Keep text that fits. Trim on a word boundary. Drop rather than sever a word."""
    raw = _normalize(text)
    if not raw:
        return ""
    if limit <= 0:
        return None
    if len(raw) <= limit:
        return raw
    prefix = raw[:limit]
    if raw[limit].isspace():
        cut = prefix.rstrip(" ,;:-")
        return cut or None
    cut = prefix.rsplit(" ", 1)[0].rstrip(" ,;:-")
    if not cut or len(cut) < max(8, int(limit * 0.4)):
        return None
    return cut


def _must_fit(text: str, limit: int) -> str:
    fitted = _fit(text, limit)
    if fitted is not None:
        return fitted
    raw = _normalize(text)
    if " " in raw[: max(limit, 1)]:
        return raw[:limit].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return raw[:limit]


def _clean(text: str) -> str:
    return _normalize(text)


def _tokens(text: str) -> set[str]:
    return {tok for tok in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(tok) > 2}


def _similar(left: str, right: str) -> bool:
    a, b = _normalize(left), _normalize(right)
    if not a or not b:
        return False
    ta, tb = _tokens(a), _tokens(b)
    if len(ta) < 5 or len(tb) < 5:
        return False
    inter = len(ta & tb)
    shorter = min(len(ta), len(tb))
    union = len(ta | tb) or 1
    if inter >= 4 and (inter / shorter >= 0.75 or inter / union >= 0.55):
        return True
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() >= 0.82


def _lead_text_items(raw, lead_limit: int, text_limit: int, cap: int) -> list[dict]:
    items = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        lead, text = _fit(str(item.get("lead") or ""), lead_limit), _fit(str(item.get("text") or ""), text_limit)
        if lead is None or text is None:
            continue
        if lead or text:
            items.append({"lead": lead, "text": text})
        if len(items) >= cap:
            break
    return items


def _item_blobs(block: dict) -> list[tuple[str, str]]:
    kind = block.get("type")
    blobs: list[tuple[str, str]] = []
    if kind in {"cards", "why", "bold_lead_list", "panel", "flow"}:
        for i, item in enumerate(block.get("items") or []):
            if isinstance(item, dict):
                blobs.append((f"items.{i}", f"{item.get('lead') or ''} {item.get('text') or ''}"))
        if kind == "why" and block.get("risk"):
            blobs.append(("risk", str(block.get("risk"))))
        if kind == "panel" and block.get("statement"):
            blobs.append(("statement", str(block.get("statement"))))
    elif kind == "table":
        for i, row in enumerate(block.get("rows") or []):
            cells = row.get("cells") if isinstance(row, dict) else []
            blobs.append((f"rows.{i}", " ".join(str(c) for c in cells)))
    elif kind == "steps":
        for i, item in enumerate(block.get("items") or []):
            blobs.append((f"items.{i}", str(item)))
    elif kind == "callout":
        blobs.append(("statement", f"{block.get('statement') or ''} {block.get('support') or ''}"))
    elif kind == "quote":
        blobs.append(("text", str(block.get("text") or "")))
    elif kind == "comparison":
        for side in ("left", "right"):
            col = block.get(side) if isinstance(block.get(side), dict) else {}
            for i, item in enumerate(col.get("items") or []):
                if isinstance(item, dict):
                    blobs.append((f"{side}.{i}", f"{item.get('lead') or ''} {item.get('text') or ''}"))
    return blobs


def _drop_blob(block: dict, key: str) -> dict | None:
    if "." in key:
        field, _, idx_s = key.partition(".")
        try:
            idx = int(idx_s)
        except ValueError:
            return block
        if field in {"left", "right"}:
            col = dict(block.get(field) or {})
            items = list(col.get("items") or [])
            if 0 <= idx < len(items):
                items.pop(idx)
            col["items"] = items
            block = {**block, field: col}
            left = (block.get("left") or {}).get("items") or []
            right = (block.get("right") or {}).get("items") or []
            return block if left or right else None
        items = list(block.get(field) or [])
        if 0 <= idx < len(items):
            items.pop(idx)
        block = {**block, field: items}
        if field == "rows":
            return block if block.get("headers") and items else None
        if field == "items" and block.get("type") == "flow":
            return block if len(items) >= 2 else None
        if field == "items" and block.get("type") == "why":
            return block if items or block.get("risk") else None
        return block if items else None
    if key == "risk":
        block = {**block, "risk": ""}
        return block if block.get("items") else None
    if key == "statement" and block.get("type") == "panel":
        block = {**block, "statement": ""}
        return block if block.get("items") else None
    if key in {"statement", "text"}:
        return None
    return block


def _dedupe_page_blocks(blocks: list[dict]) -> list[dict]:
    seen: list[str] = []
    out: list[dict] = []
    for block in blocks:
        current = dict(block)
        changed = True
        while changed:
            changed = False
            for key, blob in _item_blobs(current):
                if any(_similar(blob, prev) for prev in seen):
                    nxt = _drop_blob(current, key)
                    if nxt is None:
                        current = {}
                        changed = False
                        break
                    current = nxt
                    changed = True
                    break
        if not current:
            continue
        seen.extend(blob for _, blob in _item_blobs(current))
        out.append(current)
    return out


def _clean_block(block) -> dict | None:
    if not isinstance(block, dict):
        return None
    kind = str(block.get("type") or "").strip().lower()
    if kind not in BLOCK_TYPES:
        return None
    if kind == "stat_band":
        items = []
        seen_values: set[str] = set()
        for item in block.get("items") or []:
            if not isinstance(item, dict):
                continue
            value, label = _fit(str(item.get("value") or ""), 36), _fit(str(item.get("label") or ""), 96)
            if value is None or label is None:
                continue
            if not value and not label:
                continue
            key = re.sub(r"\s+", " ", value).strip().lower()
            if key in seen_values:
                continue
            seen_values.add(key)
            items.append({"value": value, "label": label})
            if len(items) >= 4:
                break
        return {"type": kind, "items": items} if len(items) >= 2 else None
    if kind == "cards":
        items = _lead_text_items(block.get("items"), 96, 360, 4)
        if not items:
            return None
        cols = int(block.get("columns") or (3 if len(items) == 3 else 2))
        return {"type": kind, "columns": cols if cols in {2, 3, 4} else 2, "items": items}
    if kind == "table":
        headers = []
        for h in block.get("headers") or []:
            fitted = _fit(str(h), 48)
            if fitted is None:
                return None
            if fitted:
                headers.append(fitted)
        rows = []
        for row in block.get("rows") or []:
            if not isinstance(row, dict):
                continue
            cells = []
            dropped = False
            for c in row.get("cells") or []:
                fitted = _fit(str(c), 160)
                if fitted is None:
                    dropped = True
                    break
                cells.append(fitted)
            if dropped or not any(cells):
                continue
            flags = [
                str(f or "").lower() if str(f or "").lower() in {"success", "warning", "error", "info"} else ""
                for f in (row.get("flags") or [])
            ]
            rows.append({"cells": cells, "flags": flags})
        headers, rows, caption = drop_constant_table_columns(headers, rows)
        block_out: dict = {"type": kind, "headers": headers, "rows": rows[:8]}
        if caption:
            block_out["caption"] = caption
        return block_out if headers and rows else None
    if kind == "flow":
        items = _lead_text_items(block.get("items"), 64, 200, 5)
        return {"type": kind, "items": items} if len(items) >= 2 else None
    if kind == "steps":
        items = []
        for item in block.get("items") or []:
            fitted = _fit(str(item), 220)
            if fitted:
                items.append(fitted)
            if len(items) >= 6:
                break
        return {"type": kind, "items": items} if items else None
    if kind == "callout":
        statement = _fit(str(block.get("statement") or block.get("lead") or ""), 280)
        if not statement:
            return None
        support = _fit(str(block.get("support") or block.get("text") or ""), 480)
        if support is None:
            support = ""
        kicker = _must_fit(str(block.get("kicker") or ""), 80)
        return {"type": kind, "kicker": kicker, "statement": statement, "support": support}
    if kind == "quote":
        text = _fit(str(block.get("text") or ""), 320)
        return {"type": kind, "text": text} if text else None
    if kind == "comparison":
        def side(raw) -> dict:
            col = raw if isinstance(raw, dict) else {}
            return {
                "heading": _must_fit(str(col.get("heading") or ""), 80),
                "items": _lead_text_items(col.get("items"), 80, 220, 6),
            }
        left, right = side(block.get("left")), side(block.get("right"))
        if not left["items"] and not right["items"]:
            return None
        return {"type": kind, "left": left, "right": right}
    if kind == "why":
        items = _lead_text_items(block.get("items"), 96, 360, 3)
        risk = _fit(str(block.get("risk") or block.get("text") or ""), 420)
        if risk is None:
            risk = ""
        heading = _must_fit(str(block.get("heading") or "Why you need this"), 80) or "Why you need this"
        if not items and not risk:
            return None
        return {"type": kind, "heading": heading, "risk": risk, "items": items}
    if kind == "bold_lead_list":
        items = _lead_text_items(block.get("items"), 96, 280, 8)
        if not items:
            return None
        cols = int(block.get("columns") or (2 if len(items) >= 4 else 1))
        return {"type": kind, "columns": 2 if cols != 1 else 1, "items": items}
    if kind == "panel":
        items = _lead_text_items(block.get("items"), 96, 280, 4)
        statement = _fit(str(block.get("statement") or ""), 280)
        if statement is None:
            statement = ""
        if not items and not statement:
            return None
        cols = int(block.get("columns") or (2 if len(items) >= 2 else 1))
        if cols not in {1, 2, 4}:
            cols = 2
        return {
            "type": kind,
            "kicker": _must_fit(str(block.get("kicker") or ""), 80),
            "statement": statement,
            "columns": cols,
            "items": items,
        }
    return None

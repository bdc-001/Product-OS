"""Create Convin-styled Google Docs for release notes. Drive folder is the parent."""

from __future__ import annotations

import logging
import re
import time
from pathlib import Path

from app.clients.llm import LLMJsonError, chat_json
from app.config import settings
from app.services.comms import RELEASE_NOTES_EXAMPLE
from app.services.gdocs_style import CONVIN_DOCS, chip_style, font_family, pt, rgb_color, theme_named_style_requests
from app.services.gdrive import drive_configured, ensure_year_folder, explain_drive_error
from app.services.pdf_notes import drive_doc_name
from app.services.prompts import with_preamble
from app.services.time_window import now_local

log = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
]

CANONICAL_HEADINGS = [
    "Background",
    "Functional Overview",
    "Navigation",
    "Key Concepts",
    "Prerequisites",
    "How to Use",
    "Configuration Options",
    "Outcome Analysis",
    "Common Workflows",
    "FAQs",
]

HEADING_ALIASES = {
    "background": "Background",
    "functional overview": "Functional Overview",
    "key highlights": "Functional Overview",
    "highlights": "Functional Overview",
    "navigation": "Navigation",
    "key concepts": "Key Concepts",
    "key concepts (glossary)": "Key Concepts",
    "glossary": "Key Concepts",
    "prerequisites": "Prerequisites",
    "prerequisites / setup checklist": "Prerequisites",
    "setup checklist": "Prerequisites",
    "how to use": "How to Use",
    "how to use (step by step)": "How to Use",
    "configuration": "Configuration Options",
    "configuration options": "Configuration Options",
    "outcome analysis": "Outcome Analysis",
    "common workflows": "Common Workflows",
    "common workflows (use cases)": "Common Workflows",
    "use cases": "Common Workflows",
    "faq": "FAQs",
    "faqs": "FAQs",
}

HEADING_DISPLAY = {
    "Background": "📌 Background",
    "Functional Overview": "📌 Functional Overview",
    "Navigation": "📌 Navigation",
    "Key Concepts": "📌 Key Concepts (Glossary)",
    "Prerequisites": "📌 Prerequisites / Setup Checklist",
    "How to Use": "📌 How to Use (Step by Step)",
    "Configuration Options": "📌 Configuration Options",
    "Outcome Analysis": "📌 Outcome Analysis",
    "Common Workflows": "📌 Common Workflows (Use Cases)",
    "FAQs": "📌 FAQs",
}

COMMS_DOC_PROMPT = with_preamble(
    "You write Convin CLIENT-FACING release-note Google Docs for customers.\n"
    "These documents are not for CSMs or internal training. Write to the customer as \"you\".\n"
    "Lead with the outcome, then the action: what you can now do, in plain benefit-led language.\n"
    "Prefer \"you can …\" and \"so you can …\". Never write \"confirm in product\", \"confirm in UAT\",\n"
    "\"under the hood\", APIs, git, tenant flags, engineering, or CSM-only steps.\n"
    "Internal Cliq / WhatsApp blasts are a different format — do not use that voice here.\n"
    "The payload `features_in_short` is what shipped. Those names ARE the document. Do not invent others.\n\n"
    "Match this FORMAT exactly (placeholders are not product facts):\n\n"
    f"{RELEASE_NOTES_EXAMPLE}\n\n"
    """Return JSON:
{
 "title": "<feature name>",
 "subtitle": "<feature> — <surface>",
 "chips": ["Release Note", "Activate"],
 "intro": "<one sentence outcome; bold the feature once as {{feature}}>",
 "meta": {
   "feature_name": "<same as title>",
   "module": "<Sense or Activate>",
   "audience": "Clients",
   "teams": "Campaign managers, operations",
   "summary": "<one sentence outcome for the customer>"
 },
 "sections": [
   {"heading": "Background", "blocks": [{"type": "bullets", "items": [
     {"lead": "Business problem it solves", "text": "<old pain>"},
     {"lead": "Who benefits", "text": "<audience>"},
     {"lead": "What changes for the user after adopting it", "text": "<what they can now do>"}]}]},
   {"heading": "Functional Overview", "blocks": [
     {"type": "para", "text": "You can use <feature> as <role> so you can <outcome>."},
     {"type": "bullets", "items": [
       {"lead": "What the user can create / configure / view", "text": "<list>"},
       {"lead": "What the system does automatically", "text": "<list>"},
       {"lead": "What outputs / reports / results the user sees", "text": "<list>"}]}]},
   {"heading": "Navigation", "blocks": [{"type": "numbered", "items": ["Open <feature>", "Choose <surface>", "Apply <filter> as needed"]}]},
   {"heading": "Key Concepts", "blocks": [{"type": "table", "headers": ["Term", "Meaning (functional)", "Example"], "rows": [["<term>", "<meaning>", "<example>"]]}]},
   {"heading": "Prerequisites", "blocks": [
     {"type": "para", "text": "Before you start, you need:"},
     {"type": "bullets", "items": ["Access / permission available", "Required parent config completed", "Related modules enabled"]}]},
   {"heading": "How to Use", "blocks": [
     {"type": "h3", "text": "8.1 Create / Configure"},
     {"type": "numbered", "items": ["Open <surface>.", "You can see <kpi> on Overview."]},
     {"type": "image", "ref": "8.1"},
     {"type": "para", "text": "Expected result: <result>."},
     {"type": "h3", "text": "8.2 Enable / Attach / Activate"},
     {"type": "numbered", "items": ["Apply <filter>.", "Open <table>."]},
     {"type": "image", "ref": "8.2"},
     {"type": "para", "text": "Expected result: metrics follow the selection."},
     {"type": "h3", "text": "8.3 Day-to-Day Usage"},
     {"type": "numbered", "items": ["Check <table>."]},
     {"type": "image", "ref": "8.3"},
     {"type": "para", "text": "Expected result: trends are scoped."},
     {"type": "h3", "text": "8.4 Review Outcomes"},
     {"type": "numbered", "items": ["Note outliers."]},
     {"type": "image", "ref": "8.4"},
     {"type": "para", "text": "Expected result: one analysis pass covers the set."}]},
   {"heading": "Configuration Options", "blocks": [{"type": "table", "headers": ["Setting", "What it controls", "Recommended use", "Impact if changed"], "rows": [["<setting>", "<controls>", "<use>", "<impact>"]]}]},
   {"heading": "Outcome Analysis", "blocks": [{"type": "table", "headers": ["Output", "Meaning", "Where seen", "How to use it"], "rows": [["<output>", "<meaning>", "<where>", "<how>"]]}]},
   {"heading": "Common Workflows", "blocks": [{"type": "para", "text": "Use Case 1: <goal>\\nSteps: <path>.\\nOutcome: <outcome>."}]},
   {"heading": "FAQs", "blocks": [{"type": "faq", "items": [{"q": "Why am I not seeing <kpi>?", "a": "Switch to <surface> so you can see it."}]}]}
 ]
}

Rules:
- Include every heading in that order.
- Background, Functional Overview, and Prerequisites MUST use type "bullets" with one idea per item. Never fake a list with "- " inside a paragraph.
- Navigation and How to Use steps MUST use type "numbered". Never fake numbers inside a paragraph.
- How to Use 8.x titles are type "h3". Put type "image" with ref 8.1 / 8.2 / 8.3 / 8.4 immediately after that step's numbered list. Use payload screenshot_filenames when present. Never in Background or FAQs.
- Field | Content comes from meta, not a section. No under-the-hood.
- Leave a block out only if evidence is missing.
"""
)

EMOJI = re.compile(
    "["
    "\U0001f300-\U0001faff"
    "\U00002700-\U000027bf"
    "\U0001f900-\U0001f9ff"
    "\U00002600-\U000026ff"
    "]+",
    flags=re.UNICODE,
)


def _creds():
    from google.oauth2 import service_account

    key = Path(settings.gdrive_key_file).expanduser()
    return service_account.Credentials.from_service_account_file(str(key), scopes=SCOPES)


def _drive():
    from googleapiclient.discovery import build

    return build("drive", "v3", credentials=_creds(), cache_discovery=False)


def _docs():
    from googleapiclient.discovery import build

    return build("docs", "v1", credentials=_creds(), cache_discovery=False)


def _docs_batch(doc_id: str, requests: list[dict]) -> None:
    if not requests:
        return
    docs = _docs()
    last: Exception | None = None
    for attempt in range(8):
        try:
            docs.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()
            return
        except Exception as exc:
            last = exc
            text = str(exc)
            if "429" in text or "RATE_LIMIT" in text:
                time.sleep(min(50.0, 6.0 * (attempt + 1)))
                continue
            raise
    raise last or RuntimeError("Google Docs write failed")


def _assets_parent() -> str:
    return (settings.gdrive_assets_folder_id or settings.gdrive_folder_id or "").strip()


def inline_image_uri(file_id: str) -> str:
    return f"https://drive.google.com/uc?export=view&id={file_id}"


def upload_screenshot(png_path: Path, branch: str) -> tuple[str, str]:
    """Upload PNG; return (file_id, insertInlineImage URI)."""
    from googleapiclient.http import MediaFileUpload

    drive = _drive()
    parent = _assets_parent()
    name = f"{(branch or 'release').replace('/', '_')}__{png_path.name}"
    media = MediaFileUpload(str(png_path), mimetype="image/png")
    created = (
        drive.files()
        .create(
            body={"name": name, "parents": [parent]} if parent else {"name": name},
            media_body=media,
            fields="id",
            supportsAllDrives=True,
        )
        .execute()
    )
    file_id = created["id"]
    domain = (settings.gdrive_domain or "").strip()
    body = {"type": "domain", "role": "reader", "domain": domain} if domain else {"type": "anyone", "role": "reader"}
    drive.permissions().create(fileId=file_id, body=body, supportsAllDrives=True).execute()
    return file_id, inline_image_uri(file_id)


def upload_howto_screenshots(paths: dict[str, Path], branch: str) -> dict[str, str]:
    """Upload How to Use stills; keys are 8.1 / 8.2 / … plus the filename."""
    uris: dict[str, str] = {}
    for key, path in (paths or {}).items():
        _, uri = upload_screenshot(Path(path), branch)
        uris[str(key)] = uri
        uris[Path(path).name] = uri
    return uris


def delete_screenshot(file_id: str) -> None:
    if not file_id:
        return
    try:
        _drive().files().delete(fileId=file_id, supportsAllDrives=True).execute()
    except Exception:
        log.exception("could not delete screenshot %s", file_id)


def trash_file(file_id: str) -> None:
    if not file_id:
        return
    try:
        _drive().files().update(fileId=file_id, body={"trashed": True}, supportsAllDrives=True).execute()
    except Exception:
        log.exception("could not trash %s", file_id)


def create_release_doc(title: str, year_month: str) -> tuple[str, str]:
    drive = _drive()
    parent = (settings.gdrive_folder_id or "").strip()
    folder = ensure_year_folder(drive, parent, year_month) if parent else ""
    body: dict = {"name": (title or "Release notes")[:180], "mimeType": "application/vnd.google-apps.document"}
    if folder:
        body["parents"] = [folder]
    try:
        created = drive.files().create(body=body, fields="id, webViewLink", supportsAllDrives=True).execute()
    except Exception as exc:
        raise explain_drive_error(exc) from exc
    return created["id"], created.get("webViewLink") or ""


def utf16_len(text: str) -> int:
    """Docs API indexes UTF-16 code units; Python len() counts code points (📌 is 2 vs 1)."""
    return len(text.encode("utf-16-le")) // 2


def _append_index(doc_id: str) -> int:
    doc = _docs().documents().get(documentId=doc_id, fields="body(content(endIndex))").execute()
    content = (doc.get("body") or {}).get("content") or []
    if not content:
        return 1
    return max(1, int(content[-1].get("endIndex") or 2) - 1)


class DocBuilder:
    """Accumulates Docs API requests while tracking the insertion cursor.

    Indices: start inclusive, end exclusive (Docs API). Body content starts at 1.
    """

    def __init__(self, doc_id: str):
        self.doc_id = doc_id
        self.requests: list[dict] = []
        self.index = 1

    def text(self, t: str) -> tuple[int, int]:
        if not t:
            return self.index, self.index
        start = self.index
        self.requests.append({"insertText": {"location": {"index": self.index}, "text": t}})
        self.index += utf16_len(t)
        return start, self.index

    def line(self, t: str) -> tuple[int, int]:
        start, _ = self.text((t or "") + "\n")
        return start, start + utf16_len(t or "")

    def style(self, start: int, end: int, **ts) -> None:
        if end <= start:
            return
        style: dict = {}
        fields: list[str] = []
        if "bold" in ts:
            style["bold"] = bool(ts["bold"])
            fields.append("bold")
        if "italic" in ts:
            style["italic"] = bool(ts["italic"])
            fields.append("italic")
        if "font_size" in ts:
            style["fontSize"] = pt(ts["font_size"])
            fields.append("fontSize")
        if "fg" in ts:
            style["foregroundColor"] = rgb_color(ts["fg"])
            fields.append("foregroundColor")
        if "bg" in ts:
            style["backgroundColor"] = rgb_color(ts["bg"])
            fields.append("backgroundColor")
        if "font" in ts:
            style["weightedFontFamily"] = font_family(bool(ts.get("bold")), str(ts.get("font") or ""))
            fields.append("weightedFontFamily")
        if not fields:
            return
        self.requests.append(
            {
                "updateTextStyle": {
                    "range": {"startIndex": start, "endIndex": end},
                    "textStyle": style,
                    "fields": ",".join(fields),
                }
            }
        )

    def para_style(self, start: int, end: int, **ps) -> None:
        if end <= start:
            return
        style: dict = {}
        fields: list[str] = []
        if "align" in ps:
            style["alignment"] = ps["align"]
            fields.append("alignment")
        if "named" in ps:
            style["namedStyleType"] = ps["named"]
            fields.append("namedStyleType")
        if "spacing" in ps:
            style["spaceBelow"] = pt(ps["spacing"])
            fields.append("spaceBelow")
        if not fields:
            return
        self.requests.append(
            {
                "updateParagraphStyle": {
                    "range": {"startIndex": start, "endIndex": end},
                    "paragraphStyle": style,
                    "fields": ",".join(fields),
                }
            }
        )

    def bullet(self, start: int, end: int, preset: str = "BULLET_DISC_CIRCLE_SQUARE") -> None:
        if end <= start:
            return
        self.requests.append(
            {
                "createParagraphBullets": {
                    "range": {"startIndex": start, "endIndex": end},
                    "bulletPreset": preset,
                }
            }
        )

    def clear_bullets(self, start: int, end: int) -> None:
        if end <= start:
            return
        self.requests.append({"deleteParagraphBullets": {"range": {"startIndex": start, "endIndex": end}}})

    def image(self, uri: str, width_pt: float) -> tuple[int, int]:
        start = self.index
        self.requests.append(
            {
                "insertInlineImage": {
                    "location": {"index": self.index},
                    "uri": uri,
                    "objectSize": {
                        "width": pt(width_pt),
                        "height": pt(width_pt * 0.56),
                    },
                }
            }
        )
        self.index += 1
        return start, self.index

    def heading(self, text: str, level: int = 2) -> tuple[int, int]:
        """NORMAL_TEXT + explicit bold. HEADING_* named styles drop run-level bold."""
        theme = CONVIN_DOCS
        size = {1: theme["title_size"], 2: theme["h2_size"], 3: theme["h3_size"]}[level if level in {1, 2, 3} else 2]
        fg = theme["accent"] if level == 2 else theme["ink"]
        spacing = 8 if level == 1 else 6 if level == 2 else 4
        s, e = self.line(text)
        self.clear_bullets(s, e + 1)
        self.para_style(s, e + 1, named="NORMAL_TEXT", spacing=spacing)
        self.style(s, e, bold=True, font_size=size, fg=fg, font=theme["heading_font"])
        return s, e

    def write_list(self, items: list, *, numbered: bool = False) -> None:
        """Real Docs bullets/numbers on NORMAL_TEXT, then a cleared spacer so the next heading is not a list item."""
        theme = CONVIN_DOCS
        start = None
        end = None
        for item in items:
            lead, body = _item_parts(item)
            if not lead and not body:
                continue
            line = lead if not body else (f"{lead}: {body}" if lead else body)
            s, e = self.line(line)
            self.para_style(s, e + 1, named="NORMAL_TEXT", spacing=4)
            if lead and body:
                colon = s + utf16_len(lead) + 1
                self.style(s, colon, bold=True, font_size=theme["body_size"], fg=theme["ink"], font=theme["font"])
                if e > colon:
                    self.style(colon, e, font_size=theme["body_size"], fg=theme["ink"], font=theme["font"])
            elif lead:
                self.style(s, e, bold=True, font_size=theme["body_size"], fg=theme["ink"], font=theme["font"])
            else:
                self.style(s, e, font_size=theme["body_size"], fg=theme["ink"], font=theme["font"])
            if start is None:
                start = s
            end = e + 1
        if start is None or end is None:
            return
        preset = "NUMBERED_DECIMAL_NESTED" if numbered else "BULLET_DISC_CIRCLE_SQUARE"
        self.bullet(start, end, preset)
        spacer, _ = self.line("")
        self.para_style(spacer, spacer + 1, named="NORMAL_TEXT")
        self.clear_bullets(spacer, spacer + 1)

    def flush(self) -> None:
        self.commit()
        self.index = _append_index(self.doc_id)

    def commit(self) -> None:
        if not self.requests:
            return
        for i in range(0, len(self.requests), 80):
            _docs_batch(self.doc_id, self.requests[i : i + 80])
        self.requests = []


def apply_doc_theme(doc_id: str) -> None:
    t = CONVIN_DOCS
    docs = _docs()
    docs.documents().batchUpdate(
        documentId=doc_id,
        body={
            "requests": [
                {
                    "updateDocumentStyle": {
                        "documentStyle": {
                            "marginTop": pt(t["margin_top"]),
                            "marginBottom": pt(t["margin_bottom"]),
                            "marginLeft": pt(t["margin_left"]),
                            "marginRight": pt(t["margin_right"]),
                        },
                        "fields": "marginTop,marginBottom,marginLeft,marginRight",
                    }
                }
            ]
        },
    ).execute()
    try:
        docs.documents().batchUpdate(documentId=doc_id, body={"requests": theme_named_style_requests()}).execute()
    except Exception:
        log.exception("could not pin Nunito named styles on %s", doc_id)


def set_doc_margins(doc_id: str) -> None:
    apply_doc_theme(doc_id)


HOWTO_STEP_RE = re.compile(r"^(8\.\d+)")


def howto_step_key(text: str) -> str:
    match = HOWTO_STEP_RE.match((text or "").strip())
    return match.group(1) if match else ""


def resolve_screenshot(screenshots: dict[str, str] | None, ref: str) -> str:
    """Map 8.1 / 8.1.png / a filename onto an uploaded insertInlineImage URI."""
    if not ref or not screenshots:
        return ""
    if screenshots.get(ref):
        return screenshots[ref]
    stem = Path(ref).stem
    if screenshots.get(stem):
        return screenshots[stem]
    step = howto_step_key(ref) or howto_step_key(stem)
    if step:
        return screenshots.get(step) or screenshots.get(f"{step}.png") or ""
    lowered = {str(key).lower(): value for key, value in screenshots.items()}
    return lowered.get(ref.lower()) or lowered.get(stem.lower()) or ""


def attach_howto_images(blocks: list, screenshots: dict[str, str] | None = None) -> list:
    """Insert one image immediately after each How to Use 8.x numbered list when a still exists."""
    items = [block for block in (blocks or []) if isinstance(block, dict)]
    out: list[dict] = []
    pending = ""
    for i, block in enumerate(items):
        kind = (block.get("type") or "para").strip().lower()
        if kind == "h3":
            pending = howto_step_key(str(block.get("text") or block.get("heading") or ""))
            out.append(block)
            continue
        if kind == "image":
            pending = ""
            out.append(block)
            continue
        out.append(block)
        if pending and kind == "numbered":
            nxt = items[i + 1] if i + 1 < len(items) else None
            already = isinstance(nxt, dict) and (nxt.get("type") or "").strip().lower() == "image"
            if not already and resolve_screenshot(screenshots, pending):
                out.append({"type": "image", "ref": pending})
            pending = ""
    return out


def is_faq_question(text: str) -> bool:
    return _clean_text(text).lower().startswith("q:")


def table_cell_text_style(header: bool) -> dict:
    """Header-row cells stay bold; Docs treats weightedFontFamily as weight, so pin both."""
    return {
        "weightedFontFamily": font_family(header, CONVIN_DOCS["heading_font"] if header else CONVIN_DOCS["font"]),
        "bold": header,
        "fontSize": pt(CONVIN_DOCS["body_size"]),
        "foregroundColor": rgb_color(CONVIN_DOCS["ink"]),
    }


def _plain_paragraph_text(paragraph: dict) -> str:
    bits = []
    for run in (paragraph or {}).get("elements") or []:
        bits.append(((run.get("textRun") or {}).get("content") or ""))
    return "".join(bits).replace("\n", "").strip()


def _bold_range_request(start: int, end: int) -> dict | None:
    if end <= start:
        return None
    return {
        "updateTextStyle": {
            "range": {"startIndex": start, "endIndex": end},
            "textStyle": {"bold": True, "weightedFontFamily": font_family(True)},
            "fields": "bold,weightedFontFamily",
        }
    }


def emphasis_requests(doc: dict) -> list[dict]:
    """Re-apply visible bold on titles, 📌 / 8.x subheads, table headers, and FAQ questions.

    Google Docs HEADING_* named styles drop run-level bold, and an inherited
    Nunito weight 400 then renders those lines as regular. Switch them to
    NORMAL_TEXT and set bold explicitly (the combination that actually sticks).
    """
    requests: list[dict] = []
    heading_types = {"TITLE", "HEADING_1", "HEADING_2", "HEADING_3"}
    for element in (doc.get("body") or {}).get("content") or []:
        paragraph = element.get("paragraph")
        if paragraph:
            named = (paragraph.get("paragraphStyle") or {}).get("namedStyleType")
            text = _plain_paragraph_text(paragraph)
            start = int(element.get("startIndex") or 1)
            end = int(element.get("endIndex") or start)
            is_title = named in {"TITLE", "HEADING_1"}
            is_h2 = named == "HEADING_2" or text.startswith("📌")
            is_h3 = named == "HEADING_3" or bool(howto_step_key(text))
            is_q = is_faq_question(text)
            if not (is_title or is_h2 or is_h3 or is_q):
                continue
            if is_title or is_h2 or is_h3:
                requests.append(
                    {
                        "updateParagraphStyle": {
                            "range": {"startIndex": start, "endIndex": end},
                            "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
                            "fields": "namedStyleType",
                        }
                    }
                )
                size = CONVIN_DOCS["title_size"] if is_title else CONVIN_DOCS["h2_size"] if is_h2 else CONVIN_DOCS["h3_size"]
                fg = CONVIN_DOCS["accent"] if is_h2 else CONVIN_DOCS["ink"]
                requests.append(
                    {
                        "updateTextStyle": {
                            "range": {"startIndex": start, "endIndex": end - 1},
                            "textStyle": {
                                "bold": True,
                                "fontSize": pt(size),
                                "foregroundColor": rgb_color(fg),
                                "weightedFontFamily": font_family(True, CONVIN_DOCS["heading_font"]),
                            },
                            "fields": "bold,fontSize,foregroundColor,weightedFontFamily",
                        }
                    }
                )
            else:
                req = _bold_range_request(start, end - 1)
                if req:
                    requests.append(req)
            continue
        table = element.get("table")
        if not table:
            continue
        rows = table.get("tableRows") or []
        if not rows:
            continue
        for cell in rows[0].get("tableCells") or []:
            for item in cell.get("content") or []:
                start = int(item.get("startIndex") or 0)
                end = int(item.get("endIndex") or start) - 1
                req = _bold_range_request(start, end)
                if req:
                    requests.append(req)
    return requests


def restore_emphasis(doc_id: str) -> None:
    doc = _docs().documents().get(documentId=doc_id).execute()
    requests = emphasis_requests(doc)
    if requests:
        _docs_batch(doc_id, requests)


def write_release_notes_doc(doc_id: str, doc_json: dict, screenshots: dict[str, str] | None = None) -> None:
    screenshots = screenshots or {}
    b = DocBuilder(doc_id)
    theme = CONVIN_DOCS
    title = _clean_text(str((doc_json or {}).get("title") or "Release notes"))
    b.heading(title, 1)

    subtitle = _clean_text(str((doc_json or {}).get("subtitle") or ""))
    if subtitle:
        s, e = b.line(subtitle)
        b.style(s, e, font_size=theme["body_size"], fg=theme["muted"], font=theme["font"])

    chips = [str(c).strip() for c in (doc_json.get("chips") or []) if str(c).strip()][:4]
    if chips:
        chip_line = "   ".join(chips)
        s, _ = b.line(chip_line)
        idx = s
        for i, chip in enumerate(chips):
            kind = "green" if "post" in chip.lower() else "orange"
            cs = chip_style(kind)
            b.style(idx, idx + utf16_len(chip), bold=True, font_size=9, fg=cs["tx"], bg=cs["bg"], font=theme["font"])
            idx += utf16_len(chip) + (3 if i < len(chips) - 1 else 0)

    meta = _meta_from_doc(doc_json)
    hero = screenshots.get("artifact") or ""
    if hero:
        img_s, _ = b.image(hero, theme["image_width_pt"])
        _, nl_e = b.text("\n\n")
        b.para_style(img_s, nl_e, align="CENTER", spacing=10)

    _write_table(
        b,
        [
            ["Field", "Content"],
            ["Feature Name", meta.get("feature_name") or ""],
            ["Module Concerned", meta.get("module") or ""],
            ["Audience", meta.get("audience") or ""],
            ["Teams Concerned", meta.get("teams") or ""],
            ["Summary", meta.get("summary") or ""],
        ],
    )

    by_heading = _section_map(doc_json)
    highlights = [h for h in (doc_json.get("highlights") or []) if isinstance(h, dict)]
    for heading in CANONICAL_HEADINGS:
        blocks = list(by_heading.get(heading) or [])
        if heading == "Functional Overview" and highlights and not _has_list(blocks, "bullets"):
            blocks.append({"type": "bullets", "items": highlights})
        if heading == "How to Use":
            blocks = attach_howto_images(blocks, screenshots)
        if not blocks:
            continue
        b.heading(HEADING_DISPLAY.get(heading, f"📌 {heading}"), 2)
        _write_blocks(b, blocks, screenshots, theme)

    b.commit()
    restore_emphasis(doc_id)


def _item_parts(item) -> tuple[str, str]:
    if isinstance(item, dict):
        lead = _clean_text(str(item.get("lead") or item.get("q") or ""))
        body = _clean_text(str(item.get("text") or item.get("a") or item.get("body") or ""))
        return lead, body
    return "", _clean_text(str(item or ""))


def _has_list(blocks: list, kind: str) -> bool:
    return any(isinstance(block, dict) and block.get("type") == kind and block.get("items") for block in blocks)


def _write_blocks(builder: DocBuilder, blocks: list, screenshots: dict[str, str], theme: dict) -> None:
    for block in blocks:
        if not isinstance(block, dict):
            continue
        kind = (block.get("type") or "para").strip().lower()
        if kind == "h3":
            text = _clean_text(str(block.get("text") or block.get("heading") or ""))
            if text:
                builder.heading(text, 3)
        elif kind == "para":
            _write_paragraphs(builder, str(block.get("text") or block.get("body") or ""), theme)
        elif kind == "bullets":
            builder.write_list(block.get("items") or [], numbered=False)
        elif kind == "numbered":
            builder.write_list(block.get("items") or [], numbered=True)
        elif kind == "table":
            headers = [str(h) for h in (block.get("headers") or []) if str(h).strip()]
            rows = [[_clean_text(str(c)) for c in row] for row in (block.get("rows") or []) if isinstance(row, list)]
            table = ([headers] if headers else []) + rows
            if table:
                _write_table(builder, table)
        elif kind == "faq":
            _write_faq(builder, block.get("items") or [], theme)
        elif kind == "image":
            uri = resolve_screenshot(screenshots, str(block.get("ref") or ""))
            if uri:
                img_s, _ = builder.image(uri, theme["image_width_pt"])
                _, nl_e = builder.text("\n\n")
                builder.para_style(img_s, nl_e, align="CENTER", spacing=10)


def _write_faq(builder: DocBuilder, items: list, theme: dict) -> None:
    for item in items or []:
        if isinstance(item, dict):
            question = _clean_text(str(item.get("q") or item.get("lead") or ""))
            answer = _clean_text(str(item.get("a") or item.get("text") or item.get("body") or ""))
        else:
            question, answer = "", _clean_text(str(item or ""))
        if question:
            _write_paragraphs(builder, question if is_faq_question(question) else f"Q: {question}", theme)
        if answer:
            prefixed = answer if answer.lower().startswith("a:") else f"A: {answer}"
            _write_paragraphs(builder, prefixed, theme)


def _write_paragraphs(builder: DocBuilder, text: str, theme: dict) -> None:
    chunks = [chunk.strip() for chunk in (text or "").split("\n") if chunk.strip()]
    for chunk in chunks:
        clean = _clean_text(chunk)
        start, end = builder.line(clean)
        builder.para_style(start, end + 1, named="NORMAL_TEXT", spacing=6)
        builder.style(
            start,
            end,
            **(
                {"bold": True}
                if is_faq_question(clean)
                else {}
            ),
            font_size=theme["body_size"],
            fg=theme["ink"],
            font=theme["font"],
        )


def _write_table(builder: DocBuilder, rows: list[list[str]]) -> None:
    rows = [[_clean_text(str(cell)) for cell in row] for row in rows if row]
    if not rows:
        return
    builder.flush()
    n_rows = len(rows)
    n_cols = max(len(row) for row in rows)
    padded = [row + [""] * (n_cols - len(row)) for row in rows]
    docs = _docs()
    insert_at = builder.index
    _docs_batch(builder.doc_id, [{"insertTable": {"rows": n_rows, "columns": n_cols, "location": {"index": insert_at}}}])
    doc = docs.documents().get(documentId=builder.doc_id).execute()
    table = None
    for element in (doc.get("body") or {}).get("content") or []:
        if element.get("table") and int(element.get("startIndex") or 0) >= insert_at:
            table = element
            break
    if not table:
        builder.index = _append_index(builder.doc_id)
        return
    inserts = []
    for r_i, row in enumerate((table.get("table") or {}).get("tableRows") or []):
        for c_i, cell in enumerate(row.get("tableCells") or []):
            content = cell.get("content") or []
            if not content:
                continue
            start = int(content[0].get("startIndex") or 0)
            text = padded[r_i][c_i] if r_i < len(padded) and c_i < len(padded[r_i]) else ""
            if text:
                inserts.append((start, text, r_i == 0))
    fill = []
    for start, text, header in sorted(inserts, reverse=True):
        fill.append({"insertText": {"location": {"index": start}, "text": text}})
        fill.append(
            {
                "updateTextStyle": {
                    "range": {"startIndex": start, "endIndex": start + utf16_len(text)},
                    "textStyle": table_cell_text_style(header),
                    "fields": "weightedFontFamily,bold,fontSize,foregroundColor",
                }
            }
        )
    _docs_batch(builder.doc_id, fill)
    builder.index = _append_index(builder.doc_id)


def _write_marked_intro(builder: DocBuilder, intro: str, theme: dict) -> None:
    parts = re.split(r"\{\{(.*?)\}\}", intro)
    for i, part in enumerate(parts):
        if not part:
            continue
        start, end = builder.text(part)
        builder.style(
            start,
            end,
            bold=(i % 2 == 1),
            font_size=theme["body_size"],
            fg=theme["ink"],
            font=theme["font"],
        )


def _plain_intro(intro: str) -> str:
    return re.sub(r"\{\{(.*?)\}\}", r"\1", intro or "").strip()


def _canonical_heading(raw: str) -> str | None:
    key = re.sub(r"^[\W_]+", "", _clean_text(str(raw or ""))).strip().lower()
    key = re.sub(r"\s+", " ", key)
    if key in HEADING_ALIASES:
        return HEADING_ALIASES[key]
    for heading in CANONICAL_HEADINGS:
        if key == heading.lower() or key.startswith(heading.lower()):
            return heading
    return None


def _clean_text(text: str) -> str:
    return EMOJI.sub("", text or "").replace("\r", "").strip()


def _normalize_item(item) -> dict | str:
    if isinstance(item, dict):
        lead, body = _item_parts(item)
        if lead or body:
            return {"lead": lead, "text": body} if lead else body
        return ""
    return _clean_text(str(item or ""))


def _normalize_blocks(raw_blocks, body: str = "") -> list[dict]:
    blocks = []
    for block in raw_blocks or []:
        if not isinstance(block, dict):
            continue
        kind = (block.get("type") or "para").strip().lower()
        if kind in {"bullets", "numbered"}:
            items = [_normalize_item(item) for item in (block.get("items") or [])]
            items = [item for item in items if item]
            if items:
                blocks.append({"type": kind, "items": items})
        elif kind == "table":
            headers = [_clean_text(str(h))[:40] for h in (block.get("headers") or []) if str(h).strip()]
            rows = []
            for row in (block.get("rows") or [])[:8]:
                if isinstance(row, list):
                    rows.append([_clean_text(str(c))[:200] for c in row[:6]])
            if headers or rows:
                blocks.append({"type": "table", "headers": headers, "rows": rows})
        elif kind == "h3":
            text = _clean_text(str(block.get("text") or block.get("heading") or ""))[:80]
            if text:
                blocks.append({"type": "h3", "text": text})
        elif kind == "image":
            ref = str(block.get("ref") or block.get("image") or "").strip()
            if ref:
                blocks.append({"type": "image", "ref": ref})
        elif kind == "faq":
            items = []
            for item in block.get("items") or []:
                if isinstance(item, dict):
                    question = _clean_text(str(item.get("q") or item.get("lead") or ""))[:400]
                    answer = _clean_text(str(item.get("a") or item.get("text") or item.get("body") or ""))[:800]
                else:
                    question, answer = "", _clean_text(str(item or ""))[:800]
                if question or answer:
                    items.append({"q": question, "a": answer})
            if items:
                blocks.append({"type": "faq", "items": items})
        else:
            text = _clean_text(str(block.get("text") or block.get("body") or ""))[:2000]
            if text:
                blocks.append({"type": "para", "text": text})
    if blocks:
        return blocks
    return _blocks_from_body(body)


def _blocks_from_body(body: str) -> list[dict]:
    text = _clean_text(body)
    if not text:
        return []
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return [{"type": "para", "text": text}]
    if all(re.match(r"^\d+[\.\)]\s+", ln) for ln in lines):
        return [{"type": "numbered", "items": [re.sub(r"^\d+[\.\)]\s+", "", ln) for ln in lines]}]
    if all(ln.startswith(("- ", "* ", "• ")) for ln in lines):
        return [{"type": "bullets", "items": [ln[2:].strip() for ln in lines]}]
    if sum(1 for ln in lines if " | " in ln) >= 2:
        rows = [[part.strip() for part in ln.split("|")] for ln in lines]
        headers = rows[0] if rows else []
        return [{"type": "table", "headers": headers, "rows": rows[1:]}]
    return [{"type": "para", "text": text}]


def _section_map(doc_json: dict) -> dict[str, list[dict]]:
    found: dict[str, list[dict]] = {}
    for item in (doc_json or {}).get("sections") or []:
        if not isinstance(item, dict):
            continue
        heading = _canonical_heading(item.get("heading") or item.get("title") or "")
        if not heading or heading in found:
            continue
        blocks = _normalize_blocks(item.get("blocks"), _clean_text(str(item.get("body") or item.get("text") or "")))
        if blocks:
            found[heading] = blocks
    return found


def _surface_for(*parts: str) -> str:
    hay = " ".join(str(part or "") for part in parts).lower()
    if any(token in hay for token in ("activate", "whatsapp", "campaign", "agentic")):
        return "Activate"
    return "Sense"


def _meta_from_doc(doc_json: dict) -> dict[str, str]:
    raw = (doc_json or {}).get("meta") or {}
    if not isinstance(raw, dict):
        raw = {}
    title = _clean_text(str((doc_json or {}).get("title") or ""))
    chips = [str(c).strip() for c in ((doc_json or {}).get("chips") or []) if str(c).strip()]
    intro = _plain_intro(_clean_text(str((doc_json or {}).get("intro") or "")))
    module = next((c for c in chips if "release" not in c.lower()), "") or _surface_for(
        title, str(raw.get("module") or ""), intro
    )
    return {
        "feature_name": _clean_text(str(raw.get("feature_name") or title))[:120],
        "module": _clean_text(str(raw.get("module") or module))[:80],
        "audience": _clean_text(str(raw.get("audience") or "Clients"))[:80],
        "teams": _clean_text(str(raw.get("teams") or "Campaign managers, operations"))[:120],
        "summary": _clean_text(str(raw.get("summary") or intro))[:400],
    }


def _heuristic_sections(feature: str) -> list[dict]:
    return [
        {
            "heading": "Background",
            "blocks": [
                {
                    "type": "bullets",
                    "items": [
                        {"lead": "Business problem it solves", "text": f"Earlier workflows made {feature} harder to use day to day."},
                        {"lead": "Who benefits", "text": "Your campaign managers and operations teams."},
                        {"lead": "What changes for the user after adopting it", "text": f"{feature} is available on the shipped surface."},
                    ],
                }
            ],
        },
        {
            "heading": "Functional Overview",
            "blocks": [
                {"type": "para", "text": f"{feature} is now available so you can review results without leaving the product."},
                {
                    "type": "bullets",
                    "items": [
                        {"lead": "What the user can create / configure / view", "text": f"Open {feature} and use the shipped fields."},
                        {"lead": "What the system does automatically", "text": "Updates the view from the current selection."},
                        {"lead": "What outputs / reports / results the user sees", "text": "The new fields and lists on the shipped surface."},
                    ],
                },
            ],
        },
        {"heading": "Navigation", "blocks": [{"type": "numbered", "items": [f"Open {feature}", "Choose the relevant surface", "Apply filters as needed"]}]},
        {
            "heading": "Key Concepts",
            "blocks": [{"type": "table", "headers": ["Term", "Meaning (functional)", "Example"], "rows": [[feature, "Shipped surface", "Open it from the product nav"]]}],
        },
        {
            "heading": "Prerequisites",
            "blocks": [
                {"type": "para", "text": "Before you start, you need:"},
                {"type": "bullets", "items": ["Access / permission available", "Required parent config completed", "Related modules enabled"]},
            ],
        },
        {
            "heading": "How to Use",
            "blocks": [
                {"type": "h3", "text": "8.1 Create / Configure"},
                {"type": "numbered", "items": ["Open the shipped surface.", f"You can see {feature} on the page."]},
                {"type": "image", "ref": "8.1"},
                {"type": "para", "text": "Expected result: the new fields are visible."},
                {"type": "h3", "text": "8.2 Enable / Attach / Activate"},
                {"type": "numbered", "items": ["Apply filters as needed.", "Open the related table."]},
                {"type": "image", "ref": "8.2"},
                {"type": "para", "text": "Expected result: metrics follow the selection."},
                {"type": "h3", "text": "8.3 Day-to-Day Usage"},
                {"type": "numbered", "items": [f"Check {feature} for the current selection."]},
                {"type": "image", "ref": "8.3"},
                {"type": "para", "text": "Expected result: trends are scoped."},
                {"type": "h3", "text": "8.4 Review Outcomes"},
                {"type": "numbered", "items": ["Note outliers."]},
                {"type": "image", "ref": "8.4"},
                {"type": "para", "text": "Expected result: one analysis pass covers the set."},
            ],
        },
        {
            "heading": "Configuration Options",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Setting", "What it controls", "Recommended use", "Impact if changed"],
                    "rows": [["Filters", "Which items feed the view", "Narrow to the accounts you own", "Clearing restores the full set"]],
                }
            ],
        },
        {
            "heading": "Outcome Analysis",
            "blocks": [
                {
                    "type": "table",
                    "headers": ["Output", "Meaning", "Where seen", "How to use it"],
                    "rows": [[feature, "Shipped result", "Overview", "Baseline before deeper analysis"]],
                }
            ],
        },
        {"heading": "Common Workflows", "blocks": [{"type": "para", "text": f"Use Case 1: Complete the day-to-day path in {feature}.\nSteps: open the surface and inspect the new fields.\nOutcome: a short list to act on."}]},
        {"heading": "FAQs", "blocks": [{"type": "faq", "items": [{"q": f"Why am I not seeing {feature}?", "a": "Open the shipped surface so you can see it once access is enabled."}]}]},
    ]


def heuristic_doc_json(title: str, features_in_short: str, branch: str = "") -> dict:
    lines = [row.strip() for row in (features_in_short or "").splitlines() if row.strip()]
    highlights = []
    for line in lines[:6]:
        clean = line.replace("  [unverified]", "").strip()
        if " — " in clean:
            lead, text = clean.split(" — ", 1)
        else:
            lead, text = clean, "Shipped on this release."
        highlights.append({"lead": lead[:80], "text": text[:400], "image": None})
    feature = (highlights[0]["lead"] if highlights else title) or "this release"
    heading = (title or feature or "Product release")[:120]
    surface = _surface_for(heading, features_in_short)
    intro = "You can now use {{" + feature + "}} in " + surface + " to get this release's outcome in one place"
    day = (branch or "").split("/")[-1]
    intro += f" from {day}." if day else "."
    return {
        "title": heading,
        "subtitle": f"{heading} — {surface}",
        "chips": ["Release Note", surface],
        "intro": intro,
        "meta": {
            "feature_name": heading,
            "module": surface,
            "audience": "Clients",
            "teams": "Campaign managers, operations",
            "summary": _plain_intro(intro),
        },
        "highlights": highlights or [{"lead": heading, "text": "You can use the shipped surface right away.", "image": None}],
        "sections": _heuristic_sections(feature),
    }


def clean_doc_json(raw: dict, features_in_short: str, screenshot_names: list[str] | None = None) -> dict:
    fallback = heuristic_doc_json(str((raw or {}).get("title") or ""), features_in_short)
    allowed = {name.lower() for name in (screenshot_names or []) if name}
    title = _clean_text(str((raw or {}).get("title") or ""))[:120]
    chips = []
    for chip in (raw or {}).get("chips") or []:
        text = _clean_text(str(chip))[:40]
        if text and text not in chips:
            chips.append(text)
    if not any("release" in c.lower() for c in chips):
        chips = ["Release Note", *chips]
    highlights = []
    for item in (raw or {}).get("highlights") or []:
        if not isinstance(item, dict):
            continue
        lead = _clean_text(str(item.get("lead") or ""))[:80]
        text = _clean_text(str(item.get("text") or ""))[:400]
        image = str(item.get("image") or "").strip() or None
        if image and image.lower() not in allowed and image not in (screenshot_names or []):
            image = None
        if lead or text:
            highlights.append({"lead": lead or "Update", "text": text, "image": image})
        if len(highlights) >= 6:
            break
    raw_map = _section_map(raw or {})
    fallback_map = _section_map(fallback)
    sections = []
    for heading in CANONICAL_HEADINGS:
        blocks = raw_map.get(heading) or fallback_map.get(heading) or []
        if heading == "Functional Overview" and highlights and not _has_list(blocks, "bullets"):
            blocks = [*blocks, {"type": "bullets", "items": highlights}]
        sections.append({"heading": heading, "blocks": blocks})
    intro = _clean_text(str((raw or {}).get("intro") or ""))
    if not title:
        title = fallback["title"]
        intro = intro or fallback["intro"]
        highlights = highlights or fallback["highlights"]
    meta_raw = (raw or {}).get("meta") if isinstance((raw or {}).get("meta"), dict) else {}
    merged = {**fallback, "title": title, "chips": chips[:4], "intro": intro[:800], "highlights": highlights, "sections": sections, "meta": meta_raw}
    subtitle = _clean_text(str((raw or {}).get("subtitle") or fallback.get("subtitle") or title))[:160]
    return {
        "title": title,
        "subtitle": subtitle,
        "chips": chips[:4],
        "intro": intro[:800],
        "meta": _meta_from_doc(merged),
        "highlights": highlights,
        "sections": sections,
    }


def generate_doc_json(
    *,
    title: str,
    features_in_short: str,
    branch: str = "",
    notes: str = "",
    screenshot_names: list[str] | None = None,
) -> dict:
    names = list(screenshot_names) if screenshot_names is not None else ["8.1", "8.2", "8.3", "8.4"]
    fallback = heuristic_doc_json(title, features_in_short, branch)
    try:
        raw = chat_json(
            surface="comms_doc",
            system=COMMS_DOC_PROMPT,
            payload={
                "title": title,
                "branch": branch,
                "features_in_short": features_in_short,
                "notes_excerpt": (notes or "")[:4000],
                "screenshot_filenames": names,
            },
            temperature=0.5,
            max_chars=20000,
            timeout=300,
            reasoning_effort="high",
        )
        return clean_doc_json(raw, features_in_short, names)
    except LLMJsonError:
        log.exception("comms_doc LLM failed; using heuristic doc JSON")
        return fallback
    except Exception:
        log.exception("comms_doc failed; using heuristic doc JSON")
        return fallback


def publish_doc(job, doc_json: dict, screenshots: dict[str, str] | None = None) -> tuple[str, str]:
    day = (getattr(job, "branch", "") or "").split("/")[-1]
    year_month = day[:7] if len(day) >= 7 else now_local().strftime("%Y-%m")
    meta = (doc_json or {}).get("meta") if isinstance((doc_json or {}).get("meta"), dict) else {}
    feature = str(meta.get("feature_name") or (doc_json or {}).get("title") or "Release notes")
    title = drive_doc_name(feature)
    previous = getattr(job, "drive_file_id", "") or ""
    if previous and previous != "dryrun":
        trash_file(previous)
    doc_id, url = create_release_doc(title, year_month)
    set_doc_margins(doc_id)
    write_release_notes_doc(doc_id, doc_json, screenshots or {})
    return doc_id, url


def export_pdf(doc_id: str, out: Path) -> Path:
    from googleapiclient.http import MediaIoBaseDownload
    import io

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    drive = _drive()
    request = drive.files().export_media(fileId=doc_id, mimeType="application/pdf")
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    out.write_bytes(buffer.getvalue())
    return out

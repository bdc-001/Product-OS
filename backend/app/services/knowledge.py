"""Personal notes and local documents available as explicit Copilot evidence."""
from datetime import datetime
from io import BytesIO
from pathlib import Path
import re
import uuid
import zipfile
import xml.etree.ElementTree as ET
from app.config import ROOT
from app.models import DailyNote, LibraryDocument

LIBRARY_DIR = ROOT / "data" / "library"
MAX_BYTES = 20 * 1024 * 1024
BLOCK_TYPES = ("paragraph", "heading", "actionable", "decision", "learning")
NOTE_KINDS = ("daily", "meeting", "decision", "learning")
TICKET_RE = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")


def _block_id():
    return uuid.uuid4().hex[:12]


def normalize_block(raw) -> dict | None:
    if not isinstance(raw, dict):
        return None
    typ = raw.get("type") if raw.get("type") in BLOCK_TYPES else "paragraph"
    text = str(raw.get("text") or "")[:8000]
    out = {"id": str(raw.get("id") or _block_id())[:32], "type": typ, "text": text}
    if typ == "actionable":
        out["done"] = bool(raw.get("done"))
        key = str(raw.get("ticket_key") or "").strip().upper()
        if not key:
            found = TICKET_RE.search(text)
            key = found.group(1) if found else ""
        if TICKET_RE.fullmatch(key):
            out["ticket_key"] = key
    return out


def blocks_from_legacy(body: str = "", learning: str = "") -> list[dict]:
    blocks = []
    for chunk in re.split(r"\n\n+", body or ""):
        chunk = chunk.strip()
        if not chunk:
            continue
        if chunk.startswith("# "):
            blocks.append(normalize_block({"type": "heading", "text": chunk[2:].strip()}))
        elif chunk.lower().startswith("actionable:"):
            rest = re.sub(r"(?i)^actionable:\s*", "", chunk).strip()
            done = rest.startswith("[x]") or rest.startswith("[X]")
            rest = re.sub(r"^\[(?:x|X| )\]\s*", "", rest)
            found = TICKET_RE.search(rest)
            blocks.append(normalize_block({"type": "actionable", "text": rest, "done": done, "ticket_key": found.group(1) if found else ""}))
        elif chunk.lower().startswith("decision:"):
            blocks.append(normalize_block({"type": "decision", "text": re.sub(r"(?i)^decision:\s*", "", chunk).strip()}))
        elif chunk.lower().startswith("learning:"):
            blocks.append(normalize_block({"type": "learning", "text": re.sub(r"(?i)^learning:\s*", "", chunk).strip()}))
        else:
            blocks.append(normalize_block({"type": "paragraph", "text": chunk}))
    if (learning or "").strip() and not any(item and item.get("type") == "learning" for item in blocks):
        blocks.append(normalize_block({"type": "learning", "text": learning.strip()}))
    return [item for item in blocks if item] or [normalize_block({"type": "paragraph", "text": ""})]


def serialize_blocks(blocks: list[dict]) -> tuple[str, str]:
    lines = []
    learning = []
    for item in blocks:
        typ = item.get("type")
        text = (item.get("text") or "").strip()
        if not text:
            continue
        if typ == "heading":
            lines.append(f"# {text}")
        elif typ == "actionable":
            mark = "x" if item.get("done") else " "
            key = f" ({item['ticket_key']})" if item.get("ticket_key") else ""
            lines.append(f"Actionable: [{mark}] {text}{key}")
        elif typ == "decision":
            lines.append(f"Decision: {text}")
        elif typ == "learning":
            lines.append(f"Learning: {text}")
            learning.append(text)
        else:
            lines.append(text)
    return "\n\n".join(lines).strip(), "\n\n".join(learning)


def note_blocks(row) -> list[dict]:
    raw = getattr(row, "blocks", None)
    if isinstance(raw, list) and raw:
        return [item for item in (normalize_block(item) for item in raw[:80]) if item]
    return blocks_from_legacy(row.body or "", row.learning or "")


def apply_blocks(row, blocks, kind: str | None = None) -> None:
    clean = [item for item in (normalize_block(item) for item in (blocks or [])[:80]) if item]
    if not clean:
        clean = [normalize_block({"type": "paragraph", "text": ""})]
    body, learning = serialize_blocks(clean)
    row.blocks = clean
    row.body = body
    row.learning = learning
    if kind in NOTE_KINDS:
        row.kind = kind


def persist_note_fields(row, *, day: str, title: str, body: str, learning: str, tags: list, kind: str | None, blocks) -> None:
    row.day = day
    row.title = title
    row.tags = tags or []
    next_kind = kind if kind in NOTE_KINDS else (getattr(row, "kind", None) or "daily")
    if blocks is not None:
        apply_blocks(row, blocks, next_kind)
        return
    row.body = body or ""
    row.learning = learning or ""
    row.kind = next_kind
    row.blocks = blocks_from_legacy(row.body, row.learning)


def note_has_kind(row, kind: str) -> bool:
    if kind in ("", "all"):
        return True
    blocks = note_blocks(row)
    if kind == "actionable":
        return any(item.get("type") == "actionable" for item in blocks) or "Actionable:" in (row.body or "")
    if kind in ("decision", "learning"):
        return (getattr(row, "kind", None) or "daily") == kind or any(item.get("type") == kind for item in blocks)
    return (getattr(row, "kind", None) or "daily") == kind


def note_out(row):
    blocks = note_blocks(row)
    kind = getattr(row, "kind", None) or "daily"
    return {
        "id": row.id,
        "day": row.day,
        "title": row.title,
        "body": row.body,
        "learning": row.learning,
        "kind": kind if kind in NOTE_KINDS else "daily",
        "blocks": blocks,
        "actionable_count": sum(1 for item in blocks if item.get("type") == "actionable" and not item.get("done")),
        "tags": row.tags or [],
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def document_out(row, detail=False):
    out = {"id": row.id, "title": row.title, "filename": row.filename, "size": row.size, "tags": row.tags or [], "status": row.status, "indexed": bool(row.text.strip()), "pages": len(row.pages or []), "extraction_note": row.extraction_note, "url": f"/api/library/documents/{row.id}/file", "created_at": row.created_at.isoformat()}
    if detail: out["text"] = row.text[:20000]
    return out


def extract(name, data):
    suffix = Path(name).suffix.lower()
    pages = []
    mime = "text/plain"
    if suffix == ".pdf":
        from pypdf import PdfReader
        if not data.startswith(b"%PDF-"): raise ValueError("The file is not a valid PDF.")
        try:
            reader = PdfReader(BytesIO(data))
            if reader.is_encrypted: raise ValueError("Upload an unlocked PDF.")
            if len(reader.pages) > 500: raise ValueError("PDFs may contain at most 500 pages.")
            pages = [{"page": i + 1, "text": p.extract_text() or ""} for i, p in enumerate(reader.pages)]
        except ValueError: raise
        except Exception as exc: raise ValueError("This PDF could not be read. Export it again and retry.") from exc
        mime = "application/pdf"
    elif suffix == ".docx":
        try:
            with zipfile.ZipFile(BytesIO(data)) as archive:
                info = archive.getinfo("word/document.xml")
                if info.file_size > MAX_BYTES: raise ValueError("Document text is too large.")
                root = ET.fromstring(archive.read(info))
                text = "\n".join("".join(n.itertext()) for n in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"))
            pages = [{"page": 1, "text": text}]
        except Exception as exc: raise ValueError("This Word document could not be read.") from exc
        mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    elif suffix in {".txt", ".md"}:
        try: pages = [{"page": 1, "text": data.decode("utf-8")}]
        except UnicodeDecodeError as exc: raise ValueError("Save the text file as UTF-8 and try again.") from exc
    else: raise ValueError("Upload a PDF, DOCX, Markdown, or text file.")
    # Explicitly report any truncation rather than presenting partial coverage as complete.
    text = "\n\n".join(p["text"] for p in pages)
    note = "" if text.strip() else "No readable text found. Scanned PDFs need OCR before Copilot can read them."
    if len(text) > 1000000: raise ValueError("Extracted text exceeds 1 million characters. Split this document before uploading.")
    return mime, pages, text, note


def store_document(db, name, data):
    if not data or len(data) > MAX_BYTES: raise ValueError("Choose a non-empty file up to 20 MB.")
    name = Path(name.replace("\\", "/")).name[:240]
    mime, pages, text, note = extract(name, data)
    file_id = f"{uuid.uuid4()}{Path(name).suffix.lower()}"
    LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    path = LIBRARY_DIR / file_id
    path.write_bytes(data)
    row = LibraryDocument(title=Path(name).stem, filename=name, file_id=file_id, media_type=mime, size=len(data), text=text, pages=pages, extraction_note=note)
    db.add(row)
    try: db.commit(); db.refresh(row)
    except Exception:
        db.rollback(); path.unlink(missing_ok=True); raise
    return document_out(row)


def context(db, question, document_ids=None, note_ids=None):
    tokens = set(re.findall(r"[a-z0-9_]{3,}", question.lower())) - {"the", "and", "what", "this", "that", "with", "from", "how", "does", "explain", "please"}
    docs = db.query(LibraryDocument)
    notes = db.query(DailyNote)
    if document_ids: docs = docs.filter(LibraryDocument.id.in_(document_ids))
    if note_ids: notes = notes.filter(DailyNote.id.in_(note_ids))
    candidates = []
    for row in docs.all():
        for page in row.pages or []:
            text = page["text"]
            for start in range(0, len(text), 2400):
                excerpt = text[start:start + 3000]
                score = sum(t in (row.title + " " + excerpt).lower() for t in tokens)
                if score or document_ids:
                    candidates.append((score, {"path": f"Document {row.id}: {row.title} · page {page['page']}", "url": f"/api/library/documents/{row.id}/file", "text": excerpt, "kind": "document", "id": row.id}))
    for row in notes.order_by(DailyNote.day.desc()).all():
        text = f"{row.title}\n{getattr(row, 'kind', 'daily')}\n{row.body}\nLearning: {row.learning}"
        score = sum(t in text.lower() for t in tokens)
        if score or note_ids or re.search(r"recent.*notes|daily notes|my notes|my.*learning", question, re.I):
            candidates.append((score, {"path": f"Note {row.id}: {row.day} · {row.title}", "url": f"/notes?note={row.id}", "text": text[:4000], "kind": "note", "id": row.id}))
    return [item for _, item in sorted(candidates, key=lambda pair: pair[0], reverse=True)[:8]]


_ACTION_HINT = re.compile(r"\b(todo|action|follow[- ]?up|need to|needs to|please|assign|file (?:a )?ticket|next step)\b", re.I)
_DECISION_HINT = re.compile(r"\b(decid(?:ed|e|ing)|decision|agreed|we will)\b", re.I)
_LEARNING_HINT = re.compile(r"\b(learn(?:ed|ing)|takeaway|realis(?:ed|ed))\b", re.I)


def _plain_lines(blocks: list[dict], body: str, learning: str) -> list[str]:
    if blocks:
        return [str(item.get("text") or "").strip() for item in blocks if str(item.get("text") or "").strip()]
    return [chunk.strip() for chunk in re.split(r"\n+", f"{body or ''}\n{learning or ''}") if chunk.strip()]


def heuristic_assist(action: str, title: str, blocks: list[dict], body: str, learning: str) -> dict:
    current = [item for item in (normalize_block(item) for item in (blocks or [])) if item] or blocks_from_legacy(body, learning)
    lines = _plain_lines(current, body, learning)
    if action == "summarize":
        summary = " ".join(lines)[:420].strip()
        if not summary:
            return {"title": title, "blocks": current, "llm_used": False}
        heading = normalize_block({"type": "heading", "text": "Summary"})
        para = normalize_block({"type": "paragraph", "text": summary})
        rest = [item for item in current if not (item.get("type") == "heading" and (item.get("text") or "").strip().lower() == "summary")]
        if rest and rest[0].get("type") == "paragraph" and rest[0].get("text") == summary:
            rest = rest[1:]
        return {"title": title, "blocks": [heading, para, *rest], "llm_used": False}
    if action == "extract":
        existing = {(item.get("text") or "").strip().lower() for item in current if item.get("type") == "actionable"}
        added = []
        for line in lines:
            if not _ACTION_HINT.search(line):
                continue
            key = line.strip().lower()
            if key in existing:
                continue
            added.append(normalize_block({"type": "actionable", "text": line.strip()}))
            existing.add(key)
        return {"title": title, "blocks": current + [item for item in added if item], "llm_used": False}
    structured = []
    for line in lines:
        if line.startswith("# "):
            structured.append(normalize_block({"type": "heading", "text": line[2:].strip()}))
        elif _ACTION_HINT.search(line):
            structured.append(normalize_block({"type": "actionable", "text": line}))
        elif _DECISION_HINT.search(line):
            structured.append(normalize_block({"type": "decision", "text": line}))
        elif _LEARNING_HINT.search(line):
            structured.append(normalize_block({"type": "learning", "text": line}))
        else:
            structured.append(normalize_block({"type": "paragraph", "text": line}))
    return {"title": title, "blocks": [item for item in structured if item] or current, "llm_used": False}


def assist_note(action: str, title: str = "", blocks: list | None = None, body: str = "", learning: str = "") -> dict:
    current = [item for item in (normalize_block(item) for item in (blocks or [])) if item] or blocks_from_legacy(body, learning)
    fallback = heuristic_assist(action, title, current, body, learning)
    try:
        from app.clients.llm import chat_json
        parsed = chat_json(
            "notes",
            """You help Arsalaan structure PM notes for Convin Sense.
Return a single JSON object. Do not invent Jira keys, dates, or facts.
Keep the author's wording. Short blocks.
Each block is {"type": "paragraph"|"heading"|"actionable"|"decision"|"learning", "text": string, "done": optional boolean}.
For summarize: put a heading "Summary" then one short paragraph, then the original blocks without duplicating that summary.
For structure: rewrite the dump into typed blocks (meeting headings, actionables, decisions, learning).
For extract: return the original blocks plus any new actionable follow-ups that were not already listed.""",
            {"action": action, "title": title, "blocks": [{"type": item.get("type"), "text": item.get("text")} for item in current]},
            max_chars=12000,
            timeout=60,
        )
    except Exception:
        return fallback
    raw_blocks = parsed.get("blocks") if isinstance(parsed, dict) else None
    if not isinstance(raw_blocks, list) or not raw_blocks:
        return fallback
    clean = [item for item in (normalize_block(item) for item in raw_blocks[:80]) if item]
    if not clean:
        return fallback
    next_title = str(parsed.get("title") or title or "")[:256]
    return {"title": next_title, "blocks": clean, "llm_used": True}

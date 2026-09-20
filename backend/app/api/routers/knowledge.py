from datetime import date, datetime
from typing import Literal
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import DailyNote, LibraryDocument
from app.services.knowledge import LIBRARY_DIR, MAX_BYTES, document_out, note_out, store_document, persist_note_fields, assist_note, note_has_kind, NOTE_KINDS

router = APIRouter()

class NoteBody(BaseModel):
    day: date
    title: str = Field(default="Daily note", max_length=256)
    body: str = Field(default="", max_length=100000)
    learning: str = Field(default="", max_length=100000)
    kind: Literal["daily", "meeting", "decision", "learning"] = "daily"
    blocks: list[dict] | None = None
    tags: list[str] = Field(default_factory=list, max_length=30)

class AssistBody(BaseModel):
    action: Literal["summarize", "structure", "extract"]
    title: str = Field(default="", max_length=256)
    body: str = Field(default="", max_length=100000)
    learning: str = Field(default="", max_length=100000)
    blocks: list[dict] | None = None

class DocumentBody(BaseModel):
    title: str | None = Field(default=None, max_length=256)
    status: Literal["to_read", "reading", "completed"] | None = None
    tags: list[str] | None = Field(default=None, max_length=30)

@router.get("/notes")
def notes(q: str = "", day: str = "", kind: str = "", offset: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    query = db.query(DailyNote)
    if q: query = query.filter(or_(DailyNote.title.contains(q), DailyNote.body.contains(q), DailyNote.learning.contains(q)))
    if day: query = query.filter(DailyNote.day == day)
    limit = min(100, max(1, limit))
    offset = max(0, offset)
    if kind in ("actionable", "decision", "learning"):
        rows = [row for row in query.order_by(DailyNote.day.desc(), DailyNote.id.desc()).all() if note_has_kind(row, kind)]
        return {"total": len(rows), "notes": [note_out(row) for row in rows[offset: offset + limit]]}
    if kind in NOTE_KINDS:
        if kind == "daily":
            query = query.filter(or_(DailyNote.kind == "daily", DailyNote.kind == "", DailyNote.kind.is_(None)))
        else:
            query = query.filter(DailyNote.kind == kind)
    return {"total": query.count(), "notes": [note_out(r) for r in query.order_by(DailyNote.day.desc(), DailyNote.id.desc()).offset(offset).limit(limit).all()]}

@router.post("/notes/assist")
def notes_assist(body: AssistBody):
    return assist_note(body.action, body.title, body.blocks, body.body, body.learning)

@router.get("/notes/{note_id}")
def note(note_id: int, db: Session = Depends(get_db)):
    row = db.get(DailyNote, note_id)
    if not row: raise HTTPException(404, "Note not found")
    return note_out(row)

@router.post("/notes")
def create_note(body: NoteBody, db: Session = Depends(get_db)):
    row = DailyNote()
    persist_note_fields(row, day=body.day.isoformat(), title=body.title, body=body.body, learning=body.learning, tags=body.tags, kind=body.kind, blocks=body.blocks)
    db.add(row); db.commit(); db.refresh(row)
    return note_out(row)

@router.put("/notes/{note_id}")
def update_note(note_id: int, body: NoteBody, db: Session = Depends(get_db)):
    row = db.get(DailyNote, note_id)
    if not row: raise HTTPException(404, "Note not found")
    persist_note_fields(row, day=body.day.isoformat(), title=body.title, body=body.body, learning=body.learning, tags=body.tags, kind=body.kind, blocks=body.blocks)
    row.updated_at = datetime.utcnow()
    db.commit(); db.refresh(row)
    return note_out(row)

@router.delete("/notes/{note_id}")
def delete_note(note_id: int, db: Session = Depends(get_db)):
    row = db.get(DailyNote, note_id)
    if not row:
        raise HTTPException(404, "Note not found")
    db.delete(row)
    db.commit()
    return {"ok": True, "id": note_id}

@router.get("/library/documents")
def documents(q: str = "", offset: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    query = db.query(LibraryDocument)
    if q: query = query.filter(or_(LibraryDocument.title.contains(q), LibraryDocument.text.contains(q)))
    return {"total": query.count(), "documents": [document_out(r) for r in query.order_by(LibraryDocument.id.desc()).offset(max(0,offset)).limit(min(100,max(1,limit))).all()]}

@router.post("/library/documents")
def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try: return store_document(db, file.filename or "document", file.file.read(MAX_BYTES + 1))
    except ValueError as exc: raise HTTPException(400, str(exc)) from exc

@router.get("/library/documents/{document_id}")
def document(document_id: int, db: Session = Depends(get_db)):
    row = db.get(LibraryDocument, document_id)
    if not row: raise HTTPException(404, "Document not found")
    return document_out(row, detail=True)

@router.patch("/library/documents/{document_id}")
def patch_document(document_id: int, body: DocumentBody, db: Session = Depends(get_db)):
    row = db.get(LibraryDocument, document_id)
    if not row: raise HTTPException(404, "Document not found")
    for key, value in body.model_dump(exclude_none=True).items(): setattr(row,key,value)
    db.commit(); db.refresh(row)
    return document_out(row)

@router.get("/library/documents/{document_id}/file")
def document_file(document_id: int, db: Session = Depends(get_db)):
    row = db.get(LibraryDocument, document_id)
    if not row: raise HTTPException(404, "Document not found")
    path = (LIBRARY_DIR / row.file_id).resolve()
    if path.parent != LIBRARY_DIR.resolve() or not path.is_file(): raise HTTPException(404, "File is unavailable")
    return FileResponse(path, media_type=row.media_type, filename=row.filename, content_disposition_type="inline" if row.media_type == "application/pdf" else "attachment")

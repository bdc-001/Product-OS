from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from app.models import Prd, LibraryDocument
from app.services.prd import prd_out
from app.services.knowledge import store_document, document_out
import hashlib

from app.api.common import PrdBody
from app.database import get_db
from app.services.codebase import snapshot_out
from app.services.pdf_notes import write_release_pdf
from app.services.prd import generate_prd, get_prd, list_prds
from app.config import ROOT
from app.storage import WorkspaceDir

router = APIRouter()
PRD_PDF_DIR = WorkspaceDir("prds")


@router.get("/prd")
def prd_list(db: Session = Depends(get_db)):
    return {"prds": list_prds(db), "codebase": snapshot_out(db, live=False, include_modules=True)}


@router.get("/prd/{prd_id}/pdf")
def prd_pdf(prd_id: int, db: Session = Depends(get_db)):
    row = get_prd(db, prd_id)
    if not row:
        raise HTTPException(status_code=404, detail="PRD not found")
    PRD_PDF_DIR.mkdir(parents=True, exist_ok=True)
    dest = PRD_PDF_DIR / f"prd-{prd_id}.pdf"
    title = (row.get("title") or "PRD").strip() or "PRD"
    write_release_pdf(
        title=title,
        branch=row.get("branch") or "",
        sha=row.get("commit_sha") or "",
        body=row.get("markdown") or "",
        dest=dest,
        audience="Internal",
        heading="Product requirements",
        branded=False,
    )
    safe = "".join(ch if ch.isalnum() or ch in "._- " else "-" for ch in title).strip(" .-")[:80] or "PRD"
    return FileResponse(path=dest, media_type="application/pdf", filename=f"{safe}.pdf")


@router.get("/prd/{prd_id}")
def prd_detail(prd_id: int, db: Session = Depends(get_db)):
    row = get_prd(db, prd_id)
    if not row:
        raise HTTPException(status_code=404, detail="PRD not found")
    return row


@router.post("/prd/generate")
def prd_generate(body: PrdBody, db: Session = Depends(get_db)):
    if not (body.title or "").strip() and not (body.problem or "").strip() and not (body.issue_key or body.issue_keys) and not body.prototype_id:
        raise HTTPException(status_code=400, detail="Tag at least one ticket, attach a prototype, or add a title / problem.")
    try:
        return generate_prd(
            db,
            title=(body.title or "").strip(),
            problem=(body.problem or "").strip(),
            service=(body.service or "").strip(),
            issue_key=(body.issue_key or "").strip(),
            issue_keys=body.issue_keys or [],
            prototype_id=int(body.prototype_id or 0),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


class PrdEdit(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    markdown: str = Field(default="", max_length=100000)


@router.post("/prd")
def create_prd(body: PrdEdit, db: Session = Depends(get_db)):
    row = Prd(title=body.title.strip() or "Untitled", markdown=body.markdown)
    db.add(row)
    db.commit()
    db.refresh(row)
    return prd_out(row)


@router.put("/prd/{prd_id}")
def save_prd(prd_id: int, body: PrdEdit, db: Session = Depends(get_db)):
    row = db.get(Prd, prd_id)
    if not row:
        raise HTTPException(404, "PRD not found")
    row.title = body.title.strip() or "Untitled"
    row.markdown = body.markdown
    db.commit()
    db.refresh(row)
    return prd_out(row)


@router.post("/prd/{prd_id}/library")
def save_prd_pdf(prd_id: int, db: Session = Depends(get_db)):
    row = db.get(Prd, prd_id)
    if not row:
        raise HTTPException(404, "PRD not found")
    # A saved PDF is an immutable snapshot; repeated saves reuse the same version.
    version = hashlib.sha256((row.title + "\0" + row.markdown).encode()).hexdigest()
    tag = f"prd:{prd_id}:{version}"
    existing = db.query(LibraryDocument).filter(LibraryDocument.tags.contains(tag)).first()
    if existing:
        return document_out(existing)
    from tempfile import TemporaryDirectory
    from pathlib import Path
    with TemporaryDirectory() as folder:
        dest = Path(folder) / "prd.pdf"
        write_release_pdf(title=row.title, branch=row.branch, sha=row.commit_sha,
                          body=row.markdown, dest=dest, audience="Internal", heading="Product requirements", branded=False)
        safe = "".join(ch if ch.isalnum() or ch in "._- " else "-" for ch in row.title).strip(" .-")[:80] or "PRD"
        result = store_document(db, f"{safe}.pdf", dest.read_bytes())
    document = db.get(LibraryDocument, result["id"])
    document.title = row.title
    document.tags = ["prd", tag]
    db.commit()
    return document_out(document)

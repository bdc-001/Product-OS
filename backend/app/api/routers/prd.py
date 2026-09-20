from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.common import PrdBody
from app.database import get_db
from app.services.codebase import snapshot_out
from app.services.pdf_notes import write_release_pdf
from app.services.prd import generate_prd, get_prd, list_prds
from app.config import ROOT

router = APIRouter()
PRD_PDF_DIR = ROOT / "data" / "prds"


@router.get("/prd")
def prd_list(db: Session = Depends(get_db)):
    return {"prds": list_prds(db), "codebase": snapshot_out(db)}


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
        heading="CONVIN  ·  Product requirements",
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

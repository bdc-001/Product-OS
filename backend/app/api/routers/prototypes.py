from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session
import html as html_lib

from app.database import get_db
from app.models import Prototype, PrototypeFile
from app.services.jobs import enqueue, job_out
from app.services.prototype import (
    PrototypePathError,
    export_zip,
    preview_target,
    prototype_out,
    put_file,
    run_turn,
    seed_prototype,
)

router = APIRouter()


class CreateBody(BaseModel):
    title: str = Field(default="", max_length=180)
    prompt: str = Field(default="", max_length=8000)


class TurnBody(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000)
    target: str = Field(default="", max_length=256)


class FileBody(BaseModel):
    path: str = Field(min_length=1, max_length=256)
    content: str = Field(default="", max_length=400000)


def _row(db: Session, prototype_id: int) -> Prototype:
    row = db.get(Prototype, prototype_id)
    if not row:
        raise HTTPException(status_code=404, detail="Prototype not found")
    return row


@router.get("/prototypes")
def list_prototypes(db: Session = Depends(get_db)):
    rows = db.query(Prototype).order_by(Prototype.updated_at.desc(), Prototype.id.desc()).limit(80).all()
    ids = [row.id for row in rows]
    counts = (
        dict(
            db.query(PrototypeFile.prototype_id, func.count())
            .filter(PrototypeFile.prototype_id.in_(ids))
            .group_by(PrototypeFile.prototype_id)
            .all()
        )
        if ids
        else {}
    )
    out = []
    for row in rows:
        data = prototype_out(row, db)
        data["file_count"] = int(counts.get(row.id) or 0)
        out.append(data)
    return {"prototypes": out}


@router.post("/prototypes")
def create_prototype(body: CreateBody, db: Session = Depends(get_db)):
    row = seed_prototype(db, title=body.title, prompt=body.prompt)
    if not body.prompt.strip():
        return prototype_out(row, db, detail=True)

    def work(session, set_step):
        set_step("generate", {"status": "running"})
        return run_turn(session, row.id, body.prompt.strip())

    job = enqueue(db, f"prototype-{row.id}", work)
    return JSONResponse(status_code=202, content={**job_out(job), "prototype_id": row.id})


@router.get("/prototypes/{prototype_id}")
def get_prototype(prototype_id: int, db: Session = Depends(get_db)):
    return prototype_out(_row(db, prototype_id), db, detail=True)


@router.post("/prototypes/{prototype_id}/turn")
def prototype_turn(prototype_id: int, body: TurnBody, db: Session = Depends(get_db)):
    row = _row(db, prototype_id)
    if row.status == "generating":
        raise HTTPException(status_code=409, detail="A generate turn is already running.")

    def work(session, set_step):
        set_step("generate", {"status": "running"})
        return run_turn(session, prototype_id, body.prompt.strip(), target=body.target.strip())

    job = enqueue(db, f"prototype-{prototype_id}", work)
    return JSONResponse(status_code=202, content={**job_out(job), "prototype_id": prototype_id})


@router.put("/prototypes/{prototype_id}/files")
def update_file(prototype_id: int, body: FileBody, db: Session = Depends(get_db)):
    _row(db, prototype_id)
    try:
        return put_file(db, prototype_id, body.path, body.content)
    except PrototypePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/prototypes/{prototype_id}/preview")
def live_preview(prototype_id: int, db: Session = Depends(get_db)):
    _row(db, prototype_id)
    try:
        url, error = preview_target(db, prototype_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if url:
        return RedirectResponse(url, status_code=302)
    message = html_lib.escape(error or "Sense preview could not start.")
    html = (
        "<!doctype html><html><head><meta charset='utf-8'><title>Sense preview</title></head>"
        f"<body style='font-family:Figtree,sans-serif;padding:48px;color:#374151'>"
        f"<h1>Sense preview</h1><p>{message}</p></body></html>"
    )
    return HTMLResponse(content=html, headers={"Cache-Control": "no-store"})


@router.get("/prototypes/{prototype_id}/export")
def download_export(prototype_id: int, db: Session = Depends(get_db)):
    row = _row(db, prototype_id)
    try:
        data = export_zip(db, prototype_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    name = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in (row.title or "prototype"))[:40] or "prototype"
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{name}.zip"'},
    )

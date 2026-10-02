from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.common import RoadmapBody
from app.database import get_db
from app.services.roadmap import generate_roadmap, latest_roadmap, resolve_ticket_pdf, save_roadmap, store_ticket_pdf

router = APIRouter()


@router.get("/roadmap")
def roadmap_get(db: Session = Depends(get_db)):
    return {"roadmap": latest_roadmap(db)}


@router.post("/roadmap/generate")
def roadmap_generate(db: Session = Depends(get_db)):
    try:
        return generate_roadmap(db)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.patch("/roadmap")
def roadmap_save(body: RoadmapBody, db: Session = Depends(get_db)):
    try:
        return save_roadmap(db, body.model_dump(exclude_none=True))
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/roadmap/files")
async def roadmap_upload(file: UploadFile = File(...)):
    data = await file.read(10 * 1024 * 1024 + 1)
    try:
        return store_ticket_pdf(original_name=file.filename or "attachment.pdf", data=data)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/roadmap/files/{file_id}")
def roadmap_file(file_id: str):
    try:
        path = resolve_ticket_pdf(file_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(path, media_type="application/pdf")

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.common import CopilotPlanBody, CopilotRunBody, CopilotUndoBody
from app.database import get_db
from app.services.copilot import (
    get_plan,
    list_mentions,
    plan_copilot,
    resolve_copilot_image,
    run_copilot,
    store_copilot_image,
    thread_out,
    undo_copilot,
)

router = APIRouter()


@router.get("/copilot/mentions")
def copilot_mentions(q: str = "", db: Session = Depends(get_db)):
    return list_mentions(db, q)


@router.get("/copilot/thread")
def copilot_thread(db: Session = Depends(get_db)):
    return thread_out(db)


@router.get("/copilot/plans/{plan_id}")
def copilot_plan_get(plan_id: int, db: Session = Depends(get_db)):
    row = get_plan(db, plan_id)
    if not row:
        raise HTTPException(status_code=404, detail="Plan not found")
    return row


@router.post("/copilot/plan")
def copilot_plan(body: CopilotPlanBody, db: Session = Depends(get_db)):
    try:
        return plan_copilot(
            db,
            prompt=body.prompt or "",
            document_ids=body.document_ids,
            note_ids=body.note_ids,
            prototype_ids=body.prototype_ids,
            parent_plan_id=body.parent_plan_id,
            code_scope=body.code_scope,
            notes=body.notes or "",
            branch=body.branch or "",
            ticket_keys=body.ticket_keys or [],
            people=body.people or [],
            image_ids=body.image_ids or [],
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/copilot/run")
def copilot_run(body: CopilotRunBody, db: Session = Depends(get_db)):
    if not body.approved:
        raise HTTPException(status_code=403, detail="Approve the plan before any Jira change.")
    try:
        return run_copilot(
            db,
            plan_id=body.plan_id,
            approved=True,
            action_ids=body.action_ids or [],
            overrides=body.overrides or {},
        )
    except RuntimeError as exc:
        message = str(exc)
        code = 403 if "Approve" in message else 400
        raise HTTPException(status_code=code, detail=message) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/copilot/undo")
def copilot_undo(body: CopilotUndoBody, db: Session = Depends(get_db)):
    try:
        return undo_copilot(db, body.plan_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/copilot/files")
async def copilot_upload(file: UploadFile = File(...)):
    data = await file.read()
    try:
        return store_copilot_image(original_name=file.filename or "attachment.png", data=data)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/copilot/files/{file_id}")
def copilot_file(file_id: str):
    try:
        path, meta = resolve_copilot_image(file_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(path, media_type=meta.get("mime") or "application/octet-stream", filename=meta.get("name") or file_id)

@router.get("/copilot/conversations")
def conversations(db: Session = Depends(get_db)):
    from app.models import CopilotPlan
    rows = db.query(CopilotPlan.id, CopilotPlan.parent_plan_id, CopilotPlan.prompt, CopilotPlan.notes, CopilotPlan.needs_confirm, CopilotPlan.status).order_by(CopilotPlan.id.desc()).limit(100).all()
    return {"id": 0, "turns": [], "plans": [{"id": r.id, "parent_plan_id": r.parent_plan_id, "prompt": r.prompt[:240], "notes": r.notes[:240], "needs_confirm": r.needs_confirm, "status": r.status} for r in rows]}

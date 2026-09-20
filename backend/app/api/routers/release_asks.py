from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.release_asks import dismiss_ticket, list_release_asks, send_nudge

router = APIRouter()


class NudgeBody(BaseModel):
    pm: str = ""


class DismissBody(BaseModel):
    issue_key: str = ""


@router.get("/release-asks")
def release_asks_list():
    return list_release_asks()


@router.post("/release-asks/dismiss")
def release_asks_dismiss(body: DismissBody):
    try:
        return dismiss_ticket(body.issue_key)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/release-asks/nudge")
def release_asks_nudge(body: NudgeBody | None = None):
    try:
        return send_nudge(pm=(body.pm if body else "") or None)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

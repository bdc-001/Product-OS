"""HeyGen avatar video pipeline API. Separate from /marketing campaigns and launch films."""
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.auth import Principal, current_principal
from app.clients.cartesia import CartesiaClient, CartesiaError
from app.clients.elevenlabs import ElevenLabsClient, ElevenLabsError
from app.clients.heygen import HeyGenError
from app.clients.llm import LLMJsonError
from app.database import get_db
from app.models import AvatarVideo, MarketingFeature
from app.services import marketing_avatar as avatar

router = APIRouter(prefix="/avatar-videos", tags=["avatar-videos"])


def _default_guard(principal: Principal, make_default: bool) -> None:
    if make_default and not principal.at_least("admin"):
        raise HTTPException(403, "Only workspace admins can change the default voice. Clone without making it the default.")


class OptionsBody(BaseModel):
    aspect_ratio: Literal["16:9", "9:16", "1:1", "4:5", "auto"] = "16:9"
    resolution: Literal["1080p", "720p"] = "1080p"
    engine: Literal["avatar_iv", "avatar_v", "avatar_iii"] = "avatar_iv"
    speed: float = Field(default=1.0, ge=0.5, le=1.5)
    background: str = Field(default="", pattern=r"^(#[0-9a-fA-F]{6})?$")
    pauses: bool = True
    expressiveness: Literal["low", "medium", "high"] = "low"
    motion_prompt: str = Field(default=avatar.PRESENTER_MOTION, max_length=avatar.MAX_MOTION_PROMPT)


class VideoBody(BaseModel):
    title: str = Field(default="", max_length=180)
    feature_id: int | None = None
    script: str = Field(default="", max_length=avatar.MAX_SCRIPT_CHARS)
    avatar_id: str = Field(default="", max_length=120)
    avatar_name: str = Field(default="", max_length=180)
    avatar_type: str = Field(default="", max_length=32)
    avatar_preview_url: str = Field(default="", max_length=2000)
    voice_id: str = Field(default="", max_length=120)
    voice_name: str = Field(default="", max_length=180)
    options: OptionsBody = Field(default_factory=OptionsBody)
    render: bool = False


class ScriptBody(BaseModel):
    feature_id: int | None = None
    brief: str = Field(default="", max_length=4000)
    seconds: int = Field(default=60, ge=15, le=180)
    angle: str = Field(default="", max_length=500)


PROVIDER_ERRORS = (HeyGenError, CartesiaError, ElevenLabsError)


def _heygen_error(exc: HeyGenError | CartesiaError | ElevenLabsError) -> HTTPException:
    return HTTPException(502 if exc.status == 0 or exc.status >= 500 else 400, str(exc))


def _row(db: Session, video_id: int) -> AvatarVideo:
    row = db.get(AvatarVideo, video_id)
    if not row:
        raise HTTPException(404, "Avatar video not found.")
    return row


def _fields(db: Session, body: VideoBody) -> dict:
    if body.feature_id and not db.get(MarketingFeature, body.feature_id):
        raise HTTPException(404, "That feature no longer exists.")
    return body.model_dump(exclude={"render"})


def _render(db: Session, row: AvatarVideo) -> dict:
    try:
        return avatar.video_out(avatar.submit(db, row))
    except ValueError as exc:
        raise HTTPException(409 if row.status not in avatar.EDITABLE else 400, str(exc))
    except PROVIDER_ERRORS as exc:
        raise _heygen_error(exc)


@router.get("")
def workspace(db: Session = Depends(get_db)):
    avatar.refresh_active(db)
    rows = db.query(AvatarVideo).order_by(AvatarVideo.id.desc()).limit(200).all()
    features = (db.query(MarketingFeature).filter(MarketingFeature.status != "dismissed")
                .order_by(MarketingFeature.module, MarketingFeature.name).all())
    return {
        "account": avatar.account_status(), "videos": [avatar.video_out(row) for row in rows],
        "features": [{"id": f.id, "name": f.name, "module": f.module} for f in features],
        "options": avatar.option_catalog(), "script_ready": avatar.script_ready(),
        "default_voice": avatar.default_voice(),
        "narrators": {"cartesia": CartesiaClient().configured, "elevenlabs": ElevenLabsClient().configured},
    }


@router.get("/avatars")
def avatars(ownership: Literal["private", "public"] = "private", token: str = Query(default="", max_length=500)):
    try:
        return avatar.list_avatars(ownership=ownership, token=token or None)
    except HeyGenError as exc:
        raise _heygen_error(exc)


@router.post("/avatars", status_code=201)
async def create_avatar(
    name: str = Form(..., max_length=80),
    group_id: str = Form(default="", max_length=120),
    look_names: list[str] = Form(default=[]),
    photos: list[UploadFile] = File(...),
):
    if len(photos) > avatar.MAX_PHOTOS:
        raise HTTPException(400, f"Add up to {avatar.MAX_PHOTOS} photos at a time.")
    items = []
    for upload in photos:
        data = await upload.read(avatar.MAX_PHOTO_BYTES + 1)
        if len(data) > avatar.MAX_PHOTO_BYTES:
            raise HTTPException(413, "Each photo must be under 20 MB.")
        items.append((upload.filename or "photo", data))
    try:
        return await run_in_threadpool(avatar.create_photo_avatar, name, items, group_id=group_id, look_names=look_names)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except HeyGenError as exc:
        raise _heygen_error(exc)


@router.get("/avatars/looks/{look_id}")
def look(look_id: str = Path(..., pattern=r"^[A-Za-z0-9_-]{1,120}$")):
    try:
        return avatar.look_status(look_id)
    except HeyGenError as exc:
        raise HTTPException(404, str(exc)) if exc.status == 404 else _heygen_error(exc)


@router.get("/voices")
def voices(
    voice_type: Literal["private", "public"] = Query(default="public", alias="type"),
    language: str = Query(default="", max_length=60),
    gender: Literal["", "male", "female"] = "",
    token: str = Query(default="", max_length=500),
):
    try:
        return avatar.list_voices(voice_type=voice_type, language=language or None, gender=gender or None, token=token or None)
    except HeyGenError as exc:
        raise _heygen_error(exc)


@router.post("/voices/cartesia", status_code=201)
async def clone_cartesia_voice(
    name: str = Form(..., max_length=80),
    language: str = Form(default="hi", pattern=r"^[a-z]{2}$"),
    accent: str = Form(default="standard-hindi", max_length=40),
    speaks: list[str] = Form(default=["indian-english"]),
    make_default: bool = Form(default=True),
    sample: UploadFile = File(...),
    principal: Principal = Depends(current_principal),
):
    _default_guard(principal, make_default)
    data = await sample.read(avatar.MAX_SAMPLE_BYTES + 1)
    if len(data) > avatar.MAX_SAMPLE_BYTES:
        raise HTTPException(413, "The recording must be under 25 MB.")
    try:
        return await run_in_threadpool(avatar.clone_cartesia_voice, name, sample.filename or "sample.wav", data,
                                       language=language, accent=accent, speaks=tuple(speaks[:9]), make_default=make_default)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except CartesiaError as exc:
        raise _heygen_error(exc)


@router.post("/voices/elevenlabs", status_code=201)
async def clone_voice(
    name: str = Form(..., max_length=80),
    remove_background_noise: bool = Form(default=False),
    make_default: bool = Form(default=True),
    samples: list[UploadFile] = File(...),
    principal: Principal = Depends(current_principal),
):
    _default_guard(principal, make_default)
    items = []
    for upload in samples[:5]:
        data = await upload.read(avatar.MAX_SAMPLE_BYTES + 1)
        if len(data) > avatar.MAX_SAMPLE_BYTES:
            raise HTTPException(413, "Each recording must be under 25 MB.")
        items.append((upload.filename or "sample.mp3", data))
    try:
        return await run_in_threadpool(avatar.clone_elevenlabs_voice, name, items,
                                       remove_background_noise=remove_background_noise, make_default=make_default)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except ElevenLabsError as exc:
        raise _heygen_error(exc)


@router.post("/script")
def script(body: ScriptBody, db: Session = Depends(get_db)):
    try:
        return avatar.draft_script(db, feature_id=body.feature_id, brief=body.brief, seconds=body.seconds, angle=body.angle)
    except LookupError as exc:
        raise HTTPException(404, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except LLMJsonError:
        raise HTTPException(502, "The writing model did not return a script. Try again or write it by hand.")
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))


@router.post("", status_code=201)
def create(body: VideoBody, db: Session = Depends(get_db)):
    row = AvatarVideo(status="draft", options={}, result={}, assets=[])
    avatar.apply_fields(row, _fields(db, body))
    db.add(row)
    db.commit()
    db.refresh(row)
    return _render(db, row) if body.render else avatar.video_out(row)


@router.put("/{video_id}")
def update(video_id: int, body: VideoBody, db: Session = Depends(get_db)):
    row = _row(db, video_id)
    if row.status not in avatar.EDITABLE:
        raise HTTPException(409, "Only drafts and failed videos can be edited. Duplicate this one to make a new version.")
    avatar.apply_fields(row, _fields(db, body))
    row.revision = (row.revision or 1) + 1
    db.commit()
    return _render(db, row) if body.render else avatar.video_out(row)


@router.post("/{video_id}/render")
def render(video_id: int, db: Session = Depends(get_db)):
    return _render(db, _row(db, video_id))


@router.post("/{video_id}/narration")
def narration(video_id: int, db: Session = Depends(get_db)):
    row = _row(db, video_id)
    if row.status not in avatar.EDITABLE:
        raise HTTPException(409, "This video is already rendering or finished. Duplicate it to change the narration.")
    try:
        avatar.narrate(db, row)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except (CartesiaError, ElevenLabsError) as exc:
        raise _heygen_error(exc)
    return avatar.video_out(row)


@router.post("/{video_id}/refresh")
def refresh(video_id: int, db: Session = Depends(get_db)):
    return avatar.video_out(avatar.refresh(db, _row(db, video_id), force=True))


@router.post("/{video_id}/duplicate", status_code=201)
def duplicate(video_id: int, db: Session = Depends(get_db)):
    return avatar.video_out(avatar.duplicate(db, _row(db, video_id)))


@router.delete("/{video_id}")
def remove(video_id: int, db: Session = Depends(get_db)):
    try:
        avatar.delete(db, _row(db, video_id))
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    return {"ok": True}


@router.get("/{video_id}/files/{filename}")
def file(video_id: int, filename: str, db: Session = Depends(get_db)):
    row = _row(db, video_id)
    asset = next((a for a in row.assets or [] if a.get("filename") == filename), None)
    if not asset and filename == avatar.NARRATION_FILE and (row.result or {}).get("narration"):
        asset = {"mime": "audio/mpeg"}
    folder = avatar.video_folder(video_id).resolve()
    path = (folder / filename).resolve()
    if not asset or path.parent != folder or not path.is_file():
        raise HTTPException(404, "Avatar video file not found.")
    return FileResponse(path, media_type=asset["mime"], filename=filename,
                        headers={"Content-Security-Policy": "sandbox", "X-Content-Type-Options": "nosniff"})

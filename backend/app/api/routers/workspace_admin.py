"""Who am I, which workspaces can I open, and workspace administration (profile, people, members)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import context
from app.auth import Principal, auth_mode, clerk_api, current_principal, require_admin
from app.config import settings
from app.connections import store
from app.database import get_db
from app.models import AuditEvent, Membership, Person, User, Workspace
from app.storage import workspace_path
from app.workspaces import (
    PROFILE_DEFAULTS,
    ROLES,
    create_workspace,
    save_profile,
    user_workspaces,
    workspace_out,
)

router = APIRouter()

PERSON_ROLES = ("pm", "dev", "qa", "design", "notes_pm", "other")


class WorkspaceCreate(BaseModel):
    name: str
    slug: str = ""
    timezone: str = "Asia/Kolkata"


class ProfilePatch(BaseModel):
    name: str | None = None
    timezone: str | None = None
    profile: dict | None = None


class PersonBody(BaseModel):
    name: str | None = None
    short: str | None = None
    email: str | None = None
    jira_account_id: str | None = None
    cliq_user_id: str | None = None
    cliq_chat_id: str | None = None
    role: str | None = None
    team: str | None = None
    aliases: list[str] | None = None
    active: bool | None = None
    notes: str | None = None


class MemberPatch(BaseModel):
    role: str


class InviteBody(BaseModel):
    email: str
    role: str = "member"


def _workspace(db: Session) -> Workspace:
    return store.workspace_row(db)


def person_out(row: Person) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "short": row.short,
        "email": row.email,
        "jira_account_id": row.jira_account_id,
        "cliq_user_id": row.cliq_user_id,
        "cliq_chat_id": row.cliq_chat_id,
        "role": row.role,
        "team": row.team,
        "aliases": list(row.aliases or []),
        "active": bool(row.active),
        "notes": row.notes or "",
    }


def onboarding(db: Session, ws: Workspace) -> dict:
    from app.models import Connection, Repository

    profile = ws.profile or {}
    connected = {row.provider for row in db.query(Connection).all()}
    steps = [
        {"id": "profile", "label": "Describe your product", "done": bool(profile.get("product_name") and profile.get("product_description"))},
        {"id": "connections", "label": "Connect your tools", "done": bool(connected & {"jira", "llm"})},
        {"id": "repository", "label": "Add a repository", "done": bool(db.query(Repository.id).first())},
        {"id": "people", "label": "Add your team", "done": bool(db.query(Person.id).first())},
    ]
    return {"steps": steps, "complete": all(step["done"] for step in steps), "dismissed": bool(ws.onboarded_at)}


@router.get("/me")
def me(principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    with context.system():
        user = db.get(User, principal.user_id)
        workspaces = user_workspaces(db, user)
        ws = db.get(Workspace, principal.workspace_id)
    return {
        "user": {"id": user.id, "email": user.email, "name": user.name, "avatar_url": user.avatar_url},
        "workspace": workspace_out(ws, principal.role),
        "role": principal.role,
        "workspaces": workspaces,
        "auth_mode": auth_mode(),
    }


@router.post("/workspaces")
def create(body: WorkspaceCreate, principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    if auth_mode() == "clerk":
        raise HTTPException(status_code=400, detail="Create an organization from the workspace switcher; it becomes a workspace on first open.")
    if not body.name.strip():
        raise HTTPException(status_code=422, detail="Name the workspace.")
    with context.system():
        owner = db.get(User, principal.user_id)
        ws = create_workspace(db, body.name, slug=body.slug or None, owner=owner, timezone=body.timezone or "Asia/Kolkata")
    return workspace_out(ws, "owner")


@router.get("/workspace")
def get_workspace(principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    ws = _workspace(db)
    return {
        **workspace_out(ws, principal.role),
        "profile": {**PROFILE_DEFAULTS, **(ws.profile or {})},
        "onboarding": onboarding(db, ws),
    }


@router.patch("/workspace")
def patch_workspace(body: ProfilePatch, principal: Principal = Depends(require_admin), db: Session = Depends(get_db)):
    updates = dict(body.profile or {})
    if body.name is not None:
        updates["name"] = body.name
    if body.timezone is not None:
        updates["timezone"] = body.timezone
    save_profile(db, updates, actor=principal.email)
    return get_workspace(principal, db)


@router.post("/workspace/onboarding/dismiss")
def dismiss_onboarding(principal: Principal = Depends(require_admin), db: Session = Depends(get_db)):
    ws = _workspace(db)
    ws.onboarded_at = ws.onboarded_at or datetime.utcnow()
    db.add(ws)
    db.commit()
    return {"ok": True}


# Brand kit: logos used in artifacts, one-pagers and PDF headers (see services/brand.py).

BRAND_ASSETS = {
    "logo-light": (".svg", ".png", ".jpg", ".jpeg"),
    "logo-dark": (".svg", ".png", ".jpg", ".jpeg"),
    "wordmark": (".png", ".jpg", ".jpeg"),
}
BRAND_MIME = {".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
MAX_BRAND_BYTES = 2 * 1024 * 1024


def _brand_file(stem: str):
    folder = workspace_path("brand")
    for ext in BRAND_ASSETS[stem]:
        path = folder / f"{stem}{ext}"
        if path.is_file():
            return path
    return None


def _brand_stem(stem: str) -> str:
    if stem not in BRAND_ASSETS:
        raise HTTPException(status_code=404, detail="Unknown brand asset")
    return stem


@router.get("/workspace/brand")
def brand_assets(_: Principal = Depends(current_principal)):
    out = {}
    for stem in BRAND_ASSETS:
        path = _brand_file(stem)
        out[stem] = {"uploaded": bool(path), "updated_at": datetime.utcfromtimestamp(path.stat().st_mtime).isoformat() if path else None, "accepts": list(BRAND_ASSETS[stem])}
    return {"assets": out}


@router.get("/workspace/brand/{stem}")
def brand_asset(stem: str, _: Principal = Depends(current_principal)):
    path = _brand_file(_brand_stem(stem))
    if path is None:
        raise HTTPException(status_code=404, detail="Not uploaded")
    # Uploaded SVGs are served as inert images even if opened directly.
    headers = {"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'", "X-Content-Type-Options": "nosniff", "Cache-Control": "no-cache"}
    return FileResponse(path, media_type=BRAND_MIME[path.suffix.lower()], headers=headers)


@router.put("/workspace/brand/{stem}")
def upload_brand_asset(stem: str, file: UploadFile = File(...), principal: Principal = Depends(require_admin), db: Session = Depends(get_db)):
    stem = _brand_stem(stem)
    ext = ("." + (file.filename or "").rsplit(".", 1)[-1].lower()) if "." in (file.filename or "") else ""
    if ext not in BRAND_ASSETS[stem]:
        raise HTTPException(status_code=422, detail=f"Use {', '.join(e.lstrip('.').upper() for e in BRAND_ASSETS[stem])} for this asset.")
    data = file.file.read(MAX_BRAND_BYTES + 1)
    if len(data) > MAX_BRAND_BYTES:
        raise HTTPException(status_code=413, detail="Keep logos under 2 MB.")
    if not data:
        raise HTTPException(status_code=422, detail="The file is empty.")
    folder = workspace_path("brand")
    folder.mkdir(parents=True, exist_ok=True)
    for old in BRAND_ASSETS[stem]:
        (folder / f"{stem}{old}").unlink(missing_ok=True)
    (folder / f"{stem}{ext}").write_bytes(data)
    store.audit(db, "brand.uploaded", stem, {"bytes": len(data), "type": ext.lstrip(".")}, principal.email)
    db.commit()
    return brand_assets(principal)


@router.delete("/workspace/brand/{stem}")
def remove_brand_asset(stem: str, principal: Principal = Depends(require_admin), db: Session = Depends(get_db)):
    stem = _brand_stem(stem)
    folder = workspace_path("brand")
    for ext in BRAND_ASSETS[stem]:
        (folder / f"{stem}{ext}").unlink(missing_ok=True)
    store.audit(db, "brand.removed", stem, {}, principal.email)
    db.commit()
    return brand_assets(principal)


# People: the team roster that briefings, release asks and Copilot resolve names against.


@router.get("/people")
def list_people(db: Session = Depends(get_db), _: Principal = Depends(current_principal)):
    rows = db.query(Person).order_by(Person.active.desc(), Person.role, Person.name).all()
    return {"people": [person_out(row) for row in rows], "roles": list(PERSON_ROLES)}


def _apply_person(row: Person, body: PersonBody) -> None:
    data = body.model_dump(exclude_none=True)
    if "role" in data and data["role"] not in PERSON_ROLES:
        raise HTTPException(status_code=422, detail=f"Role must be one of {', '.join(PERSON_ROLES)}")
    if "aliases" in data:
        data["aliases"] = [a.strip() for a in data["aliases"] if a and a.strip()]
    for key, value in data.items():
        setattr(row, key, value.strip() if isinstance(value, str) else value)


@router.post("/people")
def add_person(body: PersonBody, principal: Principal = Depends(require_admin), db: Session = Depends(get_db)):
    if not (body.name or "").strip():
        raise HTTPException(status_code=422, detail="Name is required.")
    row = Person(name=body.name.strip())
    _apply_person(row, body)
    db.add(row)
    store.bump_version(db)
    store.audit(db, "person.added", row.name, {}, principal.email)
    db.commit()
    db.refresh(row)
    return person_out(row)


@router.patch("/people/{person_id}")
def edit_person(person_id: int, body: PersonBody, principal: Principal = Depends(require_admin), db: Session = Depends(get_db)):
    row = db.get(Person, person_id)
    if row is None or row.workspace_id != principal.workspace_id:
        raise HTTPException(status_code=404, detail="Person not found")
    _apply_person(row, body)
    db.add(row)
    store.bump_version(db)
    store.audit(db, "person.updated", row.name, {"fields": sorted(body.model_dump(exclude_none=True))}, principal.email)
    db.commit()
    return person_out(row)


@router.delete("/people/{person_id}")
def remove_person(person_id: int, principal: Principal = Depends(require_admin), db: Session = Depends(get_db)):
    row = db.get(Person, person_id)
    if row is None or row.workspace_id != principal.workspace_id:
        raise HTTPException(status_code=404, detail="Person not found")
    row.active = False
    db.add(row)
    store.bump_version(db)
    store.audit(db, "person.archived", row.name, {}, principal.email)
    db.commit()
    return {"ok": True}


# Members: who can sign in to this workspace.


def _member_rows(db: Session, workspace_id: int):
    with context.system():
        return (
            db.query(Membership, User)
            .join(User, User.id == Membership.user_id)
            .filter(Membership.workspace_id == workspace_id)
            .order_by(Membership.id)
            .all()
        )


@router.get("/members")
def list_members(principal: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    members = [
        {
            "id": m.id,
            "user_id": u.id,
            "email": u.email,
            "name": u.name,
            "avatar_url": u.avatar_url,
            "role": m.role,
            "you": u.id == principal.user_id,
            "joined_at": m.created_at.isoformat() if m.created_at else None,
            "last_seen_at": u.last_seen_at.isoformat() if u.last_seen_at else None,
        }
        for m, u in _member_rows(db, principal.workspace_id)
    ]
    invitations = []
    ws = _workspace(db)
    if auth_mode() == "clerk" and ws.clerk_org_id and principal.at_least("admin"):
        data = clerk_api(f"/organizations/{ws.clerk_org_id}/invitations?status=pending")
        for item in data.get("data") or []:
            invitations.append({"id": item.get("id"), "email": item.get("email_address"), "role": CLERK_TO_ROLE.get(item.get("role"), "member")})
    return {"members": members, "invitations": invitations, "roles": list(ROLES), "can_invite": auth_mode() == "clerk" and bool(ws.clerk_org_id)}


CLERK_TO_ROLE = {"org:admin": "admin", "org:member": "member"}
ROLE_TO_CLERK = {"owner": "org:admin", "admin": "org:admin", "member": "org:member"}


def _clerk_write(method: str, path: str, payload: dict) -> dict:
    secret = (settings.env_value("clerk_secret_key") or "").strip()
    if not secret:
        raise HTTPException(status_code=503, detail="CLERK_SECRET_KEY is not set on the server.")
    from app.clients.http import client

    with client(timeout=15) as http:
        response = http.request(method, f"https://api.clerk.com/v1{path}", json=payload, headers={"Authorization": f"Bearer {secret}"})
    if response.status_code >= 400:
        try:
            detail = (response.json().get("errors") or [{}])[0].get("long_message") or response.text
        except Exception:
            detail = response.text
        raise HTTPException(status_code=response.status_code, detail=str(detail)[:300])
    return response.json() if response.content else {}


@router.patch("/members/{member_id}")
def change_role(member_id: int, body: MemberPatch, principal: Principal = Depends(require_admin), db: Session = Depends(get_db)):
    if body.role not in ROLES:
        raise HTTPException(status_code=422, detail="Unknown role")
    with context.system():
        row = db.get(Membership, member_id)
        if row is None or row.workspace_id != principal.workspace_id:
            raise HTTPException(status_code=404, detail="Member not found")
        if (row.role == "owner" or body.role == "owner") and principal.role != "owner":
            raise HTTPException(status_code=403, detail="Only an owner can change ownership.")
        owners = db.query(Membership).filter(Membership.workspace_id == row.workspace_id, Membership.role == "owner").count()
        if row.role == "owner" and body.role != "owner" and owners <= 1:
            raise HTTPException(status_code=400, detail="A workspace needs at least one owner.")
        ws = db.get(Workspace, row.workspace_id)
        user = db.get(User, row.user_id)
        if auth_mode() == "clerk" and ws.clerk_org_id and user.clerk_user_id:
            _clerk_write("PATCH", f"/organizations/{ws.clerk_org_id}/memberships/{user.clerk_user_id}", {"role": ROLE_TO_CLERK[body.role]})
        row.role = body.role
        db.add(row)
    store.audit(db, "member.role", user.email, {"role": body.role}, principal.email)
    db.commit()
    return {"ok": True}


@router.delete("/members/{member_id}")
def remove_member(member_id: int, principal: Principal = Depends(require_admin), db: Session = Depends(get_db)):
    with context.system():
        row = db.get(Membership, member_id)
        if row is None or row.workspace_id != principal.workspace_id:
            raise HTTPException(status_code=404, detail="Member not found")
        if row.role == "owner":
            raise HTTPException(status_code=400, detail="Transfer ownership before removing an owner.")
        ws = db.get(Workspace, row.workspace_id)
        user = db.get(User, row.user_id)
        if auth_mode() == "clerk" and ws.clerk_org_id and user.clerk_user_id:
            _clerk_write("DELETE", f"/organizations/{ws.clerk_org_id}/memberships/{user.clerk_user_id}", {})
        db.delete(row)
    store.audit(db, "member.removed", user.email, {}, principal.email)
    db.commit()
    return {"ok": True}


@router.post("/members/invite")
def invite(body: InviteBody, principal: Principal = Depends(require_admin), db: Session = Depends(get_db)):
    ws = _workspace(db)
    if auth_mode() != "clerk" or not ws.clerk_org_id:
        raise HTTPException(status_code=400, detail="Invitations need Clerk sign-in and an organization workspace.")
    role = body.role if body.role in {"admin", "member"} else "member"
    payload = {
        "email_address": body.email.strip(),
        "role": ROLE_TO_CLERK[role],
        "inviter_user_id": principal.clerk_user_id or None,
        "redirect_url": (settings.env_value("public_app_url") or "").rstrip("/") + "/",
    }
    data = _clerk_write("POST", f"/organizations/{ws.clerk_org_id}/invitations", payload)
    store.audit(db, "member.invited", body.email, {"role": role}, principal.email)
    db.commit()
    return {"ok": True, "id": data.get("id")}


@router.get("/audit")
def audit_log(limit: int = 100, _: Principal = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.query(AuditEvent).order_by(AuditEvent.id.desc()).limit(max(1, min(limit, 500))).all()
    return {
        "events": [
            {"id": r.id, "actor": r.actor, "action": r.action, "target": r.target, "detail": r.detail or {}, "at": r.created_at.isoformat() if r.created_at else None}
            for r in rows
        ]
    }

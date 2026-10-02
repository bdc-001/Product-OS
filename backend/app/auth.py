"""Who is calling, in which workspace, with which role.

`AUTH_MODE=clerk` verifies the Clerk session JWT (RS256, Clerk's JWKS). The active Clerk
organization is the workspace; without one the caller works in their personal workspace,
created on first sign-in. `AUTH_MODE=local` is single-user laptop mode: one local owner.

Every authenticated request runs inside the resolved `WorkspaceContext`.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, AsyncIterator

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app import context
from app.config import settings
from app.database import SessionLocal
from app.models import Membership, User, Workspace
from app.workspaces import (
    build_context,
    create_workspace,
    ensure_local_principal,
    ensure_membership,
    ensure_user,
    membership,
    role_at_least,
)

log = logging.getLogger(__name__)

CLERK_ROLES = {"org:admin": "admin", "admin": "admin", "org:member": "member", "basic_member": "member", "member": "member"}
_JWKS: dict[str, Any] = {"client": None, "url": ""}
_JWKS_LOCK = threading.Lock()
_PROFILE_CACHE: dict[str, tuple[float, dict]] = {}


@dataclass
class Principal:
    user_id: int
    email: str
    name: str
    workspace_id: int
    workspace_slug: str
    role: str
    clerk_user_id: str = ""

    def at_least(self, role: str) -> bool:
        return role_at_least(self.role, role)


class AuthError(HTTPException):
    def __init__(self, detail: str, status_code: int = 401) -> None:
        super().__init__(status_code=status_code, detail=detail, headers={"WWW-Authenticate": "Bearer"} if status_code == 401 else None)


def auth_mode() -> str:
    return (settings.env_value("auth_mode") or "local").strip().lower()


# Clerk tokens


def _jwks_url() -> str:
    explicit = (settings.env_value("clerk_jwks_url") or "").strip()
    if explicit:
        return explicit
    issuer = (settings.env_value("clerk_issuer") or "").strip().rstrip("/")
    return f"{issuer}/.well-known/jwks.json" if issuer else ""


def _jwks_client() -> jwt.PyJWKClient:
    url = _jwks_url()
    if not url:
        raise AuthError("Sign-in is not configured on the server (CLERK_ISSUER).", 503)
    with _JWKS_LOCK:
        if _JWKS["client"] is None or _JWKS["url"] != url:
            _JWKS["client"] = jwt.PyJWKClient(url, cache_keys=True, lifespan=3600)
            _JWKS["url"] = url
        return _JWKS["client"]


def verify_clerk_token(token: str) -> dict:
    try:
        key = _jwks_client().get_signing_key_from_jwt(token)
        issuer = (settings.env_value("clerk_issuer") or "").strip().rstrip("/") or None
        claims = jwt.decode(
            token,
            key.key,
            algorithms=["RS256"],
            issuer=issuer,
            options={"require": ["exp", "sub"], "verify_aud": False},
            leeway=10,
        )
    except AuthError:
        raise
    except jwt.PyJWTError as exc:
        raise AuthError(f"Invalid session: {exc}") from exc
    parties = [item.strip() for item in (settings.env_value("clerk_authorized_parties") or "").split(",") if item.strip()]
    if parties and claims.get("azp") and claims["azp"] not in parties:
        raise AuthError("Session was issued for another site.")
    return claims


def org_claims(claims: dict) -> tuple[str, str, str]:
    """(org_id, role, slug) from a Clerk session token, v1 or v2 claim shape."""
    nested = claims.get("o") if isinstance(claims.get("o"), dict) else {}
    org_id = claims.get("org_id") or nested.get("id") or ""
    role = claims.get("org_role") or nested.get("rol") or ""
    slug = claims.get("org_slug") or nested.get("slg") or ""
    if role and not role.startswith("org:") and nested:
        role = f"org:{role}"
    return str(org_id), str(role), str(slug)


def clerk_api(path: str) -> dict:
    secret = (settings.env_value("clerk_secret_key") or "").strip()
    if not secret:
        return {}
    cached = _PROFILE_CACHE.get(path)
    if cached and time.time() - cached[0] < 600:
        return cached[1]
    from app.clients.http import get

    try:
        response = get(f"https://api.clerk.com/v1{path}", headers={"Authorization": f"Bearer {secret}"}, timeout=10)
        data = response.json() if response.status_code == 200 else {}
    except Exception:
        log.warning("Clerk API %s failed", path)
        data = {}
    _PROFILE_CACHE[path] = (time.time(), data)
    return data


def _user_details(claims: dict) -> tuple[str, str, str]:
    email = str(claims.get("email") or claims.get("primary_email") or "")
    name = str(claims.get("name") or claims.get("full_name") or "")
    avatar = str(claims.get("picture") or claims.get("image_url") or "")
    if not email:
        data = clerk_api(f"/users/{claims['sub']}")
        primary = data.get("primary_email_address_id")
        for item in data.get("email_addresses") or []:
            if item.get("id") == primary or not email:
                email = item.get("email_address") or email
        name = name or " ".join(part for part in (data.get("first_name"), data.get("last_name")) if part)
        avatar = avatar or data.get("image_url") or ""
    return email, name, avatar


def link_user(db: Session, clerk_user_id: str, email: str, name: str, avatar: str) -> User:
    """Find the Clerk user, or adopt a pre-created user with the same email (an owner migrated from a laptop install)."""
    user = db.query(User).filter(User.clerk_user_id == clerk_user_id).one_or_none()
    if user is None and email:
        user = db.query(User).filter(User.email == email, User.clerk_user_id.is_(None)).first()
        if user is not None:
            user.clerk_user_id = clerk_user_id
            db.add(user)
            db.flush()
    if user is None:
        return ensure_user(db, clerk_user_id=clerk_user_id, email=email, name=name, avatar_url=avatar)
    return ensure_user(db, clerk_user_id=clerk_user_id, email=email or user.email, name=name or user.name, avatar_url=avatar or user.avatar_url)


def org_workspace(db: Session, org_id: str, slug: str, owner: User) -> Workspace:
    ws = db.query(Workspace).filter(Workspace.clerk_org_id == org_id).one_or_none()
    if ws is not None:
        return ws
    data = clerk_api(f"/organizations/{org_id}")
    wanted_slug = data.get("slug") or slug or ""
    by_slug = db.query(Workspace).filter(Workspace.slug == wanted_slug, Workspace.clerk_org_id.is_(None)).one_or_none() if wanted_slug else None
    if by_slug is not None and membership(db, owner, by_slug) is not None:
        by_slug.clerk_org_id = org_id
        db.add(by_slug)
        db.commit()
        return by_slug
    return create_workspace(db, data.get("name") or wanted_slug or "Workspace", slug=wanted_slug or None, clerk_org_id=org_id, owner=owner)


def personal_workspace(db: Session, user: User) -> Workspace:
    ws = db.query(Workspace).filter(Workspace.personal_user_id == user.id).one_or_none()
    if ws is not None:
        return ws
    first = (user.name or user.email.split("@")[0] or "My").split(" ")[0]
    return create_workspace(db, f"{first}'s workspace", kind="personal", owner=user)


def resolve_clerk(db: Session, token: str, requested: str = "") -> Principal:
    claims = verify_clerk_token(token)
    email, name, avatar = _user_details(claims)
    user = link_user(db, str(claims["sub"]), email, name, avatar)
    org_id, org_role, org_slug = org_claims(claims)
    if org_id:
        ws = org_workspace(db, org_id, org_slug, user)
        existing = membership(db, user, ws)
        role = CLERK_ROLES.get(org_role, "member")
        if existing is not None and existing.role == "owner":
            role = "owner"
        ensure_membership(db, user, ws, role)
    elif requested:
        ws = db.query(Workspace).filter(Workspace.slug == requested).one_or_none()
        member = membership(db, user, ws) if ws else None
        if ws is None or member is None:
            raise AuthError("You are not a member of that workspace.", 403)
        role = member.role
    else:
        ws = personal_workspace(db, user)
        role = "owner"
        ensure_membership(db, user, ws, role)
    db.commit()
    member = membership(db, user, ws)
    return Principal(user.id, user.email, user.name, ws.id, ws.slug, member.role if member else role, user.clerk_user_id or "")


def resolve_local(db: Session, requested: str = "") -> Principal:
    user, ws, member = ensure_local_principal(db)
    if requested and requested != ws.slug:
        other = db.query(Workspace).filter(Workspace.slug == requested).one_or_none()
        if other is None:
            raise AuthError("Workspace not found.", 404)
        member = ensure_membership(db, user, other, "owner")
        db.commit()
        ws = other
    return Principal(user.id, user.email, user.name, ws.id, ws.slug, member.role)


def _bearer(request: Request) -> str:
    header = request.headers.get("authorization") or ""
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return request.cookies.get("__session") or ""


def authenticate(request: Request, db: Session) -> Principal:
    requested = (request.headers.get("x-workspace") or request.query_params.get("workspace") or "").strip()
    with context.system():
        if auth_mode() == "clerk":
            token = _bearer(request)
            if not token:
                raise AuthError("Sign in to continue.")
            return resolve_clerk(db, token, requested)
        return resolve_local(db, requested)


def _activate(db: Session, principal: Principal) -> context.WorkspaceContext:
    with context.system():
        ws = db.get(Workspace, principal.workspace_id)
        user = db.get(User, principal.user_id)
        db.refresh(ws)
        return build_context(db, ws, user=user, role=principal.role)


def _resolve(request: Request) -> tuple[Principal, context.WorkspaceContext]:
    db = SessionLocal()
    try:
        principal = authenticate(request, db)
        return principal, _activate(db, principal)
    finally:
        db.close()


async def current_principal(request: Request) -> AsyncIterator[Principal]:
    """FastAPI dependency: authenticate, then run the request inside the caller's workspace.

    Async on purpose: a context variable set in a sync dependency stays in its worker thread.
    """
    principal, ctx = await run_in_threadpool(_resolve, request)
    request.state.principal = principal
    token = context.activate(ctx)
    try:
        yield principal
    finally:
        try:
            context.deactivate(token)
        except ValueError:
            # The endpoint ran in another context copy (threadpool); nothing left to reset here.
            pass


def require_role(minimum: str):
    def dependency(principal: Principal = Depends(current_principal)) -> Principal:
        if not principal.at_least(minimum):
            raise HTTPException(status_code=403, detail=f"Only workspace {minimum}s can do this.")
        return principal

    return dependency


require_admin = require_role("admin")
require_member = require_role("member")


# Clerk webhooks (svix signatures)


def verify_webhook(secret: str, headers: dict, body: bytes, tolerance: int = 300) -> bool:
    msg_id = headers.get("svix-id") or ""
    stamp = headers.get("svix-timestamp") or ""
    signatures = headers.get("svix-signature") or ""
    if not (secret and msg_id and stamp and signatures):
        return False
    try:
        if abs(time.time() - int(stamp)) > tolerance:
            return False
    except ValueError:
        return False
    key = base64.b64decode(secret.split("_", 1)[1] if secret.startswith("whsec_") else secret)
    expected = base64.b64encode(hmac.new(key, f"{msg_id}.{stamp}.".encode() + body, hashlib.sha256).digest()).decode()
    for item in signatures.split():
        _, _, value = item.partition(",")
        if value and hmac.compare_digest(value, expected):
            return True
    return False


def apply_webhook(db: Session, event: dict) -> str:
    kind = str(event.get("type") or "")
    data = event.get("data") or {}
    with context.system():
        if kind in {"user.created", "user.updated"}:
            emails = data.get("email_addresses") or []
            primary = next((e.get("email_address") for e in emails if e.get("id") == data.get("primary_email_address_id")), "")
            name = " ".join(part for part in (data.get("first_name"), data.get("last_name")) if part)
            link_user(db, data["id"], primary, name, data.get("image_url") or "")
        elif kind in {"organization.created", "organization.updated"}:
            ws = db.query(Workspace).filter(Workspace.clerk_org_id == data["id"]).one_or_none()
            if ws is None:
                creator = db.query(User).filter(User.clerk_user_id == data.get("created_by")).one_or_none()
                ws = create_workspace(db, data.get("name") or "Workspace", slug=data.get("slug"), clerk_org_id=data["id"], owner=creator)
            else:
                ws.name = data.get("name") or ws.name
                db.add(ws)
        elif kind in {"organizationMembership.created", "organizationMembership.updated"}:
            org = data.get("organization") or {}
            public = data.get("public_user_data") or {}
            ws = db.query(Workspace).filter(Workspace.clerk_org_id == org.get("id")).one_or_none()
            user = db.query(User).filter(User.clerk_user_id == public.get("user_id")).one_or_none()
            if user is None and public.get("user_id"):
                user = ensure_user(db, clerk_user_id=public["user_id"], email=public.get("identifier") or "", name=" ".join(p for p in (public.get("first_name"), public.get("last_name")) if p))
            if ws is not None and user is not None:
                existing = membership(db, user, ws)
                role = CLERK_ROLES.get(str(data.get("role") or ""), "member")
                ensure_membership(db, user, ws, "owner" if existing and existing.role == "owner" else role)
        elif kind == "organizationMembership.deleted":
            org = data.get("organization") or {}
            public = data.get("public_user_data") or {}
            ws = db.query(Workspace).filter(Workspace.clerk_org_id == org.get("id")).one_or_none()
            user = db.query(User).filter(User.clerk_user_id == public.get("user_id")).one_or_none()
            if ws is not None and user is not None:
                db.query(Membership).filter(Membership.workspace_id == ws.id, Membership.user_id == user.id, Membership.role != "owner").delete()
        else:
            return "ignored"
        db.commit()
    return "applied"

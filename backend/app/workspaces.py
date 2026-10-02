"""Workspaces, users and memberships, and the per-workspace context used by requests and runs."""

from __future__ import annotations

import logging
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Iterator

from sqlalchemy.orm import Session

from app import context
from app.config import settings
from app.connections import crypto, store
from app.models import Membership, Person, Repository, User, Workspace
from app.storage import safe_slug

log = logging.getLogger(__name__)

ROLES = ("owner", "admin", "member")
ROLE_RANK = {"member": 1, "admin": 2, "owner": 3}

# Product profile keys that map directly onto `settings.<name>` inside the workspace.
PROFILE_SETTINGS = (
    "pm_display_name",
    "pm_cliq_user_id",
    "pm_cliq_mentions",
    "project_keywords",
    "product_name",
    "company_name",
    "support_email",
    "prototype_kit",
    "standup_hour",
    "standup_nudge_minute",
    "release_notes_hour",
    "jira_allowed_projects",
)
PROFILE_DEFAULTS: dict[str, Any] = {
    "product_name": "",
    "company_name": "",
    "product_description": "",
    "competitor_focus": "",
    "competitor_pack": "",
    "product_modules": "",
    "product_module_keywords": {},
    "website": "",
    "industries": "",
    "tone": "",
    "brand_rules": "",
    "pm_display_name": "",
    "pm_personas": "",
    "pm_cliq_user_id": "",
    "pm_cliq_mentions": "",
    "project_keywords": "",
    "jira_allowed_projects": "",
    "jira_scope_rules": "",
    "support_email": "",
    "newsletter_sender": "",
    "brand": {},
    "data_branch": "",
    "prototype_kit": "starter",
    "standup_hour": 9,
    "standup_nudge_minute": 55,
    "release_notes_hour": 10,
}

_CACHE: dict[int, tuple[int, context.WorkspaceContext]] = {}
_CACHE_LOCK = threading.Lock()


def role_at_least(role: str, minimum: str) -> bool:
    return ROLE_RANK.get(role or "", 0) >= ROLE_RANK.get(minimum, 99)


def unique_slug(db: Session, wanted: str) -> str:
    base = safe_slug(wanted)
    slug = base
    n = 2
    while db.query(Workspace.id).filter(Workspace.slug == slug).first():
        slug = f"{base}-{n}"
        n += 1
    return slug


def create_workspace(
    db: Session,
    name: str,
    *,
    slug: str | None = None,
    kind: str = "organization",
    clerk_org_id: str | None = None,
    owner: User | None = None,
    timezone: str = "Asia/Kolkata",
    profile: dict | None = None,
) -> Workspace:
    ws = Workspace(
        slug=unique_slug(db, slug or name),
        name=name.strip() or "Workspace",
        kind=kind,
        clerk_org_id=clerk_org_id,
        personal_user_id=owner.id if (owner and kind == "personal") else None,
        timezone=timezone,
        profile={**PROFILE_DEFAULTS, **(profile or {})},
        data_key=crypto.new_data_key(),
        config_version=1,
    )
    db.add(ws)
    db.flush()
    if owner is not None:
        ensure_membership(db, owner, ws, "owner")
    from app.pipelines.registry import seed_pipeline_configs

    with context.use(context.WorkspaceContext(id=ws.id, slug=ws.slug, name=ws.name)):
        seed_pipeline_configs(db)
    db.commit()
    db.refresh(ws)
    return ws


def ensure_user(db: Session, *, clerk_user_id: str | None, email: str = "", name: str = "", avatar_url: str = "") -> User:
    query = db.query(User)
    user = query.filter(User.clerk_user_id == clerk_user_id).one_or_none() if clerk_user_id else None
    if user is None and email and not clerk_user_id:
        user = query.filter(User.email == email, User.clerk_user_id.is_(None)).one_or_none()
    if user is None:
        user = User(clerk_user_id=clerk_user_id, email=email, name=name, avatar_url=avatar_url)
        db.add(user)
        db.flush()
    changed = False
    for attr, value in (("email", email), ("name", name), ("avatar_url", avatar_url)):
        if value and getattr(user, attr) != value:
            setattr(user, attr, value)
            changed = True
    user.last_seen_at = datetime.utcnow()
    if changed:
        db.add(user)
    return user


def ensure_membership(db: Session, user: User, workspace: Workspace, role: str = "member") -> Membership:
    row = (
        db.query(Membership)
        .filter(Membership.user_id == user.id, Membership.workspace_id == workspace.id)
        .one_or_none()
    )
    if row is None:
        row = Membership(user_id=user.id, workspace_id=workspace.id, role=role if role in ROLES else "member")
        db.add(row)
        db.flush()
    elif role in ROLES and row.role != role and role != "member":
        row.role = role
        db.add(row)
    return row


def membership(db: Session, user: User, workspace: Workspace) -> Membership | None:
    return (
        db.query(Membership)
        .filter(Membership.user_id == user.id, Membership.workspace_id == workspace.id)
        .one_or_none()
    )


def user_workspaces(db: Session, user: User) -> list[dict]:
    rows = (
        db.query(Workspace, Membership.role)
        .join(Membership, Membership.workspace_id == Workspace.id)
        .filter(Membership.user_id == user.id)
        .order_by(Workspace.kind.desc(), Workspace.name)
        .all()
    )
    return [workspace_out(ws, role) for ws, role in rows]


def workspace_out(ws: Workspace, role: str = "") -> dict:
    profile = ws.profile or {}
    return {
        "id": ws.id,
        "slug": ws.slug,
        "name": ws.name,
        "kind": ws.kind,
        "role": role,
        "timezone": ws.timezone,
        "product_name": profile.get("product_name") or "",
        "company_name": profile.get("company_name") or "",
        "clerk_org_id": ws.clerk_org_id or "",
        "onboarded": bool(ws.onboarded_at),
        "created_at": ws.created_at.isoformat() if ws.created_at else None,
    }


def local_workspace(db: Session, slug: str = "") -> Workspace | None:
    """The workspace named by `slug` or LOCAL_WORKSPACE_SLUG; with neither set, the install's first workspace."""
    wanted = (slug or settings.env_value("local_workspace_slug") or "").strip()
    query = db.query(Workspace)
    if wanted:
        return query.filter(Workspace.slug == safe_slug(wanted)).one_or_none()
    return query.order_by(Workspace.id).first()


def ensure_local_principal(db: Session) -> tuple[User, Workspace, Membership]:
    """Single-user laptop mode: one local owner in the local workspace, created on first use."""
    slug = safe_slug(settings.env_value("local_workspace_slug") or "default")
    explicit = (settings.env_value("local_user_email") or "").strip()
    ws = local_workspace(db)
    owner = None
    if ws is not None and not explicit:
        owner = (
            db.query(User)
            .join(Membership, Membership.user_id == User.id)
            .filter(Membership.workspace_id == ws.id, Membership.role == "owner")
            .order_by(Membership.id)
            .first()
        )
    user = owner or ensure_user(db, clerk_user_id=None, email=explicit or "owner@localhost", name="Local owner")
    if ws is None:
        ws = create_workspace(db, settings.env_value("local_workspace_name") or "My workspace", slug=slug, owner=user)
    member = ensure_membership(db, user, ws, "owner")
    db.commit()
    return user, ws, member


def _people(db: Session) -> list[dict]:
    rows = db.query(Person).filter(Person.active.is_(True)).order_by(Person.role, Person.name).all()
    return [
        {
            "id": row.id,
            "short": row.short or (row.name.split()[0] if row.name else ""),
            "name": row.name,
            "email": row.email,
            "account_id": row.jira_account_id,
            "cliq_user_id": row.cliq_user_id,
            "cliq_chat_id": row.cliq_chat_id,
            "role": row.role,
            "team": row.team,
            "aliases": list(row.aliases or []),
        }
        for row in rows
    ]


def _repository_values(db: Session) -> dict:
    repo = (
        db.query(Repository)
        .order_by(Repository.is_primary.desc(), Repository.id)
        .first()
    )
    if repo is None:
        return {}
    from app.services.repos import repository_values

    return repository_values(repo)


def build_context(db: Session, ws: Workspace, *, user: User | None = None, role: str = "") -> context.WorkspaceContext:
    version = int(ws.config_version or 0)
    with _CACHE_LOCK:
        cached = _CACHE.get(ws.id)
    if cached and cached[0] == version:
        base = cached[1]
    else:
        seed = context.WorkspaceContext(id=ws.id, slug=ws.slug, name=ws.name, timezone=ws.timezone or "Asia/Kolkata")
        with context.use(seed):
            values, bundle = store.settings_values(db, ws)
            people = _people(db)
            try:
                values.update(_repository_values(db))
            except Exception:
                log.exception("could not resolve repository checkout for workspace %s", ws.slug)
        profile = {**PROFILE_DEFAULTS, **(ws.profile or {})}
        for key in PROFILE_SETTINGS:
            value = profile.get(key)
            if value not in (None, ""):
                values[key] = value
        values["timezone"] = ws.timezone or "Asia/Kolkata"
        profile["people"] = people
        base = context.WorkspaceContext(
            id=ws.id,
            slug=ws.slug,
            name=ws.name,
            timezone=ws.timezone or "Asia/Kolkata",
            values=values,
            profile=profile,
            llm=bundle,
            version=version,
        )
        with _CACHE_LOCK:
            _CACHE[ws.id] = (version, base)
    return base.child(user_id=user.id if user else None, user_email=user.email if user else "", role=role)


def invalidate(workspace_id: int) -> None:
    with _CACHE_LOCK:
        _CACHE.pop(workspace_id, None)


def context_for(db: Session, workspace_id: int, *, user: User | None = None, role: str = "") -> context.WorkspaceContext:
    ws = db.get(Workspace, workspace_id)
    if ws is None:
        raise context.NoWorkspaceError(f"Workspace {workspace_id} not found")
    db.refresh(ws)
    return build_context(db, ws, user=user, role=role)


@contextmanager
def in_workspace(db: Session, workspace_id: int, **extra: Any) -> Iterator[context.WorkspaceContext]:
    ctx = context_for(db, workspace_id)
    for key, value in extra.items():
        setattr(ctx, key, value)
    with context.use(ctx):
        yield ctx


def save_profile(db: Session, updates: dict, *, actor: str = "") -> dict:
    ws = store.workspace_row(db)
    profile = {**PROFILE_DEFAULTS, **(ws.profile or {})}
    for key, value in (updates or {}).items():
        if key == "timezone":
            if value:
                ws.timezone = str(value).strip()
            continue
        if key == "name":
            if str(value or "").strip():
                ws.name = str(value).strip()
            continue
        if key not in PROFILE_DEFAULTS or value is None:
            continue
        if isinstance(PROFILE_DEFAULTS[key], int):
            try:
                value = int(value)
            except (TypeError, ValueError):
                continue
        elif isinstance(PROFILE_DEFAULTS[key], dict):
            value = value if isinstance(value, dict) else {}
        else:
            value = str(value).strip()
        profile[key] = value
    profile.pop("people", None)
    ws.profile = profile
    db.add(ws)
    store.bump_version(db, ws.id)
    store.audit(db, "profile.saved", ws.slug, {"fields": sorted(updates or {})}, actor)
    db.commit()
    ctx = context.current()
    if ctx is not None and ctx.id == ws.id:
        fresh = build_context(db, ws)
        ctx.values.update(fresh.values)
        ctx.profile.update(fresh.profile)
        ctx.timezone = fresh.timezone
    return {**profile, "timezone": ws.timezone, "name": ws.name}

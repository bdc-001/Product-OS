"""Connections hub: every provider, its masked state, and save / test / disconnect."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.routers.public import cliq_authorize_url, cliq_redirect_uri
from app.auth import Principal, current_principal, require_admin
from app.connections import store
from app.connections.registry import PROVIDERS, get_provider
from app.database import get_db
from app.pipelines.registry import CATALOG

router = APIRouter()


class ConnectionBody(BaseModel):
    values: dict = {}
    clear: list[str] = []
    name: str = "default"
    test: bool = True


def provider_out(provider) -> dict:
    used_by = [p.name for p in CATALOG if provider.id in p.requires or provider.id in p.optional]
    if provider.category == "Code":
        used_by = [p.name for p in CATALOG if "repository" in p.requires or "repository" in p.optional]
    return {
        "id": provider.id,
        "name": provider.name,
        "category": provider.category,
        "description": provider.description,
        "help_url": provider.help_url,
        "custom_ui": provider.custom_ui,
        "multiple": provider.multiple,
        "used_by": used_by,
        "fields": [
            {
                "key": f.key,
                "label": f.label,
                "kind": f.kind,
                "secret": f.secret,
                "required": f.required,
                "placeholder": f.placeholder,
                "help": f.help,
                "default": f.default,
                "options": list(f.options),
                "advanced": f.advanced,
            }
            for f in provider.fields
        ],
    }


def _provider(provider_id: str):
    try:
        return get_provider(provider_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown provider") from exc


@router.get("/connections")
def list_all(db: Session = Depends(get_db), principal: Principal = Depends(current_principal)):
    rows: dict[str, list] = {}
    for row in store.list_connections(db):
        rows.setdefault(row.provider, []).append(row)
    out = []
    for provider in PROVIDERS.values():
        mine = rows.get(provider.id) or []
        views = [store.public_view(db, row, provider) for row in mine] or [store.public_view(db, None, provider)]
        out.append({**provider_out(provider), "connections": views if principal.at_least("admin") else [_member_view(v) for v in views]})
    return {"providers": out, "can_edit": principal.at_least("admin"), "cliq_redirect_uri": cliq_redirect_uri()}


def _member_view(view: dict) -> dict:
    """Members see status, not configuration."""
    return {k: view[k] for k in ("provider", "name", "connected", "status", "last_verified_at", "last_error")}


@router.put("/connections/{provider_id}")
def save(provider_id: str, body: ConnectionBody, principal: Principal = Depends(require_admin), db: Session = Depends(get_db)):
    provider = _provider(provider_id)
    unknown = [key for key in body.values if provider.fields and not provider.field(key)]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown fields: {', '.join(unknown)}")
    row = store.save_connection(db, provider_id, body.values, name=body.name or "default", clear=body.clear, actor=principal.email)
    result = None
    if body.test and not provider.missing(store.connection_values(db, row)):
        tested = store.test_connection(db, provider_id, row.name)
        result = {"ok": tested.ok, "message": tested.message, "details": tested.details}
        row = store.get_connection(db, provider_id, row.name)
    return {"connection": store.public_view(db, row, provider), "test": result}


@router.post("/connections/{provider_id}/test")
def test(provider_id: str, name: str = "default", _: Principal = Depends(require_admin), db: Session = Depends(get_db)):
    provider = _provider(provider_id)
    result = store.test_connection(db, provider_id, name)
    return {"ok": result.ok, "message": result.message, "details": result.details, "connection": store.public_view(db, store.get_connection(db, provider_id, name), provider)}


@router.delete("/connections/{provider_id}")
def remove(provider_id: str, name: str = "default", principal: Principal = Depends(require_admin), db: Session = Depends(get_db)):
    _provider(provider_id)
    from app.models import Repository

    if get_provider(provider_id).category == "Code":
        row = store.get_connection(db, provider_id, name)
        if row is not None and db.query(Repository.id).filter(Repository.connection_id == row.id).first():
            raise HTTPException(status_code=409, detail="A repository still uses this credential. Change or remove the repository first.")
    return {"ok": store.disconnect(db, provider_id, name, actor=principal.email)}


@router.get("/connections/cliq/authorize")
def cliq_authorize(principal: Principal = Depends(require_admin), db: Session = Depends(get_db)):
    row = store.get_connection(db, "cliq")
    values = store.connection_values(db, row) if row else {}
    if not (values.get("client_id") and values.get("client_secret")):
        raise HTTPException(status_code=400, detail="Save the Zoho client ID and secret first.")
    return {"url": cliq_authorize_url(values, principal.workspace_id, principal.email), "redirect_uri": cliq_redirect_uri()}

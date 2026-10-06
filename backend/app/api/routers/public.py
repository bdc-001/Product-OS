"""Routes that run without a signed-in user: liveness, Clerk webhooks and the Zoho OAuth return."""

from __future__ import annotations

import json
import logging
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import text

from app.auth import apply_webhook, verify_webhook
from app.config import settings
from app.connections import crypto
from app.database import SessionLocal

log = logging.getLogger(__name__)
router = APIRouter()

CLIQ_SCOPES = ",".join(
    (
        "ZohoCliq.Chats.READ",
        "ZohoCliq.Messages.READ",
        "ZohoCliq.Messages.CREATE",
        "ZohoCliq.Webhooks.CREATE",
        "ZohoCliq.Users.READ",
        "ZohoCliq.Channels.READ",
    )
)


@router.get("/healthz")
def healthz():
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"database unavailable: {exc.__class__.__name__}") from exc
    finally:
        db.close()
    return {"ok": True}


@router.post("/webhooks/clerk")
async def clerk_webhook(request: Request):
    body = await request.body()
    secret = settings.env_value("clerk_webhook_secret") or ""
    if not verify_webhook(secret, {k.lower(): v for k, v in request.headers.items()}, body):
        raise HTTPException(status_code=400, detail="Invalid signature")
    event = json.loads(body or b"{}")
    db = SessionLocal()
    try:
        outcome = apply_webhook(db, event)
    finally:
        db.close()
    return {"ok": True, "outcome": outcome}


def cliq_redirect_uri() -> str:
    base = (settings.env_value("public_app_url") or "").rstrip("/")
    return f"{base}/api/connections/cliq/callback"


def cliq_authorize_url(values: dict, workspace_id: int, user_email: str) -> str:
    accounts = str(values.get("accounts_url") or "https://accounts.zoho.in").rstrip("/")
    state = crypto.sign({"ws": workspace_id, "by": user_email, "p": "cliq"})
    query = urlencode(
        {
            "scope": CLIQ_SCOPES,
            "client_id": values.get("client_id") or "",
            "response_type": "code",
            "access_type": "offline",
            "prompt": "consent",
            "redirect_uri": cliq_redirect_uri(),
            "state": state,
        }
    )
    return f"{accounts}/oauth/v2/auth?{query}"


def _back(status: str, message: str = "") -> RedirectResponse:
    base = (settings.env_value("public_app_url") or "").rstrip("/")
    query = urlencode({"provider": "cliq", "status": status, **({"message": message[:200]} if message else {})})
    return RedirectResponse(f"{base}/settings/connections?{query}", status_code=302)


@router.get("/connections/cliq/callback")
def cliq_callback(request: Request):
    params = request.query_params
    state = crypto.unsign(params.get("state") or "")
    if not state or state.get("p") != "cliq":
        return _back("error", "The sign-in link expired. Start Connect with Zoho again.")
    if params.get("error"):
        return _back("error", params.get("error") or "Zoho sign-in was cancelled.")
    code = params.get("code") or ""
    from app.clients.http import post
    from app.connections import store
    from app.workspaces import in_workspace

    db = SessionLocal()
    try:
        with in_workspace(db, int(state["ws"]), user_email=str(state.get("by") or "")):
            row = store.get_connection(db, "cliq")
            if row is None:
                return _back("error", "Save the Cliq client ID and secret first.")
            values = store.connection_values(db, row)
            accounts = (params.get("accounts-server") or values.get("accounts_url") or "https://accounts.zoho.in").rstrip("/")
            response = post(
                f"{accounts}/oauth/v2/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": values.get("client_id") or "",
                    "client_secret": values.get("client_secret") or "",
                    "redirect_uri": cliq_redirect_uri(),
                    "code": code,
                },
                timeout=20,
            )
            data = response.json() if response.content else {}
            if not data.get("access_token"):
                return _back("error", f"Zoho did not return a token: {data.get('error') or response.status_code}")
            tokens = {"access_token": data["access_token"]}
            if data.get("refresh_token"):
                tokens["refresh_token"] = data["refresh_token"]
            store.store_tokens(db, "cliq", tokens)
            if params.get("accounts-server") and params["accounts-server"].rstrip("/") != values.get("accounts_url"):
                store.save_connection(db, "cliq", {"accounts_url": params["accounts-server"]}, actor=str(state.get("by") or ""))
            store.audit(db, "connection.oauth", "cliq:default", {}, str(state.get("by") or ""))
            db.commit()
            result = store.test_connection(db, "cliq")
        return _back("connected" if result.ok else "error", "" if result.ok else result.message)
    except Exception as exc:
        log.exception("cliq oauth callback failed")
        return _back("error", str(exc))
    finally:
        db.close()

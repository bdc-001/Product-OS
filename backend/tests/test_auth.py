import base64
import hashlib
import hmac
import json
import time
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import auth, context
from app.config import settings
from app.database import SessionLocal
from app.models import Membership, User, Workspace

ISSUER = "https://clerk.test.example"
_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class _Signing:
    key = _KEY.public_key()


class _Jwks:
    def get_signing_key_from_jwt(self, token):
        return _Signing()


@pytest.fixture
def clerk(monkeypatch):
    monkeypatch.setattr(settings._base, "auth_mode", "clerk")
    monkeypatch.setattr(settings._base, "clerk_issuer", ISSUER)
    monkeypatch.setattr(settings._base, "clerk_secret_key", "")
    monkeypatch.setattr(settings._base, "clerk_authorized_parties", "https://app.test.example")
    monkeypatch.setattr(auth, "_jwks_client", lambda: _Jwks())


@pytest.fixture
def client():
    from app.main import app

    with context.system():
        yield TestClient(app)


def token(sub=None, *, key=_KEY, **claims):
    body = {"sub": sub or f"user_{uuid.uuid4().hex[:10]}", "iss": ISSUER, "exp": int(time.time()) + 300, "iat": int(time.time()),
            "azp": "https://app.test.example", "email": f"{uuid.uuid4().hex[:8]}@example.com", "name": "Test Person", **claims}
    return jwt.encode(body, key, algorithm="RS256")


def _headers(value, workspace=""):
    out = {"Authorization": f"Bearer {value}"}
    if workspace:
        out["X-Workspace"] = workspace
    return out


def test_clerk_token_must_be_signed_by_clerk(clerk):
    good = token()
    assert auth.verify_clerk_token(good)["iss"] == ISSUER
    forged = token(key=rsa.generate_private_key(public_exponent=65537, key_size=2048))
    with pytest.raises(HTTPException) as bad:
        auth.verify_clerk_token(forged)
    assert bad.value.status_code == 401
    expired = jwt.encode({"sub": "u", "iss": ISSUER, "exp": int(time.time()) - 600}, _KEY, algorithm="RS256")
    with pytest.raises(HTTPException):
        auth.verify_clerk_token(expired)
    wrong_site = token(azp="https://evil.example")
    with pytest.raises(HTTPException, match="another site"):
        auth.verify_clerk_token(wrong_site)


def test_api_requires_a_session_in_clerk_mode(clerk, client):
    assert client.get("/api/me").status_code == 401
    assert client.get("/api/connections").status_code == 401
    assert client.get("/api/healthz").status_code == 200


def test_first_sign_in_creates_a_personal_workspace(clerk, client):
    sub = f"user_{uuid.uuid4().hex[:10]}"
    first = client.get("/api/me", headers=_headers(token(sub, name="Priya Shah")))
    assert first.status_code == 200
    body = first.json()
    assert body["role"] == "owner" and body["workspace"]["name"] == "Priya's workspace"
    again = client.get("/api/me", headers=_headers(token(sub, name="Priya Shah"))).json()
    assert again["workspace"]["id"] == body["workspace"]["id"]
    with context.system():
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.clerk_user_id == sub).one()
            assert db.query(Membership).filter(Membership.user_id == user.id).count() == 1
        finally:
            db.close()


def test_org_members_cannot_manage_connections_but_admins_can(clerk, client):
    org = f"org_{uuid.uuid4().hex[:10]}"
    slug = f"acme-{uuid.uuid4().hex[:6]}"
    creator = token(org_id=org, org_role="org:admin", org_slug=slug)
    admin = token(org_id=org, org_role="org:admin", org_slug=slug)
    member = token(org_id=org, org_role="org:member", org_slug=slug)
    first = client.get("/api/me", headers=_headers(creator)).json()
    assert first["role"] == "owner" and first["workspace"]["slug"] == slug
    assert client.get("/api/me", headers=_headers(admin)).json()["role"] == "admin"
    assert client.get("/api/me", headers=_headers(member)).json()["role"] == "member"

    payload = {"values": {"base_url": "https://acme.atlassian.net", "email": "pm@acme.com", "api_token": "tok-123"}, "test": False}
    denied = client.put("/api/connections/jira", headers=_headers(member), json=payload)
    assert denied.status_code == 403
    saved = client.put("/api/connections/jira", headers=_headers(admin), json=payload)
    assert saved.status_code == 200 and "tok-123" not in saved.text
    member_view = client.get("/api/connections", headers=_headers(member)).json()
    jira = next(p for p in member_view["providers"] if p["id"] == "jira")
    assert member_view["can_edit"] is False and "config" not in jira["connections"][0]


def test_cannot_open_a_workspace_you_do_not_belong_to(clerk, client):
    with context.system():
        db = SessionLocal()
        try:
            other = Workspace(slug=f"private-{uuid.uuid4().hex[:6]}", name="Private", data_key="", profile={})
            db.add(other)
            db.commit()
            slug = other.slug
        finally:
            db.close()
    response = client.get("/api/me", headers=_headers(token(), workspace=slug))
    assert response.status_code == 403


def test_role_ladder():
    member = auth.Principal(1, "m@x", "M", 1, "ws", "member")
    with pytest.raises(HTTPException) as denied:
        auth.require_role("admin")(member)
    assert denied.value.status_code == 403
    assert auth.require_role("member")(member) is member
    owner = auth.Principal(1, "o@x", "O", 1, "ws", "owner")
    assert auth.require_role("admin")(owner) is owner


def _svix(secret: str, body: bytes, stamp: int | None = None):
    stamp = stamp or int(time.time())
    key = base64.b64decode(secret.split("_", 1)[1])
    sig = base64.b64encode(hmac.new(key, f"msg_1.{stamp}.".encode() + body, hashlib.sha256).digest()).decode()
    return {"svix-id": "msg_1", "svix-timestamp": str(stamp), "svix-signature": f"v1,{sig}"}


def test_clerk_webhook_signature():
    secret = "whsec_" + base64.b64encode(b"0123456789abcdef0123456789abcdef").decode()
    body = json.dumps({"type": "user.created"}).encode()
    assert auth.verify_webhook(secret, _svix(secret, body), body)
    assert not auth.verify_webhook(secret, _svix(secret, body), body + b" ")
    assert not auth.verify_webhook(secret, _svix(secret, body, stamp=int(time.time()) - 3600), body)
    assert not auth.verify_webhook("", _svix(secret, body), body)

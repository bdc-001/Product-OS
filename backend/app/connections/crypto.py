"""Envelope encryption for workspace secrets.

The master key (`APP_ENCRYPTION_KEY`, one or more comma-separated Fernet keys, newest first) lives
only in the environment. Each workspace has its own data key, stored encrypted by the master key on
the `workspaces` row. Connection secrets are encrypted with the workspace data key.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import time
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.config import data_root, settings

log = logging.getLogger(__name__)


class EncryptionKeyMissing(RuntimeError):
    pass


def _local_key() -> bytes:
    """Development-only fallback so a laptop install works without APP_ENCRYPTION_KEY."""
    path = data_root() / ".platform.key"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.is_file():
        path.write_bytes(Fernet.generate_key())
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    return path.read_bytes().strip()


@lru_cache(maxsize=4)
def _master_for(raw: str) -> MultiFernet:
    keys = [item.strip() for item in raw.split(",") if item.strip()]
    if not keys:
        if settings.is_production:
            raise EncryptionKeyMissing("APP_ENCRYPTION_KEY is required in production.")
        keys = [_local_key().decode("utf-8")]
    return MultiFernet([Fernet(key.encode("utf-8")) for key in keys])


def master() -> MultiFernet:
    return _master_for(settings.env_value("app_encryption_key") or "")


def new_data_key() -> str:
    return master().encrypt(Fernet.generate_key()).decode("utf-8")


def _data_fernet(wrapped_key: str) -> Fernet:
    return Fernet(master().decrypt(wrapped_key.encode("utf-8")))


def encrypt_json(wrapped_key: str, payload: dict) -> str:
    if not payload:
        return ""
    return _data_fernet(wrapped_key).encrypt(json.dumps(payload, default=str).encode("utf-8")).decode("utf-8")


def decrypt_json(wrapped_key: str, token: str) -> dict:
    if not token:
        return {}
    try:
        raw = _data_fernet(wrapped_key).decrypt(token.encode("utf-8"))
    except InvalidToken:
        log.error("connection secrets could not be decrypted; check APP_ENCRYPTION_KEY")
        return {}
    data = json.loads(raw.decode("utf-8"))
    return data if isinstance(data, dict) else {}


def rotate_data_key(wrapped_key: str) -> str:
    """Re-wrap a data key under the newest master key (after adding a key to APP_ENCRYPTION_KEY)."""
    return master().rotate(wrapped_key.encode("utf-8")).decode("utf-8")


def _signing_key() -> bytes:
    raw = (settings.env_value("app_encryption_key") or "").split(",")[0].strip()
    material = raw.encode("utf-8") if raw else _local_key()
    return hashlib.sha256(b"product-os-signing:" + material).digest()


def sign(payload: dict, ttl_seconds: int = 900) -> str:
    """Short-lived signed token (OAuth `state`). Not encrypted: never put secrets in it."""
    body = base64.urlsafe_b64encode(json.dumps({**payload, "exp": int(time.time()) + ttl_seconds}).encode()).decode().rstrip("=")
    mac = base64.urlsafe_b64encode(hmac.new(_signing_key(), body.encode(), hashlib.sha256).digest()).decode().rstrip("=")
    return f"{body}.{mac}"


def unsign(token: str) -> dict | None:
    body, _, mac = (token or "").partition(".")
    if not body or not mac:
        return None
    expected = base64.urlsafe_b64encode(hmac.new(_signing_key(), body.encode(), hashlib.sha256).digest()).decode().rstrip("=")
    if not hmac.compare_digest(mac, expected):
        return None
    try:
        data = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except ValueError:
        return None
    if not isinstance(data, dict) or int(data.get("exp") or 0) < time.time():
        return None
    return data

from __future__ import annotations

import json
import re
import ssl
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from app.clients.http import get, post
from app.config import ENV_FILE, ROOT, settings
import os

# Plaintext OAuth cache on disk. Files are chmod 600. Rotate by deleting this file
# and replacing CLIQ_REFRESH_TOKEN in .env, then restart so Cliq re-auths.
TOKEN_PATH = ROOT / "data" / "cliq_token.json"


def _load_cached_tokens() -> dict:
    if not TOKEN_PATH.is_file():
        return {}
    try:
        os.chmod(TOKEN_PATH, 0o600)
    except OSError:
        pass
    try:
        data = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _write_env_value(key: str, value: str) -> None:
    if not value or not ENV_FILE.is_file():
        return
    text = ENV_FILE.read_text(encoding="utf-8")
    line = f"{key}={value}"
    if re.search(rf"^{re.escape(key)}=.*$", text, re.M):
        text = re.sub(rf"^{re.escape(key)}=.*$", line, text, count=1, flags=re.M)
    else:
        text = text.rstrip() + f"\n{line}\n"
    ENV_FILE.write_text(text, encoding="utf-8")
    attr = key.lower()
    if hasattr(settings, attr):
        setattr(settings, attr, value)


def _save_cached_tokens(access: str, refresh: str) -> None:
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(
        json.dumps({"access_token": access, "refresh_token": refresh}),
        encoding="utf-8",
    )
    try:
        os.chmod(TOKEN_PATH, 0o600)
    except OSError:
        pass
    setattr(settings, "cliq_access_token", access)
    if refresh:
        setattr(settings, "cliq_refresh_token", refresh)
    try:
        from app.services.workspace import store_cliq_tokens

        store_cliq_tokens(access, refresh)
    except Exception:
        _write_env_value("CLIQ_ACCESS_TOKEN", access)
        if refresh:
            _write_env_value("CLIQ_REFRESH_TOKEN", refresh)


def _parse_ts(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        ms = int(value)
        if ms > 10_000_000_000:
            ms = ms / 1000
        return datetime.fromtimestamp(ms, tz=timezone.utc).replace(tzinfo=None)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None
    return None


def _message_text(raw: dict) -> str:
    for key in ("text", "content", "message", "plain_text"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    content = raw.get("content")
    if isinstance(content, dict):
        return (content.get("text") or content.get("message") or "").strip()
    return ""


SCOPE_HINT = (
    "Cliq can read chats but cannot send DMs with the current login. "
    "In the Zoho API console add scope ZohoCliq.Webhooks.CREATE, generate a new refresh token, "
    "and replace CLIQ_REFRESH_TOKEN."
)


def _cliq_api_error(response) -> Exception:
    code = ""
    message = ""
    try:
        body = response.json() if response.content else {}
        if isinstance(body, dict):
            code = str(body.get("code") or "")
            message = str(body.get("message") or "")
    except Exception:
        pass
    if code == "oauthtoken_scope_invalid" or "required scope" in message.lower():
        return RuntimeError(SCOPE_HINT)
    if message:
        return RuntimeError(f"Cliq {response.status_code}: {message}")
    return RuntimeError(f"Cliq {response.status_code}")


class CliqClient:
    def __init__(self) -> None:
        cached = _load_cached_tokens()
        self.api = settings.cliq_api_domain.rstrip("/")
        self.accounts = settings.cliq_accounts_url.rstrip("/")
        self.access_token = cached.get("access_token") or settings.cliq_access_token
        self.refresh_token = cached.get("refresh_token") or settings.cliq_refresh_token

    @property
    def configured(self) -> bool:
        return bool(self.access_token or (settings.cliq_client_id and self.refresh_token))

    def _headers(self) -> dict[str, str]:
        token = self.ensure_access_token()
        return {
            "Authorization": f"Zoho-oauthtoken {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def ensure_access_token(self) -> str:
        if self.access_token:
            return self.access_token
        if not self.refresh_token:
            raise RuntimeError("Cliq is not configured: missing access or refresh token")
        return self.refresh_access_token()

    def refresh_access_token(self) -> str:
        if not (settings.cliq_client_id and settings.cliq_client_secret and self.refresh_token):
            raise RuntimeError("Cliq refresh requires client id, secret, and refresh token")
        response = self._call(
            post,
            f"{self.accounts}/oauth/v2/token",
            data={
                "grant_type": "refresh_token",
                "client_id": settings.cliq_client_id,
                "client_secret": settings.cliq_client_secret,
                "refresh_token": self.refresh_token,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        token = data.get("access_token")
        if not token:
            raise RuntimeError("Cliq token refresh failed")
        if data.get("refresh_token"):
            self.refresh_token = data["refresh_token"]
        self.access_token = token
        _save_cached_tokens(self.access_token, self.refresh_token)
        return token

    def exchange_code(self, code: str, redirect_uri: str) -> dict:
        response = post(
            f"{self.accounts}/oauth/v2/token",
            data={
                "grant_type": "authorization_code",
                "client_id": settings.cliq_client_id,
                "client_secret": settings.cliq_client_secret,
                "redirect_uri": redirect_uri,
                "code": code,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("access_token"):
            self.access_token = data["access_token"]
        if data.get("refresh_token"):
            self.refresh_token = data["refresh_token"]
        if self.access_token:
            _save_cached_tokens(self.access_token, self.refresh_token)
        return data

    @staticmethod
    def _transient(exc: Exception) -> bool:
        if isinstance(exc, (ssl.SSLError, httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError, httpx.TimeoutException)):
            return True
        text = str(exc)
        return "UNEXPECTED_EOF" in text or "EOF occurred in violation of protocol" in text

    def _call(self, method, url: str, **kwargs):
        last: Exception | None = None
        headers = dict(kwargs.pop("headers", None) or {})
        headers.setdefault("Connection", "close")
        for attempt in range(3):
            try:
                response = method(url, headers=headers, **kwargs)
                return response
            except Exception as exc:
                last = exc
                if not self._transient(exc) or attempt == 2:
                    raise
                time.sleep(0.6 * (attempt + 1))
        raise last or RuntimeError("Cliq request failed")

    def _get(self, path: str, params: dict | None = None) -> Any:
        url = f"{self.api}{path}"
        response = self._call(get, url, headers=self._headers(), params=params, timeout=45)
        if response.status_code == 401 and self.refresh_token:
            body = {}
            try:
                body = response.json() if response.content else {}
            except Exception:
                body = {}
            if str((body or {}).get("code") or "") != "oauthtoken_scope_invalid":
                self.access_token = ""
                self.refresh_access_token()
                response = self._call(get, url, headers=self._headers(), params=params, timeout=45)
        if not response.is_success:
            raise _cliq_api_error(response)
        if not response.content:
            return {}
        return response.json()

    def _post(self, path: str, json: dict) -> Any:
        url = f"{self.api}{path}"
        response = self._call(post, url, headers=self._headers(), json=json, timeout=45)
        if response.status_code == 401 and self.refresh_token:
            body = {}
            try:
                body = response.json() if response.content else {}
            except Exception:
                body = {}
            if str((body or {}).get("code") or "") != "oauthtoken_scope_invalid":
                self.access_token = ""
                self.refresh_access_token()
                response = self._call(post, url, headers=self._headers(), json=json, timeout=45)
        if not response.is_success:
            raise _cliq_api_error(response)
        if not response.content:
            return {}
        return response.json()

    def list_chats(self, modified_after_ms: int | None = None, limit: int = 100) -> list[dict]:
        params: dict[str, Any] = {"limit": limit}
        if modified_after_ms:
            params["modified_after"] = str(modified_after_ms)
        data = self._get("/api/v2/chats", params=params)
        if isinstance(data, list):
            return data
        return data.get("chats") or data.get("data") or data.get("list") or []

    def list_channels(self, limit: int = 100) -> list[dict]:
        try:
            data = self._get("/api/v2/channels", params={"limit": limit})
        except Exception:
            return []
        if isinstance(data, list):
            return data
        return data.get("channels") or data.get("data") or []

    def get_messages(self, chat_id: str, fromtime_ms: int, totime_ms: int, limit: int = 100) -> list[dict]:
        data = self._get(
            f"/api/v2/chats/{chat_id}/messages",
            params={"fromtime": fromtime_ms, "totime": totime_ms, "limit": limit},
        )
        if isinstance(data, list):
            return data
        return data.get("messages") or data.get("data") or data.get("list") or []

    def send_message(self, chat_id: str, text: str) -> dict:
        return self._post(f"/api/v2/chats/{chat_id}/message", {"text": text})

    def send_to_email(self, email: str, text: str) -> dict:
        from urllib.parse import quote

        ident = quote((email or "").strip(), safe="@.")
        if not ident:
            raise RuntimeError("Cliq DM needs an email address.")
        return self._post(f"/api/v2/buddies/{ident}/message", {"text": text})

    def send_dm(self, text: str, *, chat_id: str = "", email: str = "") -> dict:
        last: Exception | None = None
        if chat_id:
            try:
                return self.send_message(chat_id, text)
            except Exception as exc:
                last = exc
                if str(exc) == SCOPE_HINT:
                    raise
        if email:
            try:
                return self.send_to_email(email, text)
            except Exception as exc:
                last = exc
                if str(exc) == SCOPE_HINT:
                    raise
        raise last or RuntimeError("Cliq DM needs a chat or email.")

    def normalize_chat(self, raw: dict) -> dict:
        chat_id = str(raw.get("chat_id") or raw.get("id") or raw.get("chid") or "")
        name = (
            raw.get("name")
            or raw.get("title")
            or raw.get("display_name")
            or ((raw.get("user") or {}).get("name"))
            or chat_id
        )
        return {
            "chat_id": chat_id,
            "name": name,
            "chat_type": raw.get("type") or raw.get("chat_type") or "",
            "last_modified": _parse_ts(raw.get("last_modified_time") or raw.get("modified_time") or raw.get("lmtime")),
            "raw": raw,
        }

    def normalize_message(self, chat: dict, raw: dict) -> dict:
        sender = raw.get("sender") or raw.get("user") or {}
        if isinstance(sender, str):
            sender_name, sender_id = sender, ""
        else:
            sender_name = sender.get("name") or sender.get("display_name") or ""
            sender_id = str(sender.get("id") or sender.get("zuid") or "")
        return {
            "chat_id": chat["chat_id"],
            "chat_name": chat["name"],
            "message_id": str(raw.get("id") or raw.get("message_id") or ""),
            "thread_id": str(raw.get("thread_id") or raw.get("thread") or ""),
            "sender": sender_name,
            "sender_id": sender_id,
            "message": _message_text(raw),
            "timestamp": _parse_ts(raw.get("time") or raw.get("timestamp") or raw.get("sent_time")),
        }

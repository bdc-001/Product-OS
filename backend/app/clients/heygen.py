"""HeyGen v3 API: account, photo avatars, avatar looks, voices, avatar video creation and status.

v1/v2 endpoints retire on 2026-11-01, so only v3 paths are used here.
"""
from __future__ import annotations

import time
from pathlib import Path

import httpx

from app.clients.http import client as http_client
from app.config import settings

BASE_URL = "https://api.heygen.com"
RETRY_STATUSES = {429, 500, 502, 503, 504}


class HeyGenError(RuntimeError):
    def __init__(self, message: str, status: int = 0, code: str = ""):
        super().__init__(message)
        self.status = status
        self.code = code


def _error_message(response: httpx.Response) -> tuple[str, str]:
    try:
        body = response.json()
    except ValueError:
        body = {}
    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, dict):
        return str(error.get("message") or "")[:300], str(error.get("code") or "")
    if isinstance(error, str):
        return error[:300], ""
    return "", ""


class HeyGenClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self.api_key = (settings.heygen_api_key if api_key is None else api_key or "").strip()
        self.base_url = (base_url or settings.heygen_base_url or BASE_URL).rstrip("/")

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _request(self, method: str, path: str, *, params: dict | None = None, json: dict | None = None,
                 files: dict | None = None, headers: dict | None = None, timeout: float = 45, attempts: int = 3) -> dict:
        if not self.configured:
            raise HeyGenError("HeyGen is not connected. Add the API key in Connections.", 401, "not_configured")
        merged = {"x-api-key": self.api_key, "accept": "application/json", **(headers or {})}
        query = {k: v for k, v in (params or {}).items() if v not in (None, "")}
        last: HeyGenError | None = None
        for attempt in range(attempts):
            try:
                with http_client(timeout=timeout) as session:
                    response = session.request(method, self.base_url + path, params=query, json=json, files=files, headers=merged)
            except httpx.HTTPError:
                last = HeyGenError("HeyGen could not be reached. Check the network and retry.", 0, "network")
                time.sleep(1.5 * (attempt + 1))
                continue
            if response.status_code in RETRY_STATUSES and attempt < attempts - 1:
                try:
                    wait = float(response.headers.get("Retry-After") or 0)
                except ValueError:
                    wait = 0
                time.sleep(min(max(wait, 1.5 * (attempt + 1)), 10))
                continue
            if response.status_code >= 400:
                message, code = _error_message(response)
                if response.status_code == 401:
                    message = "HeyGen rejected the API key. Replace it in Connections."
                raise HeyGenError(message or f"HeyGen returned HTTP {response.status_code}.", response.status_code, code)
            try:
                body = response.json()
            except ValueError as exc:
                raise HeyGenError("HeyGen returned an unreadable response.", response.status_code, "bad_response") from exc
            return body if isinstance(body, dict) else {}
        raise last or HeyGenError("HeyGen did not respond.", 0, "network")

    def me(self) -> dict:
        return self._request("GET", "/v3/users/me", attempts=1, timeout=8).get("data") or {}

    def looks(self, *, ownership: str | None = None, avatar_type: str | None = None, group_id: str | None = None,
              limit: int = 50, token: str | None = None) -> dict:
        return self._request("GET", "/v3/avatars/looks", params={
            "ownership": ownership, "avatar_type": avatar_type, "group_id": group_id,
            "limit": max(1, min(int(limit), 50)), "token": token,
        })

    def look(self, look_id: str) -> dict:
        return self._request("GET", f"/v3/avatars/looks/{look_id}", attempts=2, timeout=20).get("data") or {}

    def delete_look(self, look_id: str) -> None:
        self._request("DELETE", f"/v3/avatars/looks/{look_id}", attempts=1, timeout=20)

    def upload_asset(self, filename: str, content: bytes, mime: str, *, idempotency_key: str) -> dict:
        data = self._request("POST", "/v3/assets", files={"file": (filename, content, mime)},
                             headers={"Idempotency-Key": idempotency_key}, timeout=120).get("data") or {}
        if not data.get("asset_id"):
            raise HeyGenError("HeyGen accepted the upload but returned no asset id.", 0, "bad_response")
        return data

    def create_photo_avatar(self, name: str, asset_id: str, *, group_id: str | None = None, idempotency_key: str) -> dict:
        """Without group_id HeyGen creates a new character named `name`; with it, the photo becomes another look."""
        body: dict = {"type": "photo", "name": name, "file": {"type": "asset_id", "asset_id": asset_id}}
        if group_id:
            body["avatar_group_id"] = group_id
        # Single attempt: HeyGen can create (and bill) the look even when the response fails, and a retry
        # with the same Idempotency-Key has been observed to create a duplicate instead of replaying.
        data = self._request("POST", "/v3/avatars", json=body, headers={"Idempotency-Key": idempotency_key},
                             timeout=90, attempts=1).get("data") or {}
        if not (data.get("avatar_item") or {}).get("id"):
            raise HeyGenError("HeyGen accepted the photo but returned no avatar look.", 0, "bad_response")
        return data

    def voices(self, *, voice_type: str = "public", language: str | None = None, gender: str | None = None,
               engine: str | None = None, limit: int = 100, token: str | None = None) -> dict:
        return self._request("GET", "/v3/voices", params={
            "type": voice_type, "language": language, "gender": gender, "engine": engine,
            "limit": max(1, min(int(limit), 100)), "token": token,
        })

    def create_video(self, body: dict, *, idempotency_key: str) -> dict:
        # The idempotency key makes the built-in retries safe: HeyGen replays the first response.
        data = self._request("POST", "/v3/videos", json=body, headers={"Idempotency-Key": idempotency_key}, timeout=60).get("data") or {}
        if not data.get("video_id"):
            raise HeyGenError("HeyGen accepted the request but returned no video id.", 0, "bad_response")
        return data

    def video(self, video_id: str, *, attempts: int = 3, timeout: float = 30) -> dict:
        return self._request("GET", f"/v3/videos/{video_id}", attempts=attempts, timeout=timeout).get("data") or {}

    def download(self, url: str, target: Path, *, timeout: float = 300) -> int:
        """Stream a presigned HeyGen file URL. The API key is never sent to file hosts."""
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(target.name + ".part")
        size = 0
        try:
            with http_client(timeout=timeout, follow_redirects=True) as session, session.stream("GET", url) as response:
                if response.status_code >= 400:
                    raise HeyGenError(f"HeyGen file download failed with HTTP {response.status_code}.", response.status_code, "download")
                with partial.open("wb") as handle:
                    for chunk in response.iter_bytes(1 << 16):
                        handle.write(chunk)
                        size += len(chunk)
        except httpx.HTTPError as exc:
            partial.unlink(missing_ok=True)
            raise HeyGenError("HeyGen file download was interrupted. It will retry.", 0, "download") from exc
        except HeyGenError:
            partial.unlink(missing_ok=True)
            raise
        partial.replace(target)
        return size

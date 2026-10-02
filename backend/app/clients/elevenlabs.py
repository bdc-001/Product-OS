"""ElevenLabs: instant voice clones and text-to-speech for avatar video narration."""
from __future__ import annotations

import json
import time

import httpx

from app.clients.http import client as http_client
from app.config import settings

BASE_URL = "https://api.elevenlabs.io"
RETRY_STATUSES = {429, 500, 502, 503, 504}


class ElevenLabsError(RuntimeError):
    def __init__(self, message: str, status: int = 0, code: str = ""):
        super().__init__(message)
        self.status = status
        self.code = code


def _error_message(response: httpx.Response) -> tuple[str, str]:
    try:
        body = response.json()
    except ValueError:
        return "", ""
    detail = body.get("detail") if isinstance(body, dict) else None
    if isinstance(detail, dict):
        return str(detail.get("message") or "")[:300], str(detail.get("status") or detail.get("code") or "")
    if isinstance(detail, list):
        return "; ".join(str(item.get("msg") or "") for item in detail if isinstance(item, dict))[:300], "invalid_request"
    if isinstance(detail, str):
        return detail[:300], ""
    return "", ""


class ElevenLabsClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self.api_key = (settings.elevenlabs_api_key if api_key is None else api_key or "").strip()
        self.base_url = (base_url or BASE_URL).rstrip("/")

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _send(self, method: str, path: str, *, params: dict | None = None, json_body: dict | None = None,
              data: dict | None = None, files: list | None = None, accept: str = "application/json",
              timeout: float = 60, attempts: int = 3) -> httpx.Response:
        if not self.configured:
            raise ElevenLabsError("ElevenLabs is not connected. Add the API key in Connections.", 401, "not_configured")
        headers = {"xi-api-key": self.api_key, "accept": accept}
        last: ElevenLabsError | None = None
        for attempt in range(attempts):
            try:
                with http_client(timeout=timeout) as session:
                    response = session.request(method, self.base_url + path, params=params, json=json_body, data=data,
                                               files=files, headers=headers)
            except httpx.HTTPError:
                last = ElevenLabsError("ElevenLabs could not be reached. Check the network and retry.", 0, "network")
                time.sleep(1.5 * (attempt + 1))
                continue
            if response.status_code in RETRY_STATUSES and attempt < attempts - 1:
                time.sleep(1.5 * (attempt + 1))
                continue
            if response.status_code >= 400:
                message, code = _error_message(response)
                if response.status_code == 401 and code != "quota_exceeded":
                    message = message or "ElevenLabs rejected the API key. Replace it in Connections."
                raise ElevenLabsError(message or f"ElevenLabs returned HTTP {response.status_code}.", response.status_code, code)
            return response
        raise last or ElevenLabsError("ElevenLabs did not respond.", 0, "network")

    def _json(self, response: httpx.Response) -> dict:
        try:
            body = response.json()
        except ValueError as exc:
            raise ElevenLabsError("ElevenLabs returned an unreadable response.", response.status_code, "bad_response") from exc
        return body if isinstance(body, dict) else {}

    def subscription(self) -> dict:
        return self._json(self._send("GET", "/v1/user/subscription", timeout=10, attempts=1))

    def voice(self, voice_id: str) -> dict:
        return self._json(self._send("GET", f"/v1/voices/{voice_id}", timeout=20, attempts=2))

    def clone_voice(self, name: str, samples: list[tuple[str, bytes, str]], *, remove_background_noise: bool = False,
                    description: str = "", labels: dict | None = None) -> dict:
        form = {"name": name, "remove_background_noise": "true" if remove_background_noise else "false"}
        if description:
            form["description"] = description
        if labels:
            form["labels"] = json.dumps(labels)
        # Single attempt: a retry after a lost response would create a second voice in the account.
        body = self._json(self._send("POST", "/v1/voices/add", data=form, timeout=180, attempts=1,
                                     files=[("files", (filename, content, mime)) for filename, content, mime in samples]))
        if not body.get("voice_id"):
            raise ElevenLabsError("ElevenLabs accepted the recording but returned no voice id.", 0, "bad_response")
        return body

    def speech(self, voice_id: str, text: str, *, model_id: str, voice_settings: dict,
               output_format: str = "mp3_44100_128") -> bytes:
        response = self._send("POST", f"/v1/text-to-speech/{voice_id}", params={"output_format": output_format},
                              json_body={"text": text, "model_id": model_id, "voice_settings": voice_settings},
                              accept="audio/mpeg", timeout=180, attempts=2)
        if len(response.content) < 1024:
            raise ElevenLabsError("ElevenLabs returned an empty narration file.", response.status_code, "bad_response")
        return response.content

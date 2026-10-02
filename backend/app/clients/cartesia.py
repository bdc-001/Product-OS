"""Cartesia: instant voice clones, voice accents and Sonic text-to-speech for avatar video narration."""
from __future__ import annotations

import time

import httpx

from app.clients.http import client as http_client

BASE_URL = "https://api.cartesia.ai"
API_VERSION = "2026-08-14"
RETRY_STATUSES = {429, 500, 502, 503, 504}


class CartesiaError(RuntimeError):
    def __init__(self, message: str, status: int = 0, code: str = ""):
        super().__init__(message)
        self.status = status
        self.code = code


def _error_message(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        return ""
    if not isinstance(body, dict):
        return ""
    for key in ("message", "error", "detail", "title"):
        value = body.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:300]
        if isinstance(value, dict) and isinstance(value.get("message"), str):
            return value["message"].strip()[:300]
    return ""


def default_key() -> str:
    # Same key the launch-film narration uses: workspace settings first, then the Sense_Communication env files.
    from app.services.marketing_video import voice_settings

    return (voice_settings().cartesia_api_key or "").strip()


class CartesiaClient:
    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self.api_key = (default_key() if api_key is None else api_key or "").strip()
        self.base_url = (base_url or BASE_URL).rstrip("/")

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _send(self, method: str, path: str, *, json_body: dict | None = None, data: dict | None = None,
              files: dict | None = None, accept: str = "application/json", timeout: float = 60,
              attempts: int = 3) -> httpx.Response:
        if not self.configured:
            raise CartesiaError("Cartesia is not connected. Add the API key in Connections.", 401, "not_configured")
        headers = {"Authorization": f"Bearer {self.api_key}", "Cartesia-Version": API_VERSION, "accept": accept}
        last: CartesiaError | None = None
        for attempt in range(attempts):
            try:
                with http_client(timeout=timeout) as session:
                    response = session.request(method, self.base_url + path, json=json_body, data=data, files=files,
                                               headers=headers)
            except httpx.HTTPError:
                last = CartesiaError("Cartesia could not be reached. Check the network and retry.", 0, "network")
                time.sleep(1.5 * (attempt + 1))
                continue
            if response.status_code in RETRY_STATUSES and attempt < attempts - 1:
                time.sleep(1.5 * (attempt + 1))
                continue
            if response.status_code >= 400:
                message = _error_message(response)
                if response.status_code == 401:
                    message = "Cartesia rejected the API key. Replace it in Connections."
                raise CartesiaError(message or f"Cartesia returned HTTP {response.status_code}.", response.status_code)
            return response
        raise last or CartesiaError("Cartesia did not respond.", 0, "network")

    def _json(self, response: httpx.Response) -> dict:
        try:
            body = response.json()
        except ValueError as exc:
            raise CartesiaError("Cartesia returned an unreadable response.", response.status_code, "bad_response") from exc
        return body if isinstance(body, dict) else {}

    def voice(self, voice_id: str) -> dict:
        return self._json(self._send("GET", f"/voices/{voice_id}", timeout=20))

    def clone_voice(self, name: str, clip: tuple[str, bytes, str], *, language: str, accent: str = "",
                    description: str = "") -> dict:
        form = {"name": name, "language": language, "access": "private"}
        if accent:
            form["accent"] = accent
        if description:
            form["description"] = description
        # Single attempt: a retry after a lost response would leave a second clone in the account.
        body = self._json(self._send("POST", "/voices/clone", data=form, files={"clip": clip}, timeout=180, attempts=1))
        if not body.get("id"):
            raise CartesiaError("Cartesia accepted the recording but returned no voice id.", 0, "bad_response")
        return body

    def add_accents(self, voice_id: str, accents: list[str]) -> dict:
        return self._json(self._send("PATCH", f"/voices/{voice_id}/accents", json_body={"accents": accents}, timeout=60))

    def speech(self, voice_id: str, transcript: str, *, model_id: str, locale: str, accent: str = "", speed: float = 1.0,
               pronunciation_dict_id: str = "") -> bytes:
        body: dict = {
            "model_id": model_id, "transcript": transcript, "voice": voice_id, "locale": locale,
            "output_format": {"container": "mp3", "sample_rate": 44100, "bit_rate": 128000},
            "generation_config": {"speed": speed},
        }
        if accent:
            body["accent"] = accent
        if pronunciation_dict_id:
            body["pronunciation_dict_id"] = pronunciation_dict_id
        response = self._send("POST", "/tts/bytes", json_body=body, accept="audio/mpeg", timeout=180, attempts=2)
        if len(response.content) < 1024:
            raise CartesiaError("Cartesia returned an empty narration file.", response.status_code, "bad_response")
        return response.content

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.clients.http import post
from app.config import settings
from app.database import SessionLocal
from app.models import LlmUsage
from app.services.prompts import parse_json_object, prompt_preamble, temperature_for
from app.services.time_window import now_local


SYSTEM_PROMPT = prompt_preamble()
DOCS_SURFACES = {
    "comms_doc",
    "release_notes",
    "newsletter",
    "artifact",
    "artifact_content",
    "artifact_brief",
    "artifact_polish",
}
HTML_SURFACES = {"artifact_brief", "artifact_polish"}
LUNA_SURFACES = {"copilot"}
log = logging.getLogger(__name__)


class LLMJsonError(RuntimeError):
    """Final failure from chat_json after retries. Callers fall back to heuristics."""


def _is_gpt5(model: str) -> bool:
    return (model or "").lower().startswith("gpt-5")


def _is_claude(model: str) -> bool:
    return "claude" in (model or "").lower()


def _record_usage(surface: str, model: str, usage: dict | None) -> None:
    if not usage:
        return
    prompt = int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0)
    completion = int(usage.get("completion_tokens") or usage.get("output_tokens") or 0)
    total = int(usage.get("total_tokens") or (prompt + completion))
    db = SessionLocal()
    try:
        db.add(
            LlmUsage(
                surface=(surface or "unknown")[:64],
                model=(model or "")[:128],
                prompt_tokens=prompt,
                completion_tokens=completion,
                total_tokens=total,
                created_at=now_local().replace(tzinfo=None),
            )
        )
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _claude_text(payload: dict) -> str:
    bits = []
    for item in payload.get("content") or []:
        if isinstance(item, dict) and item.get("type") == "text":
            bits.append(str(item.get("text") or ""))
    return "\n".join(bits).strip()


def _thinking_tokens(usage: dict | None) -> int:
    if not isinstance(usage, dict):
        return 0
    details = usage.get("output_tokens_details") if isinstance(usage.get("output_tokens_details"), dict) else {}
    return int(details.get("thinking_tokens") or 0)


def _html_from_model_text(raw: str) -> str:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:html|json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text).strip()
    lower = text.lower()
    start = lower.find("<!doctype")
    if start < 0:
        start = lower.find("<html")
    if start < 0:
        return ""
    html = text[start:]
    end = html.lower().rfind("</html>")
    if end >= 0:
        html = html[: end + len("</html>")]
    return html.strip()


def _anthropic_system(system: str, surface: str) -> str:
    text = (system or "").rstrip()
    if surface in HTML_SURFACES:
        return text
    return text + "\n\nRespond with a single JSON object only. No markdown."


class LLMClient:
    def __init__(self, model: str | None = None, surface: str = "unknown") -> None:
        from app.services.workspace import resolve_llm

        resolved = resolve_llm(surface, model)
        self.model = (resolved.get("model") or settings.llm_model or "").strip() or settings.llm_model
        self.api_key = (resolved.get("api_key") or "").strip()
        self.base_url = (resolved.get("base_url") or "").rstrip("/")
        self.protocol = (resolved.get("protocol") or "openai").strip() or "openai"
        if not self.api_key or not self.base_url:
            docs_model = (settings.llm_docs_model or "").strip()
            if _is_claude(self.model) or (docs_model and self.model == docs_model):
                self.api_key = self.api_key or (settings.llm_docs_api_key or settings.llm_api_key or "").strip()
                self.base_url = self.base_url or (settings.llm_docs_base_url or settings.llm_base_url or "").rstrip("/")
                self.protocol = "anthropic" if _is_claude(self.model) else self.protocol
            else:
                self.api_key = self.api_key or (settings.llm_api_key or "").strip()
                self.base_url = self.base_url or (settings.llm_base_url or "").rstrip("/")
                self.protocol = self.protocol or "openai"

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def complete_json(
        self,
        user_payload: dict[str, Any] | str | None = None,
        system_prompt: str | None = None,
        max_chars: int = 24000,
        images: list[dict] | None = None,
        timeout: int = 90,
        reasoning_effort: str | None = None,
        surface: str = "unknown",
        temperature: float | None = None,
        user_text: str | None = None,
    ) -> dict:
        if not self.configured:
            raise RuntimeError("LLM is not configured")
        chunks = []
        if user_text:
            chunks.append(str(user_text).strip())
        if isinstance(user_payload, str) and user_payload.strip():
            chunks.append(user_payload.strip())
        elif isinstance(user_payload, dict) and user_payload:
            chunks.append(json.dumps(user_payload, default=str))
        text = "\n\n".join(chunks)[:max_chars] or "{}"
        system = system_prompt or SYSTEM_PROMPT
        if self.protocol == "anthropic":
            return self._complete_anthropic(
                text,
                system,
                surface=surface,
                temperature=temperature,
                timeout=timeout,
                reasoning_effort=reasoning_effort,
                images=images,
            )
        return self._complete_openai(
            text,
            system,
            images=images,
            timeout=timeout,
            reasoning_effort=reasoning_effort,
            surface=surface,
            temperature=temperature,
        )

    def _complete_openai(
        self,
        text: str,
        system: str,
        *,
        images: list[dict] | None,
        timeout: int,
        reasoning_effort: str | None,
        surface: str,
        temperature: float | None,
    ) -> dict:
        user_content: Any = text
        vision = [item for item in (images or []) if isinstance(item, dict) and item.get("url")]
        if vision:
            user_content = [{"type": "text", "text": text}]
            for item in vision[:4]:
                user_content.append({"type": "image_url", "image_url": {"url": item["url"]}})
            timeout = max(timeout, 120)
        body: dict[str, Any] = {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
        }
        if _is_gpt5(self.model):
            body["reasoning_effort"] = reasoning_effort or "low"
        else:
            body["temperature"] = temperature if temperature is not None else temperature_for(surface)
        response = post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        _record_usage(surface, self.model, payload.get("usage") if isinstance(payload, dict) else None)
        content = payload["choices"][0]["message"]["content"]
        parsed = parse_json_object(content)
        if not parsed:
            raise RuntimeError("LLM returned JSON that could not be parsed object-wise.")
        return parsed

    def _complete_anthropic(
        self,
        text: str,
        system: str,
        *,
        surface: str,
        temperature: float | None,
        timeout: int,
        reasoning_effort: str | None = None,
        images: list[dict] | None = None,
    ) -> dict:
        _ = temperature
        effort = (reasoning_effort or "").strip().lower()
        if effort not in {"low", "medium", "high", "xhigh", "max"}:
            effort = "high" if (surface or "") in DOCS_SURFACES else "low"
        # Anthropic requires max_tokens. HTML documents need the Foundry output
        # ceiling even at medium effort — 8192 truncates a two-page brief.
        max_tokens = 128_000 if effort in {"high", "xhigh", "max"} or surface in HTML_SURFACES else 8192
        user_content: Any = _anthropic_user_content(text, images)
        body: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens,
            "output_config": {"effort": effort},
            "system": _anthropic_system(system, surface),
            "messages": [{"role": "user", "content": user_content}],
        }
        headers = {
            "x-api-key": self.api_key,
            "api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/anthropic/v1/messages"
        wait = max(timeout, 300 if effort in {"xhigh", "max"} else 180 if effort == "high" or surface in HTML_SURFACES else 120)
        response = post(url, headers=headers, json=body, timeout=wait)
        if response.status_code >= 400:
            log.error("anthropic %s surface=%s body=%s", response.status_code, surface, (response.text or "")[:1500])
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            payload = {}
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        _record_usage(surface, str(payload.get("model") or self.model), usage)
        raw = _claude_text(payload)
        if surface not in HTML_SURFACES and raw and not raw.lstrip().startswith("{"):
            raw = "{" + raw
        think = _thinking_tokens(usage)
        log.info(
            "anthropic surface=%s requested=%s returned=%s stop=%s effort=%s in=%s out=%s think=%s chars=%s",
            surface,
            self.model,
            payload.get("model") or self.model,
            payload.get("stop_reason"),
            effort,
            usage.get("input_tokens"),
            usage.get("output_tokens"),
            think,
            len(raw),
        )
        if think:
            log.warning("anthropic thinking_tokens=%s may have squeezed JSON for surface=%s", think, surface)
        if surface in HTML_SURFACES:
            log.info(
                "%s output_tokens=%s max_tokens=%s stop=%s chars=%s",
                surface,
                usage.get("output_tokens"),
                max_tokens,
                payload.get("stop_reason"),
                len(raw),
            )
        if payload.get("stop_reason") == "max_tokens":
            log.error(
                "anthropic truncated surface=%s out=%s max_tokens=%s",
                surface,
                usage.get("output_tokens"),
                max_tokens,
            )
        parsed = parse_json_object(raw)
        html = _html_from_model_text(raw) if surface in HTML_SURFACES else ""
        if html:
            return {"html": html}
        if parsed:
            return parsed
        log.error("anthropic JSON parse failed surface=%s stop=%s raw=%s", surface, payload.get("stop_reason"), raw[:4000])
        raise RuntimeError("LLM returned JSON that could not be parsed object-wise.")


def model_for(surface: str) -> str:
    from app.services.workspace import resolve_llm

    chosen = (resolve_llm(surface).get("model") or "").strip()
    if chosen:
        return chosen
    if (surface or "").startswith("marketing_"):
        return settings.marketing_model
    docs_model = (settings.llm_docs_model or "").strip()
    strong = (settings.llm_copilot_model or "").strip()
    name = surface or ""
    if name in LUNA_SURFACES and strong:
        return strong
    if name in DOCS_SURFACES and docs_model:
        return docs_model
    if name in {"comms_doc"} and strong:
        return strong
    return (settings.llm_model or "").strip()


def _anthropic_user_content(text: str, images: list[dict] | None) -> Any:
    blocks = []
    for item in (images or [])[:8]:
        if not isinstance(item, dict):
            continue
        data = str(item.get("data") or "").strip()
        media = str(item.get("media_type") or "image/png").strip() or "image/png"
        if not data:
            continue
        blocks.append({"type": "image", "source": {"type": "base64", "media_type": media, "data": data}})
    if not blocks:
        return text
    blocks.append({"type": "text", "text": text})
    return blocks


def chat_json(
    surface: str,
    system: str,
    payload: dict,
    temperature: float | None = None,
    max_retries: int = 1,
    max_chars: int = 16000,
    timeout: int = 90,
    reasoning_effort: str | None = None,
    images: list[dict] | None = None,
) -> dict:
    """JSON Chat Completions with per-surface logging. Raises LLMJsonError on final failure."""
    client = LLMClient(model=model_for(surface), surface=surface)
    last: Exception | None = None
    attempts = max(0, max_retries) + 1
    for _ in range(attempts):
        try:
            parsed = client.complete_json(
                payload,
                system_prompt=system,
                max_chars=max_chars,
                timeout=timeout,
                surface=surface,
                temperature=temperature,
                reasoning_effort=reasoning_effort,
                images=images,
            )
            if parsed:
                return parsed
            last = RuntimeError("LLM returned empty JSON object")
        except Exception as exc:
            last = exc
    raise LLMJsonError(str(last) if last else "LLM JSON call failed") from last

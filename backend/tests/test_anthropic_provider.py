import pytest

from app.clients import llm


@pytest.mark.parametrize("base,url,native", [
    ("https://api.anthropic.com", "https://api.anthropic.com/v1/messages", True),
    ("https://api.anthropic.com/v1", "https://api.anthropic.com/v1/messages", True),
    ("https://api.anthropic.com/v1/messages", "https://api.anthropic.com/v1/messages", True),
    ("https://example.services.ai.azure.com", "https://example.services.ai.azure.com/anthropic/v1/messages", False),
    ("https://example.services.ai.azure.com/anthropic/v1", "https://example.services.ai.azure.com/anthropic/v1/messages", False),
])
@pytest.mark.parametrize("effort", ["low", "medium", "high", "xhigh", "max"])
def test_messages_endpoint_preserves_origin_effort_and_parses_fenced_json(monkeypatch, base, url, native, effort):
    monkeypatch.setattr("app.services.workspace.resolve_llm", lambda *a: {
        "model": "claude-opus-5-5", "api_key": "test-only-secret", "base_url": base, "protocol": "anthropic"})
    monkeypatch.setattr(llm, "_record_usage", lambda *a: None)
    sent = {}

    class Response:
        status_code = 200
        text = ""

        def raise_for_status(self):
            pass

        def json(self):
            return {"content": [{"type": "thinking", "thinking": "Do not parse this block."},
                                {"type": "text", "text": '```json\n{"ok": true}\n```'}]}

    def post(destination, **kwargs):
        sent.update(url=destination, **kwargs)
        return Response()

    monkeypatch.setattr(llm, "post", post)
    assert llm.LLMClient(surface="marketing_writer").complete_json(
        {}, system_prompt="Return JSON", surface="marketing_writer", reasoning_effort=effort) == {"ok": True}
    assert sent["url"] == url
    assert sent["headers"]["x-api-key"] == "test-only-secret"
    assert ("api-key" not in sent["headers"]) is native
    assert sent["json"]["output_config"] == {"effort": effort}
    assert "temperature" not in sent["json"] and "thinking" not in sent["json"]
    assert sent["json"]["messages"][-1]["role"] == "user"

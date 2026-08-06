import json
import urllib.error

import pytest

from tarcsmem.adapters import (
    DeepSeekClient,
    ExtractiveDemoClient,
    OllamaClient,
    llm_from_environment,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_deepseek_client_uses_official_chat_api_without_leaking_key(monkeypatch):
    captured = {}
    api_key = "unit-" + "test-key"

    def fake_urlopen(request, timeout, context):
        captured["url"] = request.full_url
        captured["authorization"] = request.get_header("Authorization")
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        captured["verify_mode"] = context.verify_mode
        return FakeResponse(
            {
                "model": "deepseek-v4-flash",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "可信回答 [SOURCE: POLICY#1]"},
                    }
                ],
                "usage": {
                    "prompt_tokens": 20,
                    "completion_tokens": 8,
                    "total_tokens": 28,
                    "prompt_cache_hit_tokens": 10,
                    "completion_tokens_details": {"reasoning_tokens": 0},
                },
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client = DeepSeekClient(api_key, max_retries=0)
    result = client.chat_with_metrics([{"role": "user", "content": "测试"}])

    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["authorization"] == f"Bearer {api_key}"
    assert captured["payload"]["model"] == "deepseek-v4-flash"
    assert captured["payload"]["thinking"] == {"type": "disabled"}
    assert captured["verify_mode"] != 0
    assert "api_key" not in captured["payload"]
    assert result["content"].startswith("可信回答")
    assert result["provider"] == "deepseek"
    assert result["total_tokens"] == 28
    assert api_key not in str(result)


def test_deepseek_auth_error_does_not_include_key(monkeypatch):
    api_key = "private-" + "unit-test"

    def unauthorized(_request, timeout, context):
        raise urllib.error.HTTPError(
            "https://api.deepseek.com/chat/completions", 401, "Unauthorized", {}, None
        )

    monkeypatch.setattr("urllib.request.urlopen", unauthorized)
    client = DeepSeekClient(api_key, max_retries=0)
    with pytest.raises(RuntimeError, match="authentication failed") as error:
        client.chat([{"role": "user", "content": "测试"}])
    assert api_key not in str(error.value)


def test_llm_factory_switches_between_ollama_and_deepseek(monkeypatch):
    monkeypatch.setenv("TARCSMEM_LLM_PROVIDER", "ollama")
    assert isinstance(llm_from_environment(), OllamaClient)

    monkeypatch.setenv("TARCSMEM_LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "factory-unit-test")
    monkeypatch.setenv("TARCSMEM_DEEPSEEK_MODEL", "deepseek-v4-pro")
    client = llm_from_environment()
    assert isinstance(client, DeepSeekClient)
    assert client.model == "deepseek-v4-pro"


def test_zero_config_factory_uses_extractive_demo(monkeypatch):
    monkeypatch.delenv("TARCSMEM_LLM_PROVIDER", raising=False)
    assert isinstance(llm_from_environment(), ExtractiveDemoClient)


def test_extractive_demo_renders_only_governed_source_blocks():
    client = ExtractiveDemoClient()
    result = client.chat_with_metrics(
        [
            {
                "role": "system",
                "content": (
                    "Governed evidence:\n"
                    "[SOURCE: POLICY#1]\n"
                    "[VALID_FROM: 2026-01-01]\n"
                    "[VALID_TO: open-ended]\n"
                    "[AUTHORITY: 1.00]\n"
                    "折扣上限为5%。"
                ),
            },
            {"role": "user", "content": "折扣上限？"},
        ]
    )
    assert "折扣上限为5%" in result["content"]
    assert "[SOURCE: POLICY#1]" in result["content"]
    assert result["provider"] == "extractive-demo"


def test_llm_factory_requires_deepseek_key(monkeypatch):
    monkeypatch.setenv("TARCSMEM_LLM_PROVIDER", "deepseek")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
        llm_from_environment()


def test_deepseek_rejects_insecure_or_obsolete_configuration():
    with pytest.raises(ValueError, match="HTTPS"):
        DeepSeekClient("unit-test", base_url="http://api.deepseek.com")
    with pytest.raises(ValueError, match="deepseek-v4"):
        DeepSeekClient("unit-test", model="deepseek-chat")

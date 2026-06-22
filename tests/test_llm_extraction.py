from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mindvault_mcp.config import load_config
from mindvault_mcp.services.llm_extraction import LLMExtractionService


class FakeResponse:
    def __init__(self, payload: dict[str, Any] | str):
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    def read(self) -> bytes:
        if isinstance(self.payload, str):
            return self.payload.encode("utf-8")
        return json.dumps(self.payload).encode("utf-8")


def test_llm_disabled_returns_none() -> None:
    config = load_config(Path("missing-test-config.yaml"))
    service = LLMExtractionService(config)
    result = service.extract_via_llm("Some text")
    assert result is None


def test_llm_enabled_calls_chat_completions(monkeypatch) -> None:
    config = load_config(Path("missing-test-config.yaml"))
    config.extraction.llm_enabled = True
    config.extraction.llm_model = "test-model"
    config.extraction.llm_base_url = "https://llm.example/v1/"
    config.extraction.llm_timeout_seconds = 3.5
    calls: list[tuple[object, float | None]] = []

    def fake_urlopen(request: object, timeout: float | None = None) -> FakeResponse:
        calls.append((request, timeout))
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "title": "LLM title",
                                    "problem": "problem",
                                    "context": "context",
                                    "insight": "insight",
                                    "solution": "solution",
                                    "tags": ["llm"],
                                    "domain": "testing",
                                    "confidence": 0.8,
                                }
                            )
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    service = LLMExtractionService(config)
    result = service.extract_via_llm("Raw memory text", api_key="test-key")

    assert result == {
        "title": "LLM title",
        "problem": "problem",
        "context": "context",
        "insight": "insight",
        "solution": "solution",
        "tags": ["llm"],
        "domain": "testing",
        "confidence": 0.8,
    }
    assert len(calls) == 1
    request, timeout = calls[0]
    assert timeout == 3.5
    assert request.full_url == "https://llm.example/v1/chat/completions"
    assert request.get_method() == "POST"
    assert request.headers["Authorization"] == "Bearer test-key"
    assert request.headers["Content-type"] == "application/json"
    body = json.loads(request.data.decode("utf-8"))
    assert body["model"] == "test-model"
    assert body["temperature"] == 0
    assert "messages" in body
    assert body["messages"][0]["role"] == "system"
    assert body["messages"][1]["role"] == "user"
    assert "Raw memory text" in body["messages"][1]["content"]


def test_llm_enabled_without_api_key_returns_none(monkeypatch) -> None:
    config = load_config(Path("missing-test-config.yaml"))
    config.extraction.llm_enabled = True
    called = False

    def fake_urlopen(request: object, timeout: float | None = None) -> FakeResponse:
        nonlocal called
        called = True
        return FakeResponse({})

    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    service = LLMExtractionService(config)
    result = service.extract_via_llm("Raw memory text")

    assert result is None
    assert called is False


def test_llm_parse_failures_return_none(monkeypatch) -> None:
    config = load_config(Path("missing-test-config.yaml"))
    config.extraction.llm_enabled = True
    payloads: list[dict[str, Any] | str] = [
        "not json",
        {"choices": []},
        {"choices": [{"message": {}}]},
        {"choices": [{"message": {"content": "not json"}}]},
    ]

    def fake_urlopen(request: object, timeout: float | None = None) -> FakeResponse:
        return FakeResponse(payloads.pop(0))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    service = LLMExtractionService(config)

    for _ in range(4):
        assert service.extract_via_llm("Raw memory text", api_key="test-key") is None

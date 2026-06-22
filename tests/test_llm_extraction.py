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
    monkeypatch.setenv("LLM_API_KEY", "test-key")

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
    monkeypatch.setenv("LLM_API_KEY", "test-key")

    service = LLMExtractionService(config)

    for _ in range(4):
        assert service.extract_via_llm("Raw memory text", api_key="test-key") is None


def _service() -> LLMExtractionService:
    config = load_config(Path("missing-test-config.yaml"))
    return LLMExtractionService(config)


def test_normalize_tags_not_list_becomes_empty() -> None:
    result = _service()._normalize_result({"title": "t", "tags": "a,b,c"})
    assert result is not None
    assert result["tags"] == []


def test_normalize_tags_filters_non_strings() -> None:
    result = _service()._normalize_result({"title": "t", "tags": ["a", 1, "b", None]})
    assert result is not None
    assert result["tags"] == ["a", "b"]


def test_normalize_missing_confidence_defaults_half() -> None:
    result = _service()._normalize_result({"title": "t"})
    assert result is not None
    assert result["confidence"] == 0.5


def test_normalize_confidence_clamped_low() -> None:
    result = _service()._normalize_result({"title": "t", "confidence": -2})
    assert result is not None
    assert result["confidence"] == 0.0


def test_normalize_confidence_clamped_high() -> None:
    result = _service()._normalize_result({"title": "t", "confidence": 5})
    assert result is not None
    assert result["confidence"] == 1.0


def test_normalize_invalid_confidence_defaults_half() -> None:
    result = _service()._normalize_result({"title": "t", "confidence": "high"})
    assert result is not None
    assert result["confidence"] == 0.5


def test_normalize_long_title_truncated() -> None:
    long_title = "x" * 200
    result = _service()._normalize_result({"title": long_title})
    assert result is not None
    assert len(result["title"]) <= 80


def test_normalize_empty_title_generated_from_context() -> None:
    result = _service()._normalize_result(
        {"title": "", "context": "A useful context sentence about caching."}
    )
    assert result is not None
    assert result["title"]
    assert len(result["title"]) <= 80


def test_normalize_default_domain_general() -> None:
    result = _service()._normalize_result({"title": "t"})
    assert result is not None
    assert result["domain"] == "general"


def test_normalize_non_dict_returns_none() -> None:
    assert _service()._normalize_result(["not", "a", "dict"]) is None
    assert _service()._normalize_result("string") is None
    assert _service()._normalize_result(None) is None


def test_llm_extractor_on_success_builds_card(monkeypatch) -> None:
    from mindvault_mcp.services.extraction import LLMExtractor
    from mindvault_mcp.schemas import IngestMetadata

    config = load_config(Path("missing-test-config.yaml"))
    config.extraction.llm_enabled = True

    def fake_urlopen(request: object, timeout: float | None = None) -> FakeResponse:
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "title": "LLM-extracted title",
                                    "problem": "LLM problem",
                                    "context": "LLM context",
                                    "insight": "LLM insight",
                                    "solution": "LLM solution",
                                    "tags": ["llm", "test"],
                                    "domain": "testing",
                                    "confidence": 0.88,
                                }
                            )
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setenv("LLM_API_KEY", "test-key")

    extractor = LLMExtractor(config)
    card = extractor.extract("Raw input text", IngestMetadata(), "test-agent")

    assert card.title == "LLM-extracted title"
    assert card.problem == "LLM problem"
    assert card.context == "LLM context"
    assert card.insight == "LLM insight"
    assert card.solution == "LLM solution"
    assert card.tags == ["llm", "test"]
    assert card.domain == "testing"
    assert card.confidence == 0.88
    assert card.source_agent == "test-agent"


def test_llm_extractor_metadata_overrides_llm(monkeypatch) -> None:
    from mindvault_mcp.services.extraction import LLMExtractor
    from mindvault_mcp.schemas import IngestMetadata

    config = load_config(Path("missing-test-config.yaml"))
    config.extraction.llm_enabled = True

    def fake_urlopen(request: object, timeout: float | None = None) -> FakeResponse:
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "title": "LLM title",
                                    "problem": "LLM problem",
                                    "context": "LLM context",
                                    "insight": "LLM insight",
                                    "solution": "LLM solution",
                                    "tags": ["llm"],
                                    "domain": "general",
                                    "confidence": 0.5,
                                }
                            )
                        }
                    }
                ]
            }
        )

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setenv("LLM_API_KEY", "test-key")

    extractor = LLMExtractor(config)
    metadata = IngestMetadata(
        tags=["override"],
        domain="specific",
        confidence=0.95,
        source_agent="override-agent",
    )
    card = extractor.extract("Raw input text", metadata, "fallback-agent")

    assert card.tags == ["override"]
    assert card.domain == "specific"
    assert card.confidence == 0.95
    assert card.source_agent == "override-agent"


def test_llm_extractor_fallback_on_llm_failure(monkeypatch) -> None:
    from mindvault_mcp.services.extraction import LLMExtractor
    from mindvault_mcp.schemas import IngestMetadata

    config = load_config(Path("missing-test-config.yaml"))
    config.extraction.llm_enabled = True

    def fake_urlopen(request: object, timeout: float | None = None) -> FakeResponse:
        raise Exception("Network error")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    monkeypatch.setenv("LLM_API_KEY", "test-key")

    extractor = LLMExtractor(config)
    card = extractor.extract(
        "Problem: fallback issue\nContext: LLM unavailable\nInsight: rule-based should catch",
        IngestMetadata(),
        "test-agent",
    )

    assert card.problem.startswith("fallback issue")
    assert "rule-based" in card.insight.lower() or "unavailable" in card.context.lower()

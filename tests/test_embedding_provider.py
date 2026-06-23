from __future__ import annotations

import json
import urllib.error

import pytest

from embedding_provider import APIProvider, LocalProvider, NoneProvider, create_provider


def test_none_provider_returns_empty_vectors() -> None:
    provider = create_provider("none")

    assert isinstance(provider, NoneProvider)
    assert provider.embed_text("private local text") == []
    assert provider.embed_batch(["one", "two"]) == [[], []]


def test_local_provider_real(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeModel:
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name

        def encode(self, texts: list[str]) -> list[list[float]]:
            return [[0.25] * 384 for _ in texts]

    monkeypatch.setattr("embedding_provider.SentenceTransformer", FakeModel)

    provider = create_provider("local")

    assert isinstance(provider, LocalProvider)
    assert provider.model_name == "sentence-transformers/all-MiniLM-L6-v2"
    assert provider.embed_text("local-only text") == [0.25] * 384
    assert provider.embed_batch(["one", "two"]) == [[0.25] * 384, [0.25] * 384]


def test_api_provider_without_config_stays_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)

    def fail_urlopen(request, timeout=None):  # pragma: no cover - must not run
        raise AssertionError("api provider must not call the network without config")

    monkeypatch.setattr("urllib.request.urlopen", fail_urlopen)

    provider = create_provider("api")

    assert isinstance(provider, APIProvider)
    assert provider.embed_text("api-backed text") == []
    assert provider.embed_batch(["one", "two"]) == [[], []]


def test_create_provider_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="Unknown provider type"):
        create_provider("unknown")


class _FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None


def _api_provider(base_url: str = "https://example.com/v1") -> APIProvider:
    return APIProvider(
        api_key="secret-token",
        base_url=base_url,
        model="text-embedding-test",
        timeout_seconds=7.5,
    )


def test_api_provider_real(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["authorization"] = request.headers.get("Authorization")
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse(json.dumps({"data": [{"embedding": [0.1, 0.2, 0.3]}]}).encode("utf-8"))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    provider = _api_provider("https://example.com/v1")
    vector = provider.embed_text("real semantic text")

    assert vector == [0.1, 0.2, 0.3]
    assert captured["url"] == "https://example.com/v1/embeddings"
    assert captured["timeout"] == 7.5
    assert captured["authorization"] == "Bearer secret-token"
    assert captured["body"]["model"] == "text-embedding-test"
    assert captured["body"]["input"] == "real semantic text"
    assert captured["body"]["encoding_format"] == "float"


def test_api_provider_does_not_duplicate_embeddings_suffix(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        return _FakeResponse(json.dumps({"data": [{"embedding": [1.0]}]}).encode("utf-8"))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    provider = _api_provider("https://example.com/v1/embeddings")
    provider.embed_text("text")

    assert captured["url"] == "https://example.com/v1/embeddings"


def test_api_provider_returns_empty_when_config_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_urlopen(request, timeout=None):  # pragma: no cover - must not run
        raise AssertionError("urlopen must not be called without full config")

    monkeypatch.setattr("urllib.request.urlopen", fail_urlopen)

    assert APIProvider(api_key="", base_url="https://example.com/v1", model="m").embed_text("t") == []
    assert APIProvider(api_key="k", base_url="", model="m").embed_text("t") == []
    assert APIProvider(api_key="k", base_url="https://example.com/v1", model="").embed_text("t") == []


def test_api_provider_returns_empty_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request, timeout=None):
        raise urllib.error.HTTPError(request.full_url, 500, "boom", hdrs=None, fp=None)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    assert _api_provider().embed_text("text") == []


def test_api_provider_returns_empty_on_url_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request, timeout=None):
        raise urllib.error.URLError("no network")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    assert _api_provider().embed_text("text") == []


def test_api_provider_returns_empty_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request, timeout=None):
        raise TimeoutError("slow")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    assert _api_provider().embed_text("text") == []


def test_api_provider_returns_empty_on_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request, timeout=None):
        return _FakeResponse(b"not json")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    assert _api_provider().embed_text("text") == []


def test_api_provider_returns_empty_on_unexpected_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request, timeout=None):
        return _FakeResponse(json.dumps({"data": []}).encode("utf-8"))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    assert _api_provider().embed_text("text") == []


def test_api_provider_reads_key_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout=None):
        captured["authorization"] = request.headers.get("Authorization")
        return _FakeResponse(json.dumps({"data": [{"embedding": [0.5]}]}).encode("utf-8"))

    monkeypatch.setenv("EMBEDDING_API_KEY", "env-secret")
    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    provider = APIProvider(base_url="https://example.com/v1", model="m")
    vector = provider.embed_text("text")

    assert vector == [0.5]
    assert captured["authorization"] == "Bearer env-secret"


def test_api_provider_sends_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    """APIProvider should include User-Agent in request headers."""
    import io
    import json
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout=None):
        captured["headers"] = dict(request.headers)
        response_data = json.dumps({
            "data": [{"embedding": [0.1, 0.2, 0.3]}]
        }).encode("utf-8")
        return io.BytesIO(response_data)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    from embedding_provider import APIProvider

    provider = APIProvider(api_key="test", base_url="https://test.com", model="test")
    provider.embed_text("hello")

    ua = captured["headers"].get("User-agent") or captured["headers"].get("User-Agent")
    assert ua == "mindvault-mcp"


def test_api_provider_single_text_sends_string_input(monkeypatch: pytest.MonkeyPatch) -> None:
    """APIProvider should send input as a string (not array) for single-text requests."""
    import io
    import json
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout=None):
        captured["request_data"] = request.data
        response_data = json.dumps({
            "data": [{"embedding": [0.1, 0.2]}]
        }).encode("utf-8")
        return io.BytesIO(response_data)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    from embedding_provider import APIProvider

    provider = APIProvider(api_key="test", base_url="https://test.com", model="test")
    provider.embed_text("single text")

    payload = json.loads(captured["request_data"])
    assert isinstance(payload["input"], str)
    assert payload["input"] == "single text"


def test_api_provider_batch_sends_array_input(monkeypatch: pytest.MonkeyPatch) -> None:
    """APIProvider should send input as an array for multi-text batch requests."""
    import io
    import json
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout=None):
        captured["request_data"] = request.data
        response_data = json.dumps({
            "data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}]
        }).encode("utf-8")
        return io.BytesIO(response_data)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    from embedding_provider import APIProvider

    provider = APIProvider(api_key="test", base_url="https://test.com", model="test")
    provider.embed_batch(["text one", "text two"])

    payload = json.loads(captured["request_data"])
    assert isinstance(payload["input"], list)
    assert payload["input"] == ["text one", "text two"]

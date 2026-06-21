from __future__ import annotations

import pytest

from embedding_provider import APIProvider, LocalProvider, NoneProvider, create_provider


def test_none_provider_returns_empty_vectors() -> None:
    provider = create_provider("none")

    assert isinstance(provider, NoneProvider)
    assert provider.embed_text("private local text") == []
    assert provider.embed_batch(["one", "two"]) == [[], []]


def test_local_provider_exposes_placeholder_vector_shape() -> None:
    provider = create_provider("local")

    assert isinstance(provider, LocalProvider)
    assert provider.model_name == "all-MiniLM-L6-v2"
    assert provider.embed_text("local-only text") == [0.0] * 384
    assert provider.embed_batch(["one", "two"]) == [[0.0] * 384, [0.0] * 384]


def test_api_provider_exposes_placeholder_vector_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    monkeypatch.delenv("EMBEDDING_API_URL", raising=False)

    provider = create_provider("api")

    assert isinstance(provider, APIProvider)
    assert provider.api_key is None
    assert provider.base_url == "https://api.openai.com/v1"
    assert provider.embed_text("api-backed text") == [0.0] * 1536
    assert provider.embed_batch(["one"]) == [[0.0] * 1536]


def test_create_provider_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="Unknown provider type"):
        create_provider("unknown")

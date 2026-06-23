from __future__ import annotations

import json
from pathlib import Path

import pytest

from embedding_provider import LocalProvider
from mindvault_mcp.config import AppConfig, EmbeddingConfig, StorageConfig
from mindvault_mcp.models import Card
from mindvault_mcp.tools import build_runtime


def _runtime(tmp_path: Path, embedding: EmbeddingConfig):
    return build_runtime(
        AppConfig(
            storage=StorageConfig(
                primary_path=tmp_path / "primary",
                staging_path=tmp_path / "staging",
                sqlite_path=tmp_path / "mindvault.sqlite",
            ),
            embedding=embedding,
        )
    )


def test_fingerprint_format_none() -> None:
    config = EmbeddingConfig(provider="none")

    assert config.get_model_fingerprint(384) == "none::dim0"


def test_fingerprint_format_local() -> None:
    config = EmbeddingConfig(provider="local", local_model_path="model-path")

    assert config.get_model_fingerprint(384) == "local:model-path:dim384"


def test_fingerprint_format_api() -> None:
    config = EmbeddingConfig(provider="api", api_model="text-embedding-3-small")

    assert config.get_model_fingerprint(1536) == "api:text-embedding-3-small:dim1536"


def test_cache_miss_on_fingerprint_change(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    embedded_models: list[str] = []

    def fake_embed_text(self: LocalProvider, text: str) -> list[float]:
        embedded_models.append(self.model_name)
        if self.model_name == "model-b":
            return [0.0, 1.0]
        return [1.0, 0.0]

    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
    monkeypatch.setattr(LocalProvider, "embed_text", fake_embed_text)
    runtime = _runtime(
        tmp_path,
        EmbeddingConfig(provider="local", local_model_path="model-a"),
    )
    card = runtime.repository.save(Card(title="Fingerprint miss", problem="cache me"))

    assert runtime.embeddings.ensure_card_vector(runtime.repository, card) == [1.0, 0.0]

    runtime.config.embedding.local_model_path = "model-b"

    assert runtime.embeddings.ensure_card_vector(runtime.repository, card) == [0.0, 1.0]
    assert embedded_models == ["model-a", "model-b"]
    stored = runtime.repository.get_card_embedding(card.card_id, "local")
    assert stored is not None
    assert stored["model_fingerprint"] == "local:model-b:dim2"


def test_cache_hit_on_fingerprint_match(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    embedded_texts: list[str] = []

    def fake_embed_text(self: LocalProvider, text: str) -> list[float]:
        embedded_texts.append(text)
        return [0.25, 0.75]

    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
    monkeypatch.setattr(LocalProvider, "embed_text", fake_embed_text)
    runtime = _runtime(
        tmp_path,
        EmbeddingConfig(provider="local", local_model_path="model-a"),
    )
    card = runtime.repository.save(Card(title="Fingerprint hit", problem="cache me"))

    first = runtime.embeddings.ensure_card_vector(runtime.repository, card)
    second = runtime.embeddings.ensure_card_vector(runtime.repository, card)

    assert first == [0.25, 0.75]
    assert second == [0.25, 0.75]
    assert embedded_texts == [card.searchable_text()]


def test_migration_empty_fingerprint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    embedded_texts: list[str] = []

    def fake_embed_text(self: LocalProvider, text: str) -> list[float]:
        embedded_texts.append(text)
        return [0.1, 0.2]

    monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
    monkeypatch.setattr(LocalProvider, "embed_text", fake_embed_text)
    runtime = _runtime(
        tmp_path,
        EmbeddingConfig(provider="local", local_model_path="model-a"),
    )
    card = runtime.repository.save(Card(title="Legacy fingerprint", problem="cache me"))
    searchable_text_hash = runtime.embeddings.text_hash(card.searchable_text())
    with runtime.repository.sqlite_index.connect() as conn:
        conn.execute(
            """
            INSERT INTO card_embeddings (
                card_id, provider, dimension, vector_json, searchable_text_hash, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                card.card_id,
                "local",
                2,
                json.dumps([0.9, 0.9]),
                searchable_text_hash,
                card.updated_at.isoformat(),
            ),
        )

    vector = runtime.embeddings.ensure_card_vector(runtime.repository, card)

    assert vector == [0.1, 0.2]
    assert embedded_texts == [card.searchable_text()]
    stored = runtime.repository.get_card_embedding(card.card_id, "local")
    assert stored is not None
    assert stored["vector"] == [0.1, 0.2]
    assert stored["model_fingerprint"] == "local:model-a:dim2"

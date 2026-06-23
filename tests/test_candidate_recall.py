from __future__ import annotations

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


def test_candidate_limit_uses_multiplier(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EMBEDDING_CANDIDATE_MULTIPLIER", raising=False)
    monkeypatch.delenv("EMBEDDING_CANDIDATE_MAX", raising=False)
    runtime = _runtime(
        tmp_path,
        EmbeddingConfig(provider="local", candidate_multiplier=4, candidate_max=1000),
    )

    assert runtime.embeddings.compute_candidate_limit(limit=10, offset=5) == 60


def test_candidate_limit_respects_max(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EMBEDDING_CANDIDATE_MULTIPLIER", raising=False)
    monkeypatch.delenv("EMBEDDING_CANDIDATE_MAX", raising=False)
    runtime = _runtime(
        tmp_path,
        EmbeddingConfig(provider="local", candidate_multiplier=5, candidate_max=200),
    )

    assert runtime.embeddings.compute_candidate_limit(limit=100, offset=0) == 200


def test_candidate_limit_never_below_window(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EMBEDDING_CANDIDATE_MULTIPLIER", raising=False)
    monkeypatch.delenv("EMBEDDING_CANDIDATE_MAX", raising=False)
    runtime = _runtime(
        tmp_path,
        EmbeddingConfig(provider="local", candidate_multiplier=1, candidate_max=5),
    )

    assert runtime.embeddings.compute_candidate_limit(limit=20, offset=10) == 30


def test_candidate_limit_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = _runtime(
        tmp_path,
        EmbeddingConfig(provider="local", candidate_multiplier=5, candidate_max=200),
    )

    monkeypatch.setenv("EMBEDDING_CANDIDATE_MULTIPLIER", "3")
    monkeypatch.setenv("EMBEDDING_CANDIDATE_MAX", "500")
    assert runtime.embeddings.compute_candidate_limit(limit=10, offset=0) == 30

    monkeypatch.setenv("EMBEDDING_CANDIDATE_MAX", "20")
    assert runtime.embeddings.compute_candidate_limit(limit=10, offset=0) == 20


def test_candidate_limit_env_invalid_falls_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = _runtime(
        tmp_path,
        EmbeddingConfig(provider="local", candidate_multiplier=5, candidate_max=200),
    )

    monkeypatch.setenv("EMBEDDING_CANDIDATE_MULTIPLIER", "not-an-int")
    monkeypatch.setenv("EMBEDDING_CANDIDATE_MAX", "also-bad")
    assert runtime.embeddings.compute_candidate_limit(limit=10, offset=0) == 50


def test_rank_cards_with_scores_returns_scores(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_embed_text(self: LocalProvider, text: str) -> list[float]:
        if "close vector" in text:
            return [0.9, 0.1]
        if "far vector" in text:
            return [0.1, 0.9]
        return [0.0, 0.0]

    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    monkeypatch.setattr(LocalProvider, "embed_text", fake_embed_text)
    runtime = _runtime(tmp_path, EmbeddingConfig(provider="local"))
    far = Card(title="Far card", problem="far vector")
    close = Card(title="Close card", problem="close vector")
    runtime.repository.save(far)
    runtime.repository.save(close)
    query_vector = [1.0, 0.0]

    scored = runtime.embeddings.rank_cards_with_scores(
        runtime.repository, query_vector, [far, close]
    )

    assert [card.card_id for _, card in scored] == [close.card_id, far.card_id]
    assert all(isinstance(score, float) for score, _ in scored)
    assert scored[0][0] >= scored[1][0]


def test_rank_cards_backward_compat(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_embed_text(self: LocalProvider, text: str) -> list[float]:
        if "close vector" in text:
            return [0.9, 0.1]
        if "far vector" in text:
            return [0.1, 0.9]
        return [0.0, 0.0]

    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    monkeypatch.setattr(LocalProvider, "embed_text", fake_embed_text)
    runtime = _runtime(tmp_path, EmbeddingConfig(provider="local"))
    far = Card(title="Far card", problem="far vector")
    close = Card(title="Close card", problem="close vector")
    runtime.repository.save(far)
    runtime.repository.save(close)
    query_vector = [1.0, 0.0]

    ranked = runtime.embeddings.rank_cards(runtime.repository, query_vector, [far, close])
    scored = runtime.embeddings.rank_cards_with_scores(
        runtime.repository, query_vector, [far, close]
    )

    assert all(isinstance(card, Card) for card in ranked)
    assert [card.card_id for card in ranked] == [card.card_id for _, card in scored]

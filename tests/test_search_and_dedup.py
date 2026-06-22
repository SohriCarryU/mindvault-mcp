from __future__ import annotations

from datetime import timedelta

from embedding_provider import APIProvider, LocalProvider
from mindvault_mcp.config import AppConfig, DedupConfig
from mindvault_mcp.enums import CardStatus, Library
from mindvault_mcp.models import Card, utc_now
from mindvault_mcp.tools import approve_card, ingest_memory, search_cards


def test_search_groups_by_library_and_sorts_by_confidence_then_updated(runtime) -> None:
    staging_low = Card(
        title="Memory search staging low",
        problem="keyword match",
        confidence=0.2,
        library=Library.STAGING,
    )
    primary_low = Card(
        title="Memory search primary low",
        problem="keyword match",
        confidence=0.1,
        library=Library.PRIMARY,
        status=CardStatus.ACTIVE,
    )
    primary_high_old = Card(
        title="Memory search primary high old",
        problem="keyword match",
        confidence=0.9,
        library=Library.PRIMARY,
        status=CardStatus.ACTIVE,
    )
    primary_high_new = Card(
        title="Memory search primary high new",
        problem="keyword match",
        confidence=0.9,
        library=Library.PRIMARY,
        status=CardStatus.ACTIVE,
    )
    primary_high_old.updated_at = utc_now() - timedelta(days=1)
    primary_high_new.updated_at = utc_now()
    for card in [staging_low, primary_low, primary_high_old, primary_high_new]:
        runtime.repository.save(card)

    results = search_cards(runtime, "admin-token", query="keyword")

    assert list(results.results) == ["primary", "staging"]
    assert [card.card_id for card in results.results["primary"]] == [
        primary_high_new.card_id,
        primary_high_old.card_id,
        primary_low.card_id,
    ]
    assert [card.card_id for card in results.results["staging"]] == [staging_low.card_id]


def test_search_filters_by_permissions_query_tags_and_domain(runtime) -> None:
    visible = Card(
        title="Visible private search",
        problem="keyword visible",
        tags=["review"],
        domain="agent-ops",
        privacy_level=3,
    )
    hidden = Card(
        title="Hidden private search",
        problem="keyword hidden",
        tags=["review"],
        domain="agent-ops",
        privacy_level=7,
    )
    other = Card(
        title="Other domain search",
        problem="keyword visible",
        tags=["review"],
        domain="ops",
        privacy_level=3,
    )
    for card in [visible, hidden, other]:
        runtime.repository.save(card)

    results = search_cards(
        runtime,
        "trusted-token",
        query="keyword",
        tags=["review"],
        domain="agent-ops",
        library="staging",
    )

    assert [card.card_id for card in results.results["staging"]] == [visible.card_id]


def test_ingest_sets_possible_duplicate_when_similarity_crosses_threshold(runtime) -> None:
    first = ingest_memory(
        runtime,
        "trusted-token",
        "Problem: Agent memory review repeats setup context.\nSolution: Store review cards.",
        {"tags": ["memory", "review"], "domain": "agent-ops", "confidence": 0.8},
    )
    second = ingest_memory(
        runtime,
        "trusted-token",
        "Problem: Agent memory review repeats setup context often.\nSolution: Store reviewed cards.",
        {"tags": ["memory", "review"], "domain": "agent-ops", "confidence": 0.8},
    )

    assert first.card is not None
    assert second.card is not None
    assert second.card.possible_duplicate_of == first.card.card_id
    assert second.card.library == Library.STAGING
    assert runtime.repository.get(second.card.card_id).library == Library.STAGING


def test_dedup_threshold_boundary(tmp_path) -> None:
    config = AppConfig(
        storage={
            "primary_path": tmp_path / "primary",
            "staging_path": tmp_path / "staging",
            "sqlite_path": tmp_path / "mindvault.sqlite",
        },
        dedup=DedupConfig(similarity_threshold=0.95),
    )
    from mindvault_mcp.tools import build_runtime

    runtime = build_runtime(config)
    first = Card(title="Agent memory review", tags=["memory"], domain="agent-ops")
    runtime.repository.save(first)
    candidate = Card(title="Agent memory setup review", tags=["memory"], domain="agent-ops")

    assert runtime.dedup.find_possible_duplicate(candidate) is None


def test_search_with_none_embedding_provider_keeps_keyword_behavior(runtime) -> None:
    card = Card(title="None embedding search", problem="needle remains keyword based")
    runtime.repository.save(card)

    results = search_cards(runtime, "trusted-token", query="needle", library="staging")

    assert [found.card_id for found in results.results["staging"]] == [card.card_id]


def test_search_with_local_embedding_provider_smoke_path(runtime, monkeypatch) -> None:
    calls: list[str] = []

    def fake_embed_text(self: LocalProvider, text: str) -> list[float]:
        calls.append(text)
        return [0.0] * 384

    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    monkeypatch.setattr(LocalProvider, "embed_text", fake_embed_text)
    card = Card(title="Local embedding search", problem="needle remains keyword based")
    runtime.repository.save(card)

    results = search_cards(runtime, "trusted-token", query="needle", library="staging")

    assert calls == ["needle"]
    assert [found.card_id for found in results.results["staging"]] == [card.card_id]


def test_search_with_api_embedding_provider_smoke_path(runtime, monkeypatch) -> None:
    calls: list[str] = []

    def fake_embed_text(self: APIProvider, text: str) -> list[float]:
        calls.append(text)
        return [0.0] * 1536

    monkeypatch.setenv("EMBEDDING_PROVIDER", "api")
    monkeypatch.setattr(APIProvider, "embed_text", fake_embed_text)
    card = Card(title="API embedding search", problem="needle remains keyword based")
    runtime.repository.save(card)

    results = search_cards(runtime, "trusted-token", query="needle", library="staging")

    assert calls == ["needle"]
    assert [found.card_id for found in results.results["staging"]] == [card.card_id]


def test_search_with_invalid_embedding_provider_raises(runtime, monkeypatch) -> None:
    monkeypatch.setenv("EMBEDDING_PROVIDER", "invalid")

    import pytest

    with pytest.raises(ValueError, match="Unknown provider type"):
        search_cards(runtime, "trusted-token", query="needle", library="staging")


def test_semantic_search_ranks_by_vector_similarity(runtime, monkeypatch) -> None:
    def fake_embed_text(self: LocalProvider, text: str) -> list[float]:
        if "semantic intent" in text:
            return [1.0, 0.0]
        if "close vector" in text:
            return [0.9, 0.1]
        if "far vector" in text:
            return [0.1, 0.9]
        return [0.0, 0.0]

    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    monkeypatch.setattr(LocalProvider, "embed_text", fake_embed_text)
    far = Card(title="Unrelated far card", problem="far vector", confidence=0.9)
    close = Card(title="Unrelated close card", problem="close vector", confidence=0.1)
    runtime.repository.save(far)
    runtime.repository.save(close)

    response = search_cards(runtime, "trusted-token", query="semantic intent", library="staging")

    assert response.message == "Search completed with semantic vector ranking."
    assert [card.card_id for card in response.results["staging"]] == [close.card_id, far.card_id]


def test_semantic_search_falls_back_to_keyword_when_vectors_are_zero(runtime, monkeypatch) -> None:
    def fake_embed_text(self: LocalProvider, text: str) -> list[float]:
        return [0.0] * 384

    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    monkeypatch.setattr(LocalProvider, "embed_text", fake_embed_text)
    card = Card(title="Zero vector search", problem="keyword remains searchable")
    runtime.repository.save(card)

    response = search_cards(runtime, "trusted-token", query="keyword", library="staging")

    assert response.message == "Search completed without vector embeddings."
    assert [found.card_id for found in response.results["staging"]] == [card.card_id]


def test_semantic_search_does_not_embed_unreadable_cards(runtime, monkeypatch) -> None:
    embedded_texts: list[str] = []

    def fake_embed_text(self: LocalProvider, text: str) -> list[float]:
        embedded_texts.append(text)
        if "semantic intent" in text:
            return [1.0, 0.0]
        if "visible vector" in text:
            return [0.9, 0.1]
        if "hidden vector" in text:
            return [1.0, 0.0]
        return [0.0, 0.0]

    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    monkeypatch.setattr(LocalProvider, "embed_text", fake_embed_text)
    hidden = Card(title="Hidden semantic card", problem="hidden vector", privacy_level=7)
    visible = Card(title="Visible semantic card", problem="visible vector", privacy_level=3)
    runtime.repository.save(hidden)
    runtime.repository.save(visible)

    response = search_cards(runtime, "trusted-token", query="semantic intent", library="staging")

    assert [card.card_id for card in response.results["staging"]] == [visible.card_id]
    assert hidden.card_id not in [card.card_id for card in response.results["staging"]]
    assert hidden.searchable_text() not in embedded_texts

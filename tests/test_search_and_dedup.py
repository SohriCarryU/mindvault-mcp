from __future__ import annotations

from datetime import timedelta

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

from __future__ import annotations

import pytest

from mindvault_mcp.auth import AuthError
from mindvault_mcp.enums import CardStatus, Library, VerificationStatus
from mindvault_mcp.tools import (
    approve_card,
    get_card,
    ingest_memory,
    list_candidates,
    queue_verification,
    reject_card,
    search_cards,
    update_card,
)


def test_tools_candidate_lifecycle(runtime) -> None:
    ingest = ingest_memory(
        runtime,
        "trusted-token",
        "Agents need concise durable memory. Store stable insights as cards.",
        {"tags": ["agents"], "domain": "mcp"},
    )
    assert ingest.ok
    assert ingest.card is not None
    card_id = ingest.card.card_id
    assert ingest.card.library == Library.STAGING

    candidates = list_candidates(runtime, "trusted-token")
    assert [card.card_id for card in candidates.candidates] == [card_id]

    updated = update_card(runtime, "trusted-token", card_id, {"solution": "Use Markdown cards plus SQLite."})
    assert updated.card is not None
    assert updated.card.solution == "Use Markdown cards plus SQLite."

    queued = queue_verification(runtime, "trusted-token", card_id)
    assert queued.card is not None
    assert queued.card.verification_status == VerificationStatus.PENDING_VERIFICATION
    assert queued.queue_item is not None

    approved = approve_card(runtime, "admin-token", card_id)
    assert approved.card is not None
    assert approved.card.library == Library.PRIMARY
    assert approved.card.status == CardStatus.ACTIVE

    found = search_cards(runtime, "admin-token", query="durable")
    assert found.results["primary"][0].card_id == card_id

    loaded = get_card(runtime, "admin-token", card_id)
    assert loaded.card is not None
    assert loaded.card.card_id == card_id


def test_reject_candidate(runtime) -> None:
    ingest = ingest_memory(runtime, "trusted-token", "Temporary note that should not graduate.", {})
    assert ingest.card is not None
    rejected = reject_card(runtime, "trusted-token", ingest.card.card_id, "Too transient")
    assert rejected.card is not None
    assert rejected.card.status == CardStatus.REJECTED
    candidates = list_candidates(runtime, "trusted-token")
    assert ingest.card.card_id not in [card.card_id for card in candidates.candidates]


def test_primary_approval_requires_high_trust(runtime) -> None:
    ingest = ingest_memory(runtime, "trusted-token", "Candidate for restricted approval.", {})
    assert ingest.card is not None
    with pytest.raises(AuthError):
        approve_card(runtime, "trusted-token", ingest.card.card_id)


def test_list_candidates_filters_by_domain_tags_confidence_and_pages(runtime) -> None:
    first = ingest_memory(
        runtime,
        "trusted-token",
        "Problem: Indexed agent memory is hard to review.\nSolution: Keep candidates in staging.",
        {"tags": ["review", "memory"], "domain": "agent-ops", "confidence": 0.9},
    )
    second = ingest_memory(
        runtime,
        "trusted-token",
        "Problem: Private notes need retention rules.\nSolution: Use conservative defaults.",
        {"tags": ["privacy"], "domain": "agent-ops", "confidence": 0.4},
    )
    third = ingest_memory(
        runtime,
        "trusted-token",
        "Problem: Review queues need clear ownership.\nSolution: Filter candidates by tag.",
        {"tags": ["review"], "domain": "ops", "confidence": 0.95},
    )
    assert first.card and second.card and third.card

    filtered = list_candidates(
        runtime,
        "trusted-token",
        domain="agent-ops",
        tags=["review"],
        min_confidence=0.8,
        limit=1,
        offset=0,
    )
    assert [card.card_id for card in filtered.candidates] == [first.card.card_id]


def test_approve_preserves_source_and_created_at_with_consistent_storage(runtime) -> None:
    ingest = ingest_memory(
        runtime,
        "trusted-token",
        "Problem: Candidate promotion needs durable state.\nSolution: Move reviewed cards to primary.",
        {"source_agent": "source-agent", "confidence": 0.8},
    )
    assert ingest.card is not None
    created_at = ingest.card.created_at

    approved = approve_card(runtime, "admin-token", ingest.card.card_id)
    assert approved.card is not None
    assert approved.card.source_agent == "source-agent"
    assert approved.card.created_at == created_at
    assert approved.card.updated_at > created_at

    markdown_card = runtime.repository.markdown_store.read_card(Library.PRIMARY, ingest.card.card_id)
    indexed_location = runtime.repository.sqlite_index.get_card_location(ingest.card.card_id)
    assert markdown_card.status == CardStatus.ACTIVE
    assert indexed_location == (ingest.card.card_id, Library.PRIMARY)


def test_approve_non_staging_card_fails(runtime) -> None:
    ingest = ingest_memory(
        runtime,
        "trusted-token",
        "Problem: Already approved cards should not be approved twice.",
        {},
    )
    assert ingest.card is not None
    approve_card(runtime, "admin-token", ingest.card.card_id)

    with pytest.raises(ValueError, match="Only staging"):
        approve_card(runtime, "admin-token", ingest.card.card_id)

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


def test_primary_approval_requires_high_trust(runtime) -> None:
    ingest = ingest_memory(runtime, "trusted-token", "Candidate for restricted approval.", {})
    assert ingest.card is not None
    with pytest.raises(AuthError):
        approve_card(runtime, "trusted-token", ingest.card.card_id)

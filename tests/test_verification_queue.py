from __future__ import annotations

from datetime import timedelta

from mindvault_mcp.enums import VerificationStatus
from mindvault_mcp.models import Card, utc_now
from mindvault_mcp.tools import get_card, queue_verification


def test_queue_verification_persists_queue_record(runtime) -> None:
    card = Card(title="Needs verification", problem="External facts may expire.")
    runtime.repository.save(card)

    response = queue_verification(runtime, "trusted-token", card.card_id, reason="Check source freshness")

    assert response.card is not None
    assert response.card.verification_status == VerificationStatus.PENDING_VERIFICATION
    pending = runtime.repository.list_pending_verifications()
    assert len(pending) == 1
    assert pending[0].card_id == card.card_id
    assert pending[0].reason == "Check source freshness"
    assert pending[0].status == "pending"


def test_expired_valid_until_marks_card_expired_on_read(runtime) -> None:
    card = Card(
        title="Expiring fact",
        problem="This fact has a date.",
        valid_until=utc_now() - timedelta(days=1),
        verification_status=VerificationStatus.VERIFIED,
    )
    runtime.repository.save(card)

    loaded = get_card(runtime, "trusted-token", card.card_id)

    assert loaded.card is not None
    assert loaded.card.verification_status == VerificationStatus.EXPIRED
    assert runtime.repository.get(card.card_id).verification_status == VerificationStatus.EXPIRED


def test_no_verification_needed_card_does_not_expire(runtime) -> None:
    card = Card(
        title="Stable preference",
        problem="No external verification needed.",
        valid_until=utc_now() - timedelta(days=1),
        verification_status=VerificationStatus.NO_VERIFICATION_NEEDED,
    )
    runtime.repository.save(card)

    loaded = get_card(runtime, "trusted-token", card.card_id)

    assert loaded.card is not None
    assert loaded.card.verification_status == VerificationStatus.NO_VERIFICATION_NEEDED

from __future__ import annotations

from mindvault_mcp.enums import CardStatus, Library, VerificationStatus
from mindvault_mcp.models import Card, VerificationQueueItem, utc_now
from mindvault_mcp.services.validation import ValidationResult, ValidationStatus

from .markdown_store import MarkdownStore
from .sqlite_index import SQLiteIndex


def _verification_status_for_validation(
    status: ValidationStatus,
) -> VerificationStatus | None:
    mapping = {
        ValidationStatus.PASSED: VerificationStatus.VERIFIED,
        ValidationStatus.STALE: VerificationStatus.EXPIRED,
        ValidationStatus.FAILED: VerificationStatus.CONTESTED,
        ValidationStatus.ERROR: VerificationStatus.PENDING_VERIFICATION,
        ValidationStatus.PENDING: VerificationStatus.PENDING_VERIFICATION,
    }
    return mapping.get(status)


class CardRepository:
    def __init__(self, markdown_store: MarkdownStore, sqlite_index: SQLiteIndex):
        self.markdown_store = markdown_store
        self.sqlite_index = sqlite_index

    def save(self, card: Card) -> Card:
        card.touch()
        self.markdown_store.write_card(card)
        self.sqlite_index.upsert_card(card)
        return card

    def get(self, card_id: str) -> Card:
        location = self.sqlite_index.get_card_location(card_id)
        if location is None:
            raise KeyError(f"Card not found: {card_id}")
        _, library = location
        card = self.markdown_store.read_card(library, card_id)
        return self._apply_expiration(card)

    def search(
        self,
        query: str | None = None,
        tags: list[str] | None = None,
        domain: str | None = None,
        library: Library | str | None = None,
        status: str | None = None,
        verification_status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Card]:
        locations = self.sqlite_index.search(
            query=query,
            tags=tags,
            domain=domain,
            library=library,
            status=status,
            verification_status=verification_status,
            limit=limit,
            offset=offset,
        )
        return [self.markdown_store.read_card(lib, card_id) for card_id, lib in locations]

    def approve(self, card_id: str, source_agent: str) -> Card:
        card = self.get(card_id)
        old_library = Library(card.library)
        if old_library != Library.STAGING:
            raise ValueError("Only staging cards can be approved.")
        card.library = Library.PRIMARY
        card.status = CardStatus.ACTIVE
        card.source_agent = card.source_agent or source_agent
        self.markdown_store.delete_card(old_library, card.card_id)
        return self.save(card)

    def reject(self, card_id: str, reason: str) -> Card:
        card = self.get(card_id)
        if Library(card.library) != Library.STAGING:
            raise ValueError("Only staging cards can be rejected.")
        card.status = CardStatus.REJECTED
        suffix = f"\n\nRejection reason: {reason}" if reason else ""
        card.context = f"{card.context}{suffix}".strip()
        return self.save(card)

    def update(self, card_id: str, fields: dict[str, object]) -> Card:
        card = self.get(card_id)
        for key, value in fields.items():
            if hasattr(card, key):
                setattr(card, key, value)
        return self.save(Card.model_validate(card.model_dump()))

    def queue_verification(self, card_id: str, item: VerificationQueueItem | None = None) -> Card:
        card = self.get(card_id)
        card.verification_status = VerificationStatus.PENDING_VERIFICATION
        updated = self.save(card)
        if item is not None:
            self.sqlite_index.enqueue_verification(item)
        return updated

    def list_pending_verifications(self) -> list[VerificationQueueItem]:
        return self.sqlite_index.list_verification_queue(status="pending")

    def record_validation_result(self, result: ValidationResult) -> Card:
        card = self.get(result.card_id)
        self.sqlite_index.record_validation_result(result)
        verification_status = _verification_status_for_validation(result.status)
        if verification_status is None:
            return card
        card.verification_status = verification_status
        return self.save(card)

    def list_validation_results(
        self, card_id: str, limit: int = 20, offset: int = 0
    ) -> list[ValidationResult]:
        return self.sqlite_index.list_validation_results(card_id, limit=limit, offset=offset)

    def save_card_embedding(
        self,
        card_id: str,
        provider: str,
        vector: list[float],
        searchable_text_hash: str,
        model_fingerprint: str,
        updated_at: str,
    ) -> None:
        self.sqlite_index.save_card_embedding(
            card_id=card_id,
            provider=provider,
            vector=vector,
            searchable_text_hash=searchable_text_hash,
            model_fingerprint=model_fingerprint,
            updated_at=updated_at,
        )

    def upsert_card_embedding(
        self,
        card_id: str,
        provider: str,
        vector: list[float],
        searchable_text_hash: str,
        updated_at: str,
        model_fingerprint: str = "",
    ) -> None:
        self.save_card_embedding(
            card_id=card_id,
            provider=provider,
            vector=vector,
            searchable_text_hash=searchable_text_hash,
            model_fingerprint=model_fingerprint,
            updated_at=updated_at,
        )

    def get_card_embedding(self, card_id: str, provider: str) -> dict[str, object] | None:
        return self.sqlite_index.get_card_embedding(card_id, provider)

    def _apply_expiration(self, card: Card) -> Card:
        if (
            card.valid_until is not None
            and card.valid_until < utc_now()
            and card.verification_status != VerificationStatus.NO_VERIFICATION_NEEDED
            and card.verification_status != VerificationStatus.EXPIRED
        ):
            card.verification_status = VerificationStatus.EXPIRED
            self.save(card)
        return card

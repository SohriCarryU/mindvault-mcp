from __future__ import annotations

import os
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from mindvault_mcp.config import AppConfig
from mindvault_mcp.models import Card, VerificationQueueItem, utc_now


class ValidationStatus(StrEnum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    STALE = "stale"
    SKIPPED = "skipped"
    ERROR = "error"


class ValidationResult(BaseModel):
    card_id: str = Field(min_length=1)
    status: ValidationStatus
    checked_at: datetime = Field(default_factory=utc_now)
    source_type: str = "none"
    source_ref: str = ""
    message: str
    evidence: str | None = None
    error: str | None = None


def _env_bool(name: str) -> bool | None:
    value = os.getenv(name)
    if value is None:
        return None
    return value.strip().lower() in {"1", "true", "yes", "on"}


class ExternalValidationService:
    def __init__(self, config: AppConfig):
        env_enabled = _env_bool("EXTERNAL_VALIDATION_ENABLED")
        self.enabled = env_enabled if env_enabled is not None else config.verification.external_validation_enabled
        self.backend_mode = config.verification.backend_mode

    def create_validation_job(self, card: Card, queued_by: str, reason: str = "") -> VerificationQueueItem:
        self._require_card_id(card)
        return VerificationQueueItem(
            card_id=card.card_id,
            queued_by=queued_by,
            backend_mode=self.backend_mode,
            reason=reason,
            status=ValidationStatus.PENDING.value,
            note="External validation protocol is queued; network validation is not implemented in phase 6-A.",
        )

    def validate_card(
        self,
        card: Card,
        source_type: str = "none",
        source_ref: str = "",
    ) -> ValidationResult:
        self._require_card_id(card)
        if not self.enabled:
            return ValidationResult(
                card_id=card.card_id,
                status=ValidationStatus.SKIPPED,
                source_type=source_type,
                source_ref=source_ref,
                message="External validation is disabled.",
            )
        if not source_ref.strip():
            return ValidationResult(
                card_id=card.card_id,
                status=ValidationStatus.SKIPPED,
                source_type=source_type,
                source_ref=source_ref,
                message="External validation skipped because source_ref is missing.",
            )
        return ValidationResult(
            card_id=card.card_id,
            status=ValidationStatus.SKIPPED,
            source_type=source_type,
            source_ref=source_ref,
            message="External validation protocol is enabled, but real validators are not implemented in phase 6-A.",
        )

    def validate_cards(
        self,
        cards: list[Card],
        source_type: str = "none",
        source_ref: str = "",
    ) -> list[ValidationResult]:
        return [self.validate_card(card, source_type=source_type, source_ref=source_ref) for card in cards]

    def _require_card_id(self, card: Card) -> None:
        if not card.card_id.strip():
            raise ValueError("card_id is required for external validation")

from __future__ import annotations

import os
from datetime import datetime
from enum import StrEnum
from urllib import error, parse, request

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


class LinkValidationOutcome(BaseModel):
    status: ValidationStatus
    message: str
    evidence: str
    error: str | None = None


def _env_bool(name: str) -> bool | None:
    value = os.getenv(name)
    if value is None:
        return None
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str) -> float | None:
    value = os.getenv(name)
    if value is None:
        return None
    try:
        parsed = float(value)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def _is_http_url(source_ref: str) -> bool:
    parsed = parse.urlparse(source_ref)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _status_to_validation_status(status_code: int) -> ValidationStatus:
    if 200 <= status_code <= 399:
        return ValidationStatus.PASSED
    if status_code == 410:
        return ValidationStatus.STALE
    if 400 <= status_code <= 499:
        return ValidationStatus.FAILED
    return ValidationStatus.ERROR


class LinkValidator:
    def __init__(self, timeout_seconds: float = 5.0):
        self.timeout_seconds = timeout_seconds

    def validate(self, url: str) -> LinkValidationOutcome:
        try:
            return self._open(url, method="HEAD")
        except error.HTTPError as exc:
            if exc.code in {405, 501}:
                try:
                    return self._open(url, method="GET")
                except error.HTTPError as get_exc:
                    return self._from_http_error(get_exc, method="GET")
            return self._from_http_error(exc, method="HEAD")
        except Exception as exc:
            return self._from_network_error(exc, method="HEAD")

    def _open(self, url: str, method: str) -> LinkValidationOutcome:
        try:
            req = request.Request(url, method=method)
            response = request.urlopen(req, timeout=self.timeout_seconds)
            try:
                status_code = int(response.getcode())
                final_url = response.geturl()
            finally:
                response.close()
            return self._from_status(status_code, method=method, final_url=final_url)
        except error.HTTPError as exc:
            raise exc
        except Exception as exc:
            return self._from_network_error(exc, method=method)

    def _from_status(self, status_code: int, method: str, final_url: str) -> LinkValidationOutcome:
        status = _status_to_validation_status(status_code)
        return LinkValidationOutcome(
            status=status,
            message=f"Link validation completed with HTTP status {status_code}.",
            evidence=f"method={method}; status_code={status_code}; final_url={final_url}",
        )

    def _from_http_error(self, exc: error.HTTPError, method: str) -> LinkValidationOutcome:
        status = _status_to_validation_status(exc.code)
        return LinkValidationOutcome(
            status=status,
            message=f"Link validation completed with HTTP status {exc.code}.",
            evidence=f"method={method}; status_code={exc.code}; final_url={exc.url}",
            error=str(exc) if status == ValidationStatus.ERROR else None,
        )

    def _from_network_error(self, exc: Exception, method: str) -> LinkValidationOutcome:
        return LinkValidationOutcome(
            status=ValidationStatus.ERROR,
            message="Link validation failed due to a network error.",
            evidence=f"method={method}",
            error=str(exc),
        )


class ExternalValidationService:
    def __init__(self, config: AppConfig):
        env_enabled = _env_bool("EXTERNAL_VALIDATION_ENABLED")
        env_timeout = _env_float("EXTERNAL_VALIDATION_TIMEOUT_SECONDS")
        self.enabled = (
            env_enabled
            if env_enabled is not None
            else config.verification.external_validation_enabled
        )
        self.backend_mode = config.verification.backend_mode
        self.timeout_seconds = env_timeout or config.verification.external_validation_timeout_seconds
        self.link_validator = LinkValidator(timeout_seconds=self.timeout_seconds)

    def create_validation_job(
        self, card: Card, queued_by: str, reason: str = ""
    ) -> VerificationQueueItem:
        self._require_card_id(card)
        if not self.enabled:
            return VerificationQueueItem(
                card_id=card.card_id,
                queued_by=queued_by,
                backend_mode=self.backend_mode,
                reason=reason,
                status=ValidationStatus.SKIPPED.value,
                note="External validation is disabled; no validation job was queued.",
            )
        return VerificationQueueItem(
            card_id=card.card_id,
            queued_by=queued_by,
            backend_mode=self.backend_mode,
            reason=reason,
            status=ValidationStatus.PENDING.value,
            note="External validation job is queued; Phase 6-B supports minimal URL link checks only.",
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
        if source_type.strip().lower() == "url" and _is_http_url(source_ref):
            outcome = self.link_validator.validate(source_ref)
            return ValidationResult(
                card_id=card.card_id,
                status=outcome.status,
                source_type=source_type,
                source_ref=source_ref,
                message=outcome.message,
                evidence=outcome.evidence,
                error=outcome.error,
            )
        return ValidationResult(
            card_id=card.card_id,
            status=ValidationStatus.SKIPPED,
            source_type=source_type,
            source_ref=source_ref,
            message="External validation skipped because source_type/source_ref is not a supported URL.",
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

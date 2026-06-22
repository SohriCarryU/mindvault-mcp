from __future__ import annotations

import pytest
from pydantic import ValidationError

from mindvault_mcp.config import AppConfig, VerificationConfig
from mindvault_mcp.models import Card
from mindvault_mcp.services.validation import ExternalValidationService, ValidationResult, ValidationStatus


def test_external_validation_disabled_returns_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EXTERNAL_VALIDATION_ENABLED", raising=False)
    service = ExternalValidationService(AppConfig())
    card = Card(title="Fact needing validation")

    result = service.validate_card(card, source_type="url", source_ref="https://example.invalid/fact")

    assert service.enabled is False
    assert result.card_id == card.card_id
    assert result.status == ValidationStatus.SKIPPED
    assert "disabled" in result.message.lower()
    assert result.evidence is None
    assert result.error is None


def test_external_validation_enabled_from_config_reaches_noop_protocol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("EXTERNAL_VALIDATION_ENABLED", raising=False)
    service = ExternalValidationService(
        AppConfig(verification=VerificationConfig(external_validation_enabled=True))
    )
    card = Card(title="Config enabled validation")

    result = service.validate_card(card, source_type="url", source_ref="https://example.invalid/fact")

    assert service.enabled is True
    assert result.status == ValidationStatus.SKIPPED
    assert result.source_type == "url"
    assert result.source_ref == "https://example.invalid/fact"
    assert "not implemented" in result.message.lower()


def test_external_validation_enabled_from_env_reaches_noop_protocol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EXTERNAL_VALIDATION_ENABLED", "true")
    service = ExternalValidationService(AppConfig())
    card = Card(title="Env enabled validation")

    result = service.validate_card(card, source_type="url", source_ref="https://example.invalid/fact")

    assert service.enabled is True
    assert result.status == ValidationStatus.SKIPPED
    assert "not implemented" in result.message.lower()


def test_external_validation_missing_source_ref_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXTERNAL_VALIDATION_ENABLED", "true")
    service = ExternalValidationService(AppConfig())
    card = Card(title="Missing source")

    result = service.validate_card(card, source_type="url", source_ref="")

    assert result.status == ValidationStatus.SKIPPED
    assert "source_ref" in result.message


def test_create_validation_job_reuses_verification_queue_item(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EXTERNAL_VALIDATION_ENABLED", raising=False)
    service = ExternalValidationService(AppConfig())
    card = Card(title="Queue validation job")

    item = service.create_validation_job(card, queued_by="agent-1", reason="Check source freshness")

    assert item.card_id == card.card_id
    assert item.queued_by == "agent-1"
    assert item.reason == "Check source freshness"
    assert item.status == ValidationStatus.PENDING.value


def test_validation_result_rejects_invalid_status() -> None:
    with pytest.raises(ValidationError):
        ValidationResult(card_id="card-1", status="invalid", source_type="url", source_ref="x", message="bad")


def test_validate_card_rejects_blank_card_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EXTERNAL_VALIDATION_ENABLED", raising=False)
    service = ExternalValidationService(AppConfig())
    card = Card(title="Blank id")
    card.card_id = " "

    with pytest.raises(ValueError, match="card_id"):
        service.validate_card(card)

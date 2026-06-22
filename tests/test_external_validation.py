from __future__ import annotations

import urllib.error

import pytest
from pydantic import ValidationError

from mindvault_mcp.config import AppConfig, VerificationConfig
from mindvault_mcp.models import Card
import mindvault_mcp.services.validation as validation_module
from mindvault_mcp.services.validation import (
    ExternalValidationService,
    ValidationResult,
    ValidationStatus,
)


class FakeResponse:
    def __init__(self, status_code: int, final_url: str = "https://example.invalid/final"):
        self.status = status_code
        self._final_url = final_url
        self.closed = False

    def getcode(self) -> int:
        return self.status

    def geturl(self) -> str:
        return self._final_url

    def close(self) -> None:
        self.closed = True


def enabled_validation_service(monkeypatch: pytest.MonkeyPatch) -> ExternalValidationService:
    monkeypatch.setenv("EXTERNAL_VALIDATION_ENABLED", "true")
    return ExternalValidationService(AppConfig())


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


def test_external_validation_disabled_does_not_call_link_validator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_urlopen(*args: object, **kwargs: object) -> None:
        raise AssertionError("urlopen should not be called when external validation is disabled")

    monkeypatch.delenv("EXTERNAL_VALIDATION_ENABLED", raising=False)
    monkeypatch.setattr(validation_module.request, "urlopen", fail_urlopen)
    service = ExternalValidationService(AppConfig())
    card = Card(title="Disabled link validation")

    result = service.validate_card(card, source_type="url", source_ref="https://example.invalid/fact")

    assert result.status == ValidationStatus.SKIPPED
    assert "disabled" in result.message.lower()


def test_external_validation_enabled_from_config_reaches_noop_protocol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("EXTERNAL_VALIDATION_ENABLED", raising=False)
    service = ExternalValidationService(
        AppConfig(verification=VerificationConfig(external_validation_enabled=True))
    )
    card = Card(title="Config enabled validation")

    result = service.validate_card(card, source_type="document", source_ref="internal-source")

    assert service.enabled is True
    assert result.status == ValidationStatus.SKIPPED
    assert result.source_type == "document"
    assert result.source_ref == "internal-source"
    assert "supported url" in result.message.lower()


def test_external_validation_enabled_from_env_reaches_noop_protocol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EXTERNAL_VALIDATION_ENABLED", "true")
    service = ExternalValidationService(AppConfig())
    card = Card(title="Env enabled validation")

    result = service.validate_card(card, source_type="document", source_ref="internal-source")

    assert service.enabled is True
    assert result.status == ValidationStatus.SKIPPED
    assert "supported url" in result.message.lower()


def test_external_validation_missing_source_ref_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXTERNAL_VALIDATION_ENABLED", "true")
    service = ExternalValidationService(AppConfig())
    card = Card(title="Missing source")

    result = service.validate_card(card, source_type="url", source_ref="")

    assert result.status == ValidationStatus.SKIPPED
    assert "source_ref" in result.message


@pytest.mark.parametrize(
    ("status_code", "expected_status"),
    [
        (200, ValidationStatus.PASSED),
        (301, ValidationStatus.PASSED),
        (302, ValidationStatus.PASSED),
    ],
)
def test_link_validation_passes_for_success_and_redirect_statuses(
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
    expected_status: ValidationStatus,
) -> None:
    calls: list[tuple[str, float]] = []

    def fake_urlopen(request: object, timeout: float) -> FakeResponse:
        calls.append((request.get_method(), timeout))
        return FakeResponse(status_code)

    monkeypatch.setattr(validation_module.request, "urlopen", fake_urlopen)
    service = enabled_validation_service(monkeypatch)
    card = Card(title="Live link")

    result = service.validate_card(card, source_type="url", source_ref="https://example.invalid/fact")

    assert calls == [("HEAD", 5.0)]
    assert result.status == expected_status
    assert result.error is None
    assert "method=HEAD" in result.evidence
    assert f"status_code={status_code}" in result.evidence


@pytest.mark.parametrize(
    ("status_code", "expected_status"),
    [
        (404, ValidationStatus.FAILED),
        (410, ValidationStatus.STALE),
        (500, ValidationStatus.ERROR),
    ],
)
def test_link_validation_maps_http_errors(
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
    expected_status: ValidationStatus,
) -> None:
    def fake_urlopen(request: object, timeout: float) -> None:
        raise urllib.error.HTTPError(
            url=request.full_url,
            code=status_code,
            msg="test status",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(validation_module.request, "urlopen", fake_urlopen)
    service = enabled_validation_service(monkeypatch)
    card = Card(title="Broken link")

    result = service.validate_card(card, source_type="url", source_ref="https://example.invalid/fact")

    assert result.status == expected_status
    assert f"status_code={status_code}" in result.evidence


@pytest.mark.parametrize(
    "exc",
    [TimeoutError("timed out"), urllib.error.URLError("temporary failure")],
)
def test_link_validation_network_errors_return_error(
    monkeypatch: pytest.MonkeyPatch,
    exc: Exception,
) -> None:
    def fake_urlopen(request: object, timeout: float) -> None:
        raise exc

    monkeypatch.setattr(validation_module.request, "urlopen", fake_urlopen)
    service = enabled_validation_service(monkeypatch)
    card = Card(title="Network error link")

    result = service.validate_card(card, source_type="url", source_ref="https://example.invalid/fact")

    assert result.status == ValidationStatus.ERROR
    assert result.error is not None
    assert "method=HEAD" in result.evidence


@pytest.mark.parametrize(
    ("source_type", "source_ref"),
    [
        ("url", "not-a-url"),
        ("document", "https://example.invalid/fact"),
        ("url", "ftp://example.invalid/fact"),
    ],
)
def test_link_validation_skips_non_url_sources(
    monkeypatch: pytest.MonkeyPatch,
    source_type: str,
    source_ref: str,
) -> None:
    def fail_urlopen(*args: object, **kwargs: object) -> None:
        raise AssertionError("urlopen should not be called for non-url sources")

    monkeypatch.setattr(validation_module.request, "urlopen", fail_urlopen)
    service = enabled_validation_service(monkeypatch)
    card = Card(title="Non URL source")

    result = service.validate_card(card, source_type=source_type, source_ref=source_ref)

    assert result.status == ValidationStatus.SKIPPED


def test_link_validation_falls_back_to_get_when_head_is_not_supported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_urlopen(request: object, timeout: float) -> FakeResponse:
        method = request.get_method()
        calls.append(method)
        if method == "HEAD":
            raise urllib.error.HTTPError(
                url=request.full_url,
                code=405,
                msg="method not allowed",
                hdrs=None,
                fp=None,
            )
        return FakeResponse(200)

    monkeypatch.setattr(validation_module.request, "urlopen", fake_urlopen)
    service = enabled_validation_service(monkeypatch)
    card = Card(title="Fallback link")

    result = service.validate_card(card, source_type="url", source_ref="https://example.invalid/fact")

    assert calls == ["HEAD", "GET"]
    assert result.status == ValidationStatus.PASSED
    assert "method=GET" in result.evidence


def test_external_validation_timeout_can_be_overridden_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EXTERNAL_VALIDATION_ENABLED", "true")
    monkeypatch.setenv("EXTERNAL_VALIDATION_TIMEOUT_SECONDS", "1.25")

    service = ExternalValidationService(AppConfig())

    assert service.timeout_seconds == 1.25
    assert service.link_validator.timeout_seconds == 1.25


def test_external_validation_invalid_timeout_env_falls_back_to_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EXTERNAL_VALIDATION_ENABLED", "true")
    monkeypatch.setenv("EXTERNAL_VALIDATION_TIMEOUT_SECONDS", "not-a-number")
    config = AppConfig(verification=VerificationConfig(external_validation_timeout_seconds=2.5))

    service = ExternalValidationService(config)

    assert service.timeout_seconds == 2.5


def test_create_validation_job_skips_when_external_validation_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("EXTERNAL_VALIDATION_ENABLED", raising=False)
    service = ExternalValidationService(AppConfig())
    card = Card(title="Queue validation job")

    item = service.create_validation_job(card, queued_by="agent-1", reason="Check source freshness")

    assert item.card_id == card.card_id
    assert item.queued_by == "agent-1"
    assert item.reason == "Check source freshness"
    assert item.status == ValidationStatus.SKIPPED.value
    assert "disabled" in item.note.lower()


def test_create_validation_job_pending_when_external_validation_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EXTERNAL_VALIDATION_ENABLED", "true")
    service = ExternalValidationService(AppConfig())
    card = Card(title="Queue enabled validation job")

    item = service.create_validation_job(card, queued_by="agent-1", reason="Check source freshness")

    assert item.card_id == card.card_id
    assert item.status == ValidationStatus.PENDING.value
    assert "queued" in item.note.lower()


def test_validation_result_rejects_invalid_status() -> None:
    with pytest.raises(ValidationError):
        ValidationResult(
            card_id="card-1",
            status="invalid",
            source_type="url",
            source_ref="x",
            message="bad",
        )


def test_validate_card_rejects_blank_card_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EXTERNAL_VALIDATION_ENABLED", raising=False)
    service = ExternalValidationService(AppConfig())
    card = Card(title="Blank id")
    card.card_id = " "

    with pytest.raises(ValueError, match="card_id"):
        service.validate_card(card)

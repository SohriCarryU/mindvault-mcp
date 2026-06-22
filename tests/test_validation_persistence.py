from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from mindvault_mcp.enums import VerificationStatus
from mindvault_mcp.models import Card
from mindvault_mcp.services.validation import ValidationResult, ValidationStatus
from mindvault_mcp.storage import SQLiteIndex


def validation_result(
    card_id: str,
    status: ValidationStatus = ValidationStatus.PASSED,
    checked_at: datetime | None = None,
    source_type: str = "url",
    source_ref: str = "https://example.invalid/fact",
    message: str = "checked",
    evidence: str | None = "method=HEAD; status_code=200",
    error: str | None = None,
) -> ValidationResult:
    return ValidationResult(
        card_id=card_id,
        status=status,
        checked_at=checked_at or datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
        source_type=source_type,
        source_ref=source_ref,
        message=message,
        evidence=evidence,
        error=error,
    )


def test_sqlite_index_initializes_validation_results_table_and_indexes(tmp_path: Path) -> None:
    index = SQLiteIndex(tmp_path / "index.sqlite")

    with index.connect() as conn:
        columns = {
            row["name"]: row["type"]
            for row in conn.execute("PRAGMA table_info(validation_results)").fetchall()
        }
        indexes = {
            row["name"]
            for row in conn.execute("PRAGMA index_list(validation_results)").fetchall()
        }

    assert columns == {
        "id": "INTEGER",
        "card_id": "TEXT",
        "status": "TEXT",
        "checked_at": "TEXT",
        "source_type": "TEXT",
        "source_ref": "TEXT",
        "message": "TEXT",
        "evidence": "TEXT",
        "error": "TEXT",
    }
    assert "idx_validation_results_card" in indexes
    assert "idx_validation_results_status" in indexes
    assert "idx_validation_results_checked_at" in indexes


def test_sqlite_index_records_passed_validation_result(tmp_path: Path) -> None:
    index = SQLiteIndex(tmp_path / "index.sqlite")
    result = validation_result(card_id="card-1", status=ValidationStatus.PASSED)

    index.record_validation_result(result)

    stored = index.list_validation_results("card-1")
    assert stored == [result]


def test_sqlite_index_lists_validation_results_by_card_and_checked_at_desc(tmp_path: Path) -> None:
    index = SQLiteIndex(tmp_path / "index.sqlite")
    older = validation_result(
        card_id="card-1",
        status=ValidationStatus.FAILED,
        checked_at=datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
        message="older",
    )
    newer = validation_result(
        card_id="card-1",
        status=ValidationStatus.PASSED,
        checked_at=datetime(2026, 1, 1, 11, 0, tzinfo=timezone.utc),
        message="newer",
    )
    other_card = validation_result(
        card_id="card-2",
        status=ValidationStatus.PASSED,
        checked_at=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
        message="other",
    )

    index.record_validation_result(older)
    index.record_validation_result(other_card)
    index.record_validation_result(newer)

    assert index.list_validation_results("card-1") == [newer, older]


@pytest.mark.parametrize(
    ("validation_status", "expected_verification_status"),
    [
        (ValidationStatus.PASSED, VerificationStatus.VERIFIED),
        (ValidationStatus.FAILED, VerificationStatus.CONTESTED),
        (ValidationStatus.STALE, VerificationStatus.EXPIRED),
        (ValidationStatus.ERROR, VerificationStatus.PENDING_VERIFICATION),
        (ValidationStatus.PENDING, VerificationStatus.PENDING_VERIFICATION),
    ],
)
def test_repository_record_validation_result_maps_card_verification_status(
    runtime,
    validation_status: ValidationStatus,
    expected_verification_status: VerificationStatus,
) -> None:
    card = runtime.repository.save(Card(title=f"{validation_status} validation"))
    result = validation_result(card_id=card.card_id, status=validation_status)

    updated = runtime.repository.record_validation_result(result)

    assert updated.verification_status == expected_verification_status
    assert runtime.repository.get(card.card_id).verification_status == expected_verification_status


def test_repository_record_validation_result_persists_skipped_without_changing_card_status(runtime) -> None:
    card = Card(title="Skipped validation", verification_status=VerificationStatus.VERIFIED)
    saved = runtime.repository.save(card)
    result = validation_result(
        card_id=saved.card_id,
        status=ValidationStatus.SKIPPED,
        message="External validation disabled.",
        evidence=None,
    )

    updated = runtime.repository.record_validation_result(result)

    assert updated.verification_status == VerificationStatus.VERIFIED
    assert runtime.repository.list_validation_results(saved.card_id) == [result]


def test_repository_validation_result_preserves_all_result_fields(runtime) -> None:
    card = runtime.repository.save(Card(title="Preserve validation fields"))
    result = validation_result(
        card_id=card.card_id,
        status=ValidationStatus.ERROR,
        source_type="url",
        source_ref="https://example.invalid/source",
        message="Network error",
        evidence="method=HEAD",
        error="timed out",
    )

    runtime.repository.record_validation_result(result)

    stored = runtime.repository.list_validation_results(card.card_id)
    assert stored == [result]
    assert stored[0].source_type == "url"
    assert stored[0].source_ref == "https://example.invalid/source"
    assert stored[0].message == "Network error"
    assert stored[0].evidence == "method=HEAD"
    assert stored[0].error == "timed out"

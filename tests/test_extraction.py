from __future__ import annotations

import pytest

from mindvault_mcp.config import AppConfig, DefaultsConfig, ExtractionConfig
from mindvault_mcp.enums import ExtractionMode, Library
from mindvault_mcp.schemas import IngestMetadata
from mindvault_mcp.services.extraction import RuleBasedExtractor


SAMPLE_TEXT = """
Agent: The onboarding memory keeps getting lost after long sessions.
Problem: Agents repeat the same setup questions because durable notes are missing.
Context: The workflow uses local files and should avoid sending private context to hosted services.
Insight: Stable operational facts should be extracted into reviewable cards instead of raw logs.
Solution: Store candidate cards in staging with tags and promote only reviewed cards to primary.
Tags: onboarding, agent-memory, privacy
Domain: agent-ops
"""


def _extract(mode: ExtractionMode, text: str = SAMPLE_TEXT):
    config = AppConfig(
        extraction=ExtractionConfig(mode=mode),
        defaults=DefaultsConfig(ingest_library=Library.STAGING, privacy_level=2),
    )
    return RuleBasedExtractor(config).extract(text, IngestMetadata(), source_agent="tester")


def test_extraction_modes_have_distinct_fill_behavior() -> None:
    conservative = _extract(ExtractionMode.CONSERVATIVE)
    balanced = _extract(ExtractionMode.BALANCED)
    aggressive = _extract(ExtractionMode.AGGRESSIVE)

    assert conservative.problem.startswith("Agents repeat")
    assert conservative.solution == ""
    assert balanced.solution.startswith("Store candidate cards")
    assert aggressive.context
    assert aggressive.insight.startswith("Stable operational facts")
    assert conservative.confidence < balanced.confidence <= aggressive.confidence


def test_extraction_raises_for_empty_input() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        _extract(ExtractionMode.BALANCED, "   \n\t")


def test_extraction_degrades_for_too_short_text() -> None:
    card = _extract(ExtractionMode.BALANCED, "Remember SQLite.")
    assert card.title == "Remember SQLite"
    assert card.problem == ""
    assert card.context == "Remember SQLite."
    assert card.confidence < 0.4


def test_extraction_aggressive_fills_missing_fields_from_plain_text() -> None:
    card = _extract(
        ExtractionMode.AGGRESSIVE,
        "SQLite is the local index. Markdown remains the source of truth. Rebuild indexes from markdown.",
    )
    assert card.problem
    assert card.context
    assert card.insight
    assert card.solution
    assert 0.4 <= card.confidence <= 1.0

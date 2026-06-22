from __future__ import annotations

from pathlib import Path

from mindvault_mcp.config import load_config
from mindvault_mcp.services.llm_extraction import LLMExtractionService


def test_llm_disabled_returns_none() -> None:
    config = load_config(Path("missing-test-config.yaml"))
    service = LLMExtractionService(config)
    result = service.extract_via_llm("Some text")
    assert result is None

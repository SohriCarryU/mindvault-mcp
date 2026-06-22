from __future__ import annotations

from mindvault_mcp.config import AppConfig
from mindvault_mcp.schemas import IngestMetadata


class LLMExtractionService:
    """Optional LLM-backed extraction.

    The service is disabled by default. When disabled it returns ``None`` so
    callers fall back to the existing rule-based extraction without touching the
    network.
    """

    def __init__(self, config: AppConfig):
        self.config = config

    def extract_via_llm(
        self,
        text: str,
        metadata: IngestMetadata | None = None,
        api_key: str | None = None,
    ) -> dict | None:
        if not self.config.extraction.llm_enabled:
            return None
        return None

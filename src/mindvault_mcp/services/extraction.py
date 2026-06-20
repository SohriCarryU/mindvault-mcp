from __future__ import annotations

import re

from mindvault_mcp.config import AppConfig
from mindvault_mcp.enums import CardStatus, Library, VerificationStatus
from mindvault_mcp.models import Card
from mindvault_mcp.schemas import IngestMetadata


class RuleBasedExtractor:
    def __init__(self, config: AppConfig):
        self.config = config

    def extract(self, text: str, metadata: IngestMetadata, source_agent: str) -> Card:
        cleaned = " ".join(text.strip().split())
        if not cleaned:
            raise ValueError("ingest_memory requires non-empty text.")
        sentences = re.split(r"(?<=[.!?。！？])\s+", cleaned)
        title = self._title_from_text(sentences[0])
        mode = self.config.extraction.mode
        problem = cleaned if mode == "conservative" else sentences[0]
        context = cleaned
        insight = self._limited_sentence(sentences, index=1)
        solution = self._limited_sentence(sentences, index=2)
        library = metadata.library or self.config.defaults.ingest_library
        status = CardStatus.CANDIDATE if library == Library.STAGING else CardStatus.ACTIVE
        return Card(
            title=title,
            problem=problem,
            context=context,
            insight=insight,
            solution=solution,
            tags=metadata.tags,
            domain=metadata.domain,
            confidence=metadata.confidence if metadata.confidence is not None else 0.5,
            status=status,
            source_agent=metadata.source_agent or source_agent,
            privacy_level=metadata.privacy_level
            if metadata.privacy_level is not None
            else self.config.defaults.privacy_level,
            verification_status=VerificationStatus.NO_VERIFICATION_NEEDED,
            valid_until=metadata.valid_until,
            library=library,
        )

    def _title_from_text(self, text: str) -> str:
        title = text.strip().rstrip(".!?。！？")
        if len(title) > 80:
            title = title[:77].rstrip() + "..."
        return title or "Untitled memory"

    def _limited_sentence(self, sentences: list[str], index: int) -> str:
        if len(sentences) <= index:
            return ""
        return sentences[index][:500]


class LLMExtractorPlaceholder:
    def extract(self, text: str, metadata: IngestMetadata, source_agent: str) -> Card:
        raise NotImplementedError("LLM extraction is intentionally not implemented in phase 1.")

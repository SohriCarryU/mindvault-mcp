from __future__ import annotations

from abc import ABC, abstractmethod
import re

from mindvault_mcp.config import AppConfig
from mindvault_mcp.enums import CardStatus, ExtractionMode, Library, VerificationStatus
from mindvault_mcp.models import Card
from mindvault_mcp.schemas import IngestMetadata


class Extractor(ABC):
    @abstractmethod
    def extract(self, text: str, metadata: IngestMetadata, source_agent: str) -> Card:
        raise NotImplementedError


class RuleBasedExtractor(Extractor):
    FIELD_LABELS = {
        "problem": "problem",
        "issue": "problem",
        "pain": "problem",
        "context": "context",
        "background": "context",
        "insight": "insight",
        "lesson": "insight",
        "solution": "solution",
        "fix": "solution",
        "recommendation": "solution",
        "tags": "tags",
        "domain": "domain",
        "title": "title",
    }

    def __init__(self, config: AppConfig):
        self.config = config

    def extract(self, text: str, metadata: IngestMetadata, source_agent: str) -> Card:
        cleaned = self._clean(text)
        if not cleaned:
            raise ValueError("ingest_memory requires non-empty text.")

        labelled = self._extract_labelled_fields(text)
        sentences = self._sentences(cleaned)
        mode = self.config.extraction.mode

        title = labelled.get("title") or self._title_from_text(labelled.get("problem") or sentences[0])
        problem = labelled.get("problem", "")
        context = labelled.get("context", "")
        insight = labelled.get("insight", "")
        solution = labelled.get("solution", "")

        if mode == ExtractionMode.BALANCED:
            context = context or cleaned
            problem = problem or self._sentence_if_enough(sentences, 0)
            insight = insight or self._sentence_if_enough(sentences, 1)
        elif mode == ExtractionMode.AGGRESSIVE:
            context = context or cleaned
            problem = problem or self._sentence_or_empty(sentences, 0)
            insight = insight or self._sentence_or_empty(sentences, 1)
            solution = solution or self._sentence_or_empty(sentences, 2) or insight or problem
        else:
            context = context or self._conservative_context(cleaned, sentences)
            solution = ""

        tags = metadata.tags or self._extract_tags(labelled)
        domain = metadata.domain if metadata.domain != "general" else labelled.get("domain", "general")
        confidence = metadata.confidence if metadata.confidence is not None else self._confidence(
            problem=problem,
            context=context,
            insight=insight,
            solution=solution,
            labelled_hits=self._labelled_strength(labelled),
            mode=mode,
            text=cleaned,
        )
        library = metadata.library or self.config.defaults.ingest_library
        status = CardStatus.CANDIDATE if library == Library.STAGING else CardStatus.ACTIVE

        return Card(
            title=title,
            problem=problem,
            context=context,
            insight=insight,
            solution=solution,
            tags=tags,
            domain=domain,
            confidence=confidence,
            status=status,
            source_agent=metadata.source_agent or source_agent,
            privacy_level=metadata.privacy_level
            if metadata.privacy_level is not None
            else self.config.defaults.privacy_level,
            verification_status=VerificationStatus.NO_VERIFICATION_NEEDED,
            valid_until=metadata.valid_until,
            library=library,
        )

    def _clean(self, text: str) -> str:
        return " ".join(text.strip().split())

    def _extract_labelled_fields(self, text: str) -> dict[str, str]:
        fields: dict[str, str] = {}
        current: str | None = None
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            match = re.match(r"^([A-Za-z][A-Za-z _-]{1,30})\s*:\s*(.*)$", line)
            if match:
                label = match.group(1).strip().lower().replace(" ", "_").replace("-", "_")
                current = self.FIELD_LABELS.get(label)
                if current:
                    fields[current] = self._append(fields.get(current, ""), match.group(2).strip())
                continue
            if current in {"problem", "context", "insight", "solution"}:
                fields[current] = self._append(fields.get(current, ""), line)
        return {key: value for key, value in fields.items() if value}

    def _extract_tags(self, labelled: dict[str, str]) -> list[str]:
        raw = labelled.get("tags", "")
        if not raw:
            return []
        return [part.strip().lower() for part in re.split(r"[,;#]", raw) if part.strip()]

    def _sentences(self, text: str) -> list[str]:
        return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]

    def _title_from_text(self, text: str) -> str:
        title = text.strip().rstrip(".!?")
        if len(title) > 80:
            title = title[:77].rstrip() + "..."
        return title or "Untitled memory"

    def _sentence_if_enough(self, sentences: list[str], index: int) -> str:
        value = self._sentence_or_empty(sentences, index)
        if len(value.split()) < 4:
            return ""
        return value

    def _sentence_or_empty(self, sentences: list[str], index: int) -> str:
        if len(sentences) <= index:
            return ""
        return sentences[index][:500]

    def _conservative_context(self, text: str, sentences: list[str]) -> str:
        if len(sentences) >= 2 or len(text.split()) >= 12:
            return text
        return text

    def _confidence(
        self,
        problem: str,
        context: str,
        insight: str,
        solution: str,
        labelled_hits: int,
        mode: ExtractionMode,
        text: str,
    ) -> float:
        fields = [problem, context, insight, solution]
        filled_ratio = sum(1 for field in fields if field) / len(fields)
        score = 0.15 + filled_ratio * 0.45 + min(labelled_hits, 4) * 0.08
        if len(text.split()) < 5:
            score -= 0.25
        if mode == ExtractionMode.CONSERVATIVE:
            score -= 0.08
        elif mode == ExtractionMode.AGGRESSIVE:
            score += 0.05
        return max(0.0, min(1.0, round(score, 2)))

    def _labelled_strength(self, labelled: dict[str, str]) -> int:
        return sum(1 for key in ("problem", "context", "insight", "solution") if labelled.get(key))

    def _append(self, existing: str, value: str) -> str:
        if not value:
            return existing
        if not existing:
            return value
        return f"{existing} {value}"


class LLMExtractorPlaceholder(Extractor):
    def extract(self, text: str, metadata: IngestMetadata, source_agent: str) -> Card:
        raise NotImplementedError("LLM extraction is intentionally not implemented in phase 2.")

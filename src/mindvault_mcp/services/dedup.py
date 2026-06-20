from __future__ import annotations

import re
from typing import TYPE_CHECKING

from mindvault_mcp.config import AppConfig
from mindvault_mcp.enums import Library
from mindvault_mcp.models import Card

if TYPE_CHECKING:
    from mindvault_mcp.storage.repository import CardRepository


class DuplicateDetector:
    def __init__(self, config: AppConfig, repository: "CardRepository"):
        self.threshold = config.dedup.similarity_threshold
        self.repository = repository

    def find_possible_duplicate(self, card: Card) -> str | None:
        candidates = self.repository.search(
            tags=card.tags or None,
            domain=card.domain,
            library=Library.STAGING,
            limit=100,
        )
        best_card_id: str | None = None
        best_score = 0.0
        for existing in candidates:
            if existing.card_id == card.card_id:
                continue
            score = self.similarity(card, existing)
            if score > best_score:
                best_score = score
                best_card_id = existing.card_id
        if best_score >= self.threshold:
            return best_card_id
        return None

    def similarity(self, left: Card, right: Card) -> float:
        left_tokens = self._tokens(left)
        right_tokens = self._tokens(right)
        if not left_tokens or not right_tokens:
            return 0.0
        return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)

    def _tokens(self, card: Card) -> set[str]:
        text = " ".join([card.title, card.domain, " ".join(card.tags)])
        return {token for token in re.split(r"[^a-z0-9]+", text.lower()) if token}

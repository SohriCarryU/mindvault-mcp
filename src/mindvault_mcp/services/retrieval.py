from __future__ import annotations

import hashlib
import math
import os
from typing import TYPE_CHECKING

from embedding_provider import create_provider

from mindvault_mcp.config import AppConfig
from mindvault_mcp.models import Card

if TYPE_CHECKING:
    from mindvault_mcp.storage import CardRepository


class EmbeddingProviderUnavailable(RuntimeError):
    pass


class EmbeddingService:
    def __init__(self, config: AppConfig):
        self.config = config

    def provider_type(self) -> str:
        return os.getenv("EMBEDDING_PROVIDER", str(self.config.embedding.provider))

    def embed_query(self, query: str | None) -> list[float]:
        if not query:
            return []
        provider = create_provider(self.provider_type())
        return provider.embed_text(query)

    def is_usable_vector(self, vector: list[float]) -> bool:
        return bool(vector) and any(abs(value) > 0 for value in vector)

    def text_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def cosine_similarity(self, a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        norm_a = math.sqrt(sum(value * value for value in a))
        norm_b = math.sqrt(sum(value * value for value in b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        dot = sum(left * right for left, right in zip(a, b))
        return dot / (norm_a * norm_b)

    def ensure_card_vector(self, repository: CardRepository, card: Card) -> list[float]:
        provider_type = self.provider_type()
        if provider_type == "none":
            return []
        searchable_text = card.searchable_text()
        searchable_text_hash = self.text_hash(searchable_text)
        cached = repository.get_card_embedding(card.card_id, provider_type)
        if cached and cached["searchable_text_hash"] == searchable_text_hash:
            cached_vector = cached["vector"]
            if self.is_usable_vector(cached_vector):
                return cached_vector
        provider = create_provider(provider_type)
        vector = provider.embed_text(searchable_text)
        if not self.is_usable_vector(vector):
            return []
        repository.upsert_card_embedding(
            card_id=card.card_id,
            provider=provider_type,
            vector=vector,
            searchable_text_hash=searchable_text_hash,
            updated_at=card.updated_at.isoformat(),
        )
        return vector

    def rank_cards(
        self,
        repository: CardRepository,
        query_vector: list[float],
        cards: list[Card],
    ) -> list[Card]:
        if not self.is_usable_vector(query_vector):
            return []
        scored: list[tuple[float, Card]] = []
        for card in cards:
            card_vector = self.ensure_card_vector(repository, card)
            score = self.cosine_similarity(query_vector, card_vector)
            if score > 0:
                scored.append((score, card))
        scored.sort(
            key=lambda item: (
                -item[0],
                -item[1].confidence,
                -item[1].updated_at.timestamp(),
                item[1].card_id,
            )
        )
        return [card for _, card in scored]

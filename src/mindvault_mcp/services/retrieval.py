from __future__ import annotations

import os

from embedding_provider import create_provider

from mindvault_mcp.config import AppConfig


class EmbeddingProviderUnavailable(RuntimeError):
    pass


class EmbeddingService:
    def __init__(self, config: AppConfig):
        self.config = config

    def embed_query(self, query: str | None) -> list[float]:
        if not query:
            return []
        provider_type = os.getenv("EMBEDDING_PROVIDER", str(self.config.embedding.provider))
        provider = create_provider(provider_type)
        return provider.embed_text(query)

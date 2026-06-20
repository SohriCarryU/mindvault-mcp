from __future__ import annotations

from mindvault_mcp.config import AppConfig
from mindvault_mcp.enums import EmbeddingProvider


class EmbeddingProviderUnavailable(RuntimeError):
    pass


class EmbeddingService:
    def __init__(self, config: AppConfig):
        self.provider = config.embedding.provider

    def ensure_available(self) -> None:
        if self.provider in {EmbeddingProvider.LOCAL, EmbeddingProvider.API}:
            raise EmbeddingProviderUnavailable(
                f"Embedding provider '{self.provider}' is configured but not implemented in phase 1."
            )

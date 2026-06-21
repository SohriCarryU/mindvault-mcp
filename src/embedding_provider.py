from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Optional


class EmbeddingProvider(ABC):
    """Base class for embedding providers."""

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text."""

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""


class NoneProvider(EmbeddingProvider):
    """No-op provider. Search falls back to keyword/rule-based behavior."""

    def embed_text(self, text: str) -> list[float]:
        return []

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[] for _ in texts]


class LocalProvider(EmbeddingProvider):
    """Local embedding model interface placeholder."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name

    def embed_text(self, text: str) -> list[float]:
        return [0.0] * 384

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 384 for _ in texts]


class APIProvider(EmbeddingProvider):
    """External API embedding interface placeholder."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or os.getenv("EMBEDDING_API_KEY")
        self.base_url = base_url or os.getenv("EMBEDDING_API_URL", "https://api.openai.com/v1")

    def embed_text(self, text: str) -> list[float]:
        return [0.0] * 1536

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 1536 for _ in texts]


def create_provider(provider_type: str = "none") -> EmbeddingProvider:
    """Create an embedding provider by type."""
    normalized_provider_type = provider_type.lower()
    if normalized_provider_type == "none":
        return NoneProvider()
    if normalized_provider_type == "local":
        return LocalProvider()
    if normalized_provider_type == "api":
        return APIProvider()
    raise ValueError(f"Unknown provider type: {provider_type}")

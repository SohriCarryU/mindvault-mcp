from __future__ import annotations

import json
import os
import urllib.request
from abc import ABC, abstractmethod
from typing import Optional

SentenceTransformer = None

DEFAULT_LOCAL_MODEL_PATH = "sentence-transformers/all-MiniLM-L6-v2"


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
    """Local sentence-transformers embedding provider."""

    def __init__(self, model_name: str = DEFAULT_LOCAL_MODEL_PATH):
        self.model_name = model_name or DEFAULT_LOCAL_MODEL_PATH
        self._model = None

    def embed_text(self, text: str) -> list[float]:
        vectors = self.embed_batch([text])
        if not vectors:
            return []
        return vectors[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            model = self._load_model()
            encoded = model.encode(texts)
        except Exception:
            return [[] for _ in texts]
        return self._normalize_batch(encoded, len(texts))

    def _load_model(self):
        if self._model is not None:
            return self._model

        transformer_cls = SentenceTransformer
        if transformer_cls is None:
            try:
                from sentence_transformers import SentenceTransformer as transformer_cls
            except Exception as exc:
                raise RuntimeError("sentence-transformers is not available") from exc
        self._model = transformer_cls(self.model_name)
        return self._model

    def _normalize_batch(self, encoded: object, expected_count: int) -> list[list[float]]:
        if hasattr(encoded, "tolist"):
            encoded = encoded.tolist()
        if expected_count == 1 and self._is_number_list(encoded):
            return [self._to_float_vector(encoded)]
        if not isinstance(encoded, list) or len(encoded) != expected_count:
            return [[] for _ in range(expected_count)]
        vectors: list[list[float]] = []
        for item in encoded:
            if hasattr(item, "tolist"):
                item = item.tolist()
            if not self._is_number_list(item):
                return [[] for _ in range(expected_count)]
            vectors.append(self._to_float_vector(item))
        return vectors

    def _is_number_list(self, value: object) -> bool:
        return isinstance(value, list) and all(isinstance(item, (int, float)) for item in value)

    def _to_float_vector(self, vector: object) -> list[float]:
        if not isinstance(vector, list):
            return []
        return [float(value) for value in vector]


class APIProvider(EmbeddingProvider):
    """OpenAI-compatible API embedding provider.

    The provider is opt-in: it returns an empty vector and does not call the
    network unless api_key, base_url, and model are all configured.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: str = "",
        timeout_seconds: float = 10.0,
    ):
        self.api_key = api_key or os.getenv("EMBEDDING_API_KEY")
        self.base_url = base_url or ""
        self.model = model
        self.timeout_seconds = timeout_seconds

    def embed_text(self, text: str) -> list[float]:
        vectors = self.embed_batch([text])
        if not vectors:
            return []
        return vectors[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not self._has_config():
            return [[] for _ in texts]

        # Many OpenAI-compatible gateways only accept a string "input" and reset the
        # connection on an array. Send a string for single-text requests; keep the
        # array form for true batches (supported by the official API).
        input_value = texts[0] if len(texts) == 1 else texts
        payload = json.dumps(
            {
                "model": self.model,
                "input": input_value,
                "encoding_format": "float",
            }
        ).encode("utf-8")
        user_agent = os.getenv("HTTP_USER_AGENT", "mindvault-mcp")
        request = urllib.request.Request(
            self._embedding_endpoint(),
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": user_agent,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = response.read()
        except Exception:
            return [[] for _ in texts]

        try:
            response_json = json.loads(body)
        except (json.JSONDecodeError, TypeError):
            return [[] for _ in texts]

        return self._parse_embedding_response(response_json, len(texts))

    def _has_config(self) -> bool:
        return bool(self.api_key and self.base_url and self.model)

    def _embedding_endpoint(self) -> str:
        base_url = self.base_url.rstrip("/")
        if base_url.endswith("/embeddings"):
            return base_url
        return base_url + "/embeddings"

    def _parse_embedding_response(self, response_json: object, expected_count: int) -> list[list[float]]:
        try:
            data = response_json["data"]  # type: ignore[index]
        except (KeyError, TypeError):
            return [[] for _ in range(expected_count)]
        if not isinstance(data, list) or len(data) < expected_count:
            return [[] for _ in range(expected_count)]
        vectors: list[list[float]] = []
        for index in range(expected_count):
            item = data[index]
            if not isinstance(item, dict):
                return [[] for _ in range(expected_count)]
            embedding = item.get("embedding")
            if not isinstance(embedding, list):
                return [[] for _ in range(expected_count)]
            vector: list[float] = []
            for value in embedding:
                if not isinstance(value, (int, float)):
                    return [[] for _ in range(expected_count)]
                vector.append(float(value))
            vectors.append(vector)
        return vectors


def create_provider(provider_type: str = "none", config: object | None = None) -> EmbeddingProvider:
    """Create an embedding provider by type."""
    normalized_provider_type = provider_type.lower()
    if normalized_provider_type == "none":
        return NoneProvider()
    if normalized_provider_type == "local":
        embedding_config = getattr(config, "embedding", None)
        return LocalProvider(
            model_name=getattr(embedding_config, "local_model_path", DEFAULT_LOCAL_MODEL_PATH)
        )
    if normalized_provider_type == "api":
        embedding_config = getattr(config, "embedding", None)
        return APIProvider(
            api_key=getattr(embedding_config, "api_key", ""),
            base_url=getattr(embedding_config, "api_base_url", ""),
            model=getattr(embedding_config, "api_model", ""),
            timeout_seconds=getattr(embedding_config, "api_timeout", 10.0),
        )
    raise ValueError(f"Unknown provider type: {provider_type}")

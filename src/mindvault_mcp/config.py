from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from .enums import EmbeddingProvider, ExtractionMode, Library
from .models import Agent


class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000
    transport: str = "sse"


class StorageConfig(BaseModel):
    primary_path: Path = Path("data/primary")
    staging_path: Path = Path("data/staging")
    sqlite_path: Path = Path("data/mindvault.sqlite")


class AuthAgentConfig(Agent):
    token: str


class AuthConfig(BaseModel):
    agents: list[AuthAgentConfig] = Field(default_factory=list)


class ExtractionConfig(BaseModel):
    mode: ExtractionMode = ExtractionMode.CONSERVATIVE
    llm_enabled: bool = False
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_timeout_seconds: float = Field(default=15.0, gt=0.0)


class EmbeddingConfig(BaseModel):
    provider: EmbeddingProvider = EmbeddingProvider.NONE


class DefaultsConfig(BaseModel):
    ingest_library: Library = Library.STAGING
    privacy_level: int = 0


class VerificationConfig(BaseModel):
    backend_mode: str = "none"
    external_validation_enabled: bool = False
    external_validation_timeout_seconds: float = Field(default=5.0, gt=0.0)


class DedupConfig(BaseModel):
    similarity_threshold: float = Field(default=0.72, ge=0.0, le=1.0)


class LoggingConfig(BaseModel):
    level: str = "INFO"


class AppConfig(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)
    verification: VerificationConfig = Field(default_factory=VerificationConfig)
    dedup: DedupConfig = Field(default_factory=DedupConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


def _resolve_paths(config: AppConfig, base_dir: Path) -> AppConfig:
    storage = config.storage
    for attr in ("primary_path", "staging_path", "sqlite_path"):
        value = getattr(storage, attr)
        if not value.is_absolute():
            setattr(storage, attr, (base_dir / value).resolve())
    return config


def _env_bool(key: str, fallback: bool) -> bool:
    """Parse environment variable as bool, fallback on parse error."""
    value = os.getenv(key)
    if value is None:
        return fallback
    normalized = value.strip().lower()
    if normalized in ("true", "1", "yes"):
        return True
    if normalized in ("false", "0", "no"):
        return False
    return fallback


def _env_float(key: str, fallback: float) -> float:
    """Parse environment variable as float, fallback on parse error."""
    value = os.getenv(key)
    if value is None:
        return fallback
    try:
        return float(value)
    except (ValueError, TypeError):
        return fallback


def _apply_env_overrides(config: AppConfig) -> AppConfig:
    """Apply environment variable overrides to config after pydantic validation."""
    ext = config.extraction

    ext.llm_enabled = _env_bool("LLM_EXTRACTION_ENABLED", ext.llm_enabled)

    if "LLM_BASE_URL" in os.environ:
        ext.llm_base_url = os.environ["LLM_BASE_URL"]

    if "LLM_MODEL" in os.environ:
        ext.llm_model = os.environ["LLM_MODEL"]

    ext.llm_timeout_seconds = _env_float("LLM_TIMEOUT_SECONDS", ext.llm_timeout_seconds)

    return config


def load_config(path: str | Path | None = None) -> AppConfig:
    config_path = Path(path or os.getenv("MINDVAULT_CONFIG", "config.yaml"))
    raw: dict[str, Any] = {}
    if config_path.exists():
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    config = AppConfig.model_validate(raw)
    config = _resolve_paths(config, config_path.parent.resolve())
    config = _apply_env_overrides(config)
    return config

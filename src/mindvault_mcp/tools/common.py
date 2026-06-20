from __future__ import annotations

from dataclasses import dataclass

from mindvault_mcp.auth import AuthService
from mindvault_mcp.config import AppConfig
from mindvault_mcp.services import DuplicateDetector, EmbeddingService, RuleBasedExtractor, VerificationService
from mindvault_mcp.storage import CardRepository, MarkdownStore, SQLiteIndex


@dataclass
class ToolRuntime:
    config: AppConfig
    auth: AuthService
    repository: CardRepository
    extractor: RuleBasedExtractor
    dedup: DuplicateDetector
    embeddings: EmbeddingService
    verification: VerificationService


def build_runtime(config: AppConfig) -> ToolRuntime:
    markdown_store = MarkdownStore(config.storage.primary_path, config.storage.staging_path)
    sqlite_index = SQLiteIndex(config.storage.sqlite_path)
    repository = CardRepository(markdown_store, sqlite_index)
    return ToolRuntime(
        config=config,
        auth=AuthService(config),
        repository=repository,
        extractor=RuleBasedExtractor(config),
        dedup=DuplicateDetector(),
        embeddings=EmbeddingService(config),
        verification=VerificationService(config),
    )

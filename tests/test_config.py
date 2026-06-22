from __future__ import annotations

from pathlib import Path

from mindvault_mcp.config import load_config
from mindvault_mcp.enums import EmbeddingProvider, ExtractionMode, Library


def test_load_config_resolves_paths(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        """
server:
  host: "0.0.0.0"
  port: 9000
storage:
  primary_path: "cards/primary"
  staging_path: "cards/staging"
  sqlite_path: "cards/index.sqlite"
auth:
  agents:
    - token: "t"
      agent_id: "a"
      trust_level: 9
      allowed_libraries: ["primary", "staging"]
extraction:
  mode: "balanced"
embedding:
  provider: "none"
defaults:
  ingest_library: "staging"
  privacy_level: 2
verification:
  backend_mode: "none"
  external_validation_enabled: true
  external_validation_timeout_seconds: 2.5
""",
        encoding="utf-8",
    )
    config = load_config(config_file)
    assert config.server.port == 9000
    assert config.storage.primary_path == (tmp_path / "cards/primary").resolve()
    assert config.extraction.mode == ExtractionMode.BALANCED
    assert config.embedding.provider == EmbeddingProvider.NONE
    assert config.defaults.ingest_library == Library.STAGING
    assert config.verification.external_validation_enabled is True
    assert config.verification.external_validation_timeout_seconds == 2.5
    assert config.auth.agents[0].agent_id == "a"


def test_external_validation_defaults_disabled() -> None:
    config = load_config(Path("missing-test-config.yaml"))

    assert config.verification.external_validation_enabled is False
    assert config.verification.external_validation_timeout_seconds == 5.0

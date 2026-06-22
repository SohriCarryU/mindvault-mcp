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


def test_llm_extraction_defaults_disabled() -> None:
    config = load_config(Path("missing-test-config.yaml"))

    assert config.extraction.llm_enabled is False
    assert config.extraction.llm_provider == "openai"
    assert config.extraction.llm_model == "gpt-4o-mini"
    assert config.extraction.llm_base_url == "https://api.openai.com/v1"
    assert config.extraction.llm_timeout_seconds == 15.0


def test_llm_env_enabled_overrides_config_true(tmp_path: Path, monkeypatch) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text("extraction:\n  llm_enabled: false\n", encoding="utf-8")
    monkeypatch.setenv("LLM_EXTRACTION_ENABLED", "true")

    config = load_config(config_file)

    assert config.extraction.llm_enabled is True


def test_llm_env_enabled_overrides_config_false(tmp_path: Path, monkeypatch) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text("extraction:\n  llm_enabled: true\n", encoding="utf-8")
    monkeypatch.setenv("LLM_EXTRACTION_ENABLED", "false")

    config = load_config(config_file)

    assert config.extraction.llm_enabled is False


def test_llm_env_invalid_enabled_keeps_config(tmp_path: Path, monkeypatch) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text("extraction:\n  llm_enabled: true\n", encoding="utf-8")
    monkeypatch.setenv("LLM_EXTRACTION_ENABLED", "maybe")

    config = load_config(config_file)

    assert config.extraction.llm_enabled is True


def test_llm_env_base_url_and_model_override_config(tmp_path: Path, monkeypatch) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "extraction:\n  llm_base_url: https://config.example/v1\n  llm_model: config-model\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LLM_BASE_URL", "https://env.example/v1")
    monkeypatch.setenv("LLM_MODEL", "env-model")

    config = load_config(config_file)

    assert config.extraction.llm_base_url == "https://env.example/v1"
    assert config.extraction.llm_model == "env-model"


def test_llm_env_timeout_overrides_config(tmp_path: Path, monkeypatch) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text("extraction:\n  llm_timeout_seconds: 4.0\n", encoding="utf-8")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "8.5")

    config = load_config(config_file)

    assert config.extraction.llm_timeout_seconds == 8.5


def test_llm_env_invalid_timeout_keeps_config(tmp_path: Path, monkeypatch) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text("extraction:\n  llm_timeout_seconds: 4.0\n", encoding="utf-8")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "not-a-number")

    config = load_config(config_file)

    assert config.extraction.llm_timeout_seconds == 4.0

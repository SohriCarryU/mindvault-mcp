from __future__ import annotations

from pathlib import Path

import pytest

from mindvault_mcp.config import AppConfig, AuthAgentConfig, AuthConfig, DefaultsConfig, StorageConfig
from mindvault_mcp.enums import Library
from mindvault_mcp.tools import build_runtime


@pytest.fixture
def app_config(tmp_path: Path) -> AppConfig:
    return AppConfig(
        storage=StorageConfig(
            primary_path=tmp_path / "primary",
            staging_path=tmp_path / "staging",
            sqlite_path=tmp_path / "mindvault.sqlite",
        ),
        auth=AuthConfig(
            agents=[
                AuthAgentConfig(
                    token="admin-token",
                    agent_id="admin",
                    trust_level=10,
                    allowed_libraries=[Library.PRIMARY, Library.STAGING],
                ),
                AuthAgentConfig(
                    token="trusted-token",
                    agent_id="trusted",
                    trust_level=5,
                    allowed_libraries=[Library.STAGING],
                ),
            ]
        ),
        defaults=DefaultsConfig(ingest_library=Library.STAGING, privacy_level=3),
    )


@pytest.fixture
def runtime(app_config: AppConfig):
    return build_runtime(app_config)

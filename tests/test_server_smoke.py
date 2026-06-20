from __future__ import annotations

import asyncio
from pathlib import Path

from fastmcp import FastMCP

from mindvault_mcp.server import create_app


def test_create_app_registers_tools_and_sse_routes(tmp_path: Path) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        f"""
server:
  host: "127.0.0.1"
  port: 0
  transport: "sse"
storage:
  primary_path: "{(tmp_path / "primary").as_posix()}"
  staging_path: "{(tmp_path / "staging").as_posix()}"
  sqlite_path: "{(tmp_path / "mindvault.sqlite").as_posix()}"
auth:
  agents:
    - token: "admin-token"
      agent_id: "admin"
      trust_level: 10
      allowed_libraries: ["primary", "staging"]
extraction:
  mode: "balanced"
embedding:
  provider: "none"
defaults:
  ingest_library: "staging"
  privacy_level: 1
verification:
  backend_mode: "none"
dedup:
  similarity_threshold: 0.72
logging:
  level: "INFO"
""",
        encoding="utf-8",
    )

    app = create_app(str(config_file))

    assert isinstance(app, FastMCP)
    assert {tool.name for tool in asyncio.run(app.list_tools())} == {
        "ingest_memory",
        "search_cards",
        "list_candidates",
        "approve_card",
        "reject_card",
        "get_card",
        "update_card",
        "queue_verification",
    }

    sse_app = app.http_app(transport="sse")
    route_paths = {route.path for route in sse_app.routes}
    assert "/sse" in route_paths
    assert "/messages" in route_paths

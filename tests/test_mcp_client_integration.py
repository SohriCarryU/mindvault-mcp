from __future__ import annotations

import asyncio
from pathlib import Path

from fastmcp import Client

from mindvault_mcp.server import create_app


EXPECTED_TOOLS = {
    "ingest_memory",
    "search_cards",
    "list_candidates",
    "approve_card",
    "reject_card",
    "get_card",
    "update_card",
    "queue_verification",
}


def test_fastmcp_client_can_call_tools_with_permissions(tmp_path: Path) -> None:
    asyncio.run(_run_client_flow(tmp_path))


async def _run_client_flow(tmp_path: Path) -> None:
    config_file = _write_config(tmp_path)
    app = create_app(str(config_file))

    async with Client(app) as client:
        tools = await client.list_tools()
        assert {tool.name for tool in tools} == EXPECTED_TOOLS

        ingest = await client.call_tool(
            "ingest_memory",
            {
                "token": "high-token",
                "text": "Problem: MCP clients need durable memory. Solution: Store reviewed cards.",
                "metadata": {
                    "tags": ["mcp", "integration"],
                    "domain": "client-test",
                },
            },
        )
        assert ingest.data is not None
        card = ingest.data["card"]
        assert card["library"] == "staging"
        assert card["status"] == "candidate"

        candidates = await client.call_tool(
            "list_candidates",
            {
                "token": "high-token",
                "domain": "client-test",
                "tags": ["integration"],
            },
        )
        assert candidates.data is not None
        assert [item["card_id"] for item in candidates.data["candidates"]] == [card["card_id"]]

        denied = await client.call_tool(
            "approve_card",
            {
                "token": "low-token",
                "card_id": card["card_id"],
            },
            raise_on_error=False,
        )
        assert denied.is_error
        assert "Approving cards requires trust level >= 8" in denied.content[0].text


def _write_config(tmp_path: Path) -> Path:
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
    - token: "high-token"
      agent_id: "high-agent"
      trust_level: 10
      allowed_libraries: ["primary", "staging"]
    - token: "low-token"
      agent_id: "low-agent"
      trust_level: 5
      allowed_libraries: ["staging"]
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
    return config_file

#!/usr/bin/env python
from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any

from fastmcp import Client


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


async def run(url: str, token: str) -> None:
    async with Client(url) as client:
        tools = await client.list_tools()
        tool_names = {tool.name for tool in tools}
        missing = EXPECTED_TOOLS - tool_names
        if missing:
            raise AssertionError(f"Missing MCP tools: {sorted(missing)}")

        result = await client.call_tool(
            "list_candidates",
            {
                "token": token,
                "limit": 1,
                "offset": 0,
            },
        )
        data: dict[str, Any] | None = result.data
        if not data or data.get("ok") is not True:
            raise AssertionError(f"list_candidates returned unexpected data: {data!r}")

        print(f"Connected to {url}")
        print(f"Tools: {', '.join(sorted(tool_names))}")
        print("list_candidates: ok")


def main() -> int:
    parser = argparse.ArgumentParser(description="Manually verify the mindvault-mcp SSE endpoint.")
    parser.add_argument("--url", default="http://127.0.0.1:8000/sse", help="MCP SSE endpoint URL.")
    parser.add_argument("--token", default="dev-trusted-token", help="Agent token passed as a tool argument.")
    args = parser.parse_args()

    try:
        asyncio.run(run(args.url, args.token))
    except Exception as exc:
        print(f"SSE smoke check failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

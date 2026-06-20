from __future__ import annotations

import logging
import os
from typing import Any

from .config import load_config
from .schemas import IngestMetadata, UpdateCardFields
from .tools import (
    approve_card as approve_card_impl,
    build_runtime,
    get_card as get_card_impl,
    ingest_memory as ingest_memory_impl,
    list_candidates as list_candidates_impl,
    queue_verification as queue_verification_impl,
    reject_card as reject_card_impl,
    search_cards as search_cards_impl,
    update_card as update_card_impl,
)


def create_app(config_path: str | None = None) -> Any:
    config = load_config(config_path)
    logging.basicConfig(level=getattr(logging, config.logging.level.upper(), logging.INFO))
    runtime = build_runtime(config)

    try:
        from fastmcp import FastMCP
    except ImportError as exc:
        raise RuntimeError("fastmcp is required to run the MCP server. Install with `pip install -e .`.") from exc

    mcp = FastMCP("mindvault-mcp")

    @mcp.tool()
    def ingest_memory(token: str, text: str, metadata: dict | None = None) -> dict:
        """Create a candidate knowledge card from raw memory text."""
        response = ingest_memory_impl(runtime, token, text, IngestMetadata.model_validate(metadata or {}))
        return response.model_dump(mode="json")

    @mcp.tool()
    def search_cards(
        token: str,
        query: str | None = None,
        tags: list[str] | None = None,
        domain: str | None = None,
        library: str | None = None,
        status: str | None = None,
        verification_status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict:
        """Search indexed cards with conservative keyword filters."""
        response = search_cards_impl(
            runtime,
            token,
            query=query,
            tags=tags,
            domain=domain,
            library=library,
            status=status,
            verification_status=verification_status,
            limit=limit,
            offset=offset,
        )
        return response.model_dump(mode="json")

    @mcp.tool()
    def list_candidates(
        token: str,
        domain: str | None = None,
        tags: list[str] | None = None,
        min_confidence: float | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> dict:
        """List staging candidate cards."""
        response = list_candidates_impl(
            runtime,
            token,
            domain=domain,
            tags=tags,
            min_confidence=min_confidence,
            limit=limit,
            offset=offset,
        )
        return response.model_dump(mode="json")

    @mcp.tool()
    def approve_card(token: str, card_id: str) -> dict:
        """Promote a staging candidate card into primary."""
        response = approve_card_impl(runtime, token, card_id)
        return response.model_dump(mode="json")

    @mcp.tool()
    def reject_card(token: str, card_id: str, reason: str) -> dict:
        """Mark a staging candidate as rejected while retaining its record."""
        response = reject_card_impl(runtime, token, card_id, reason)
        return response.model_dump(mode="json")

    @mcp.tool()
    def get_card(token: str, card_id: str) -> dict:
        """Return one card after library and privacy checks."""
        response = get_card_impl(runtime, token, card_id)
        return response.model_dump(mode="json")

    @mcp.tool()
    def update_card(token: str, card_id: str, fields: dict) -> dict:
        """Update editable card fields and refresh Markdown plus SQLite index."""
        response = update_card_impl(runtime, token, card_id, UpdateCardFields.model_validate(fields))
        return response.model_dump(mode="json")

    @mcp.tool()
    def queue_verification(token: str, card_id: str) -> dict:
        """Mark a card as pending verification without calling external services."""
        response = queue_verification_impl(runtime, token, card_id)
        return response.model_dump(mode="json")

    return mcp


def main() -> None:
    config_path = os.getenv("MINDVAULT_CONFIG", "config.yaml")
    config = load_config(config_path)
    mcp = create_app(config_path)
    mcp.run(transport=config.server.transport, host=config.server.host, port=config.server.port)


if __name__ == "__main__":
    main()

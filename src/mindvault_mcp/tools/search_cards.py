from __future__ import annotations

from collections import defaultdict

from mindvault_mcp.enums import Library
from mindvault_mcp.schemas import SearchResponse

from .common import ToolRuntime


def search_cards(
    runtime: ToolRuntime,
    token: str,
    query: str | None = None,
    tags: list[str] | None = None,
    domain: str | None = None,
    library: str | None = None,
    status: str | None = None,
    verification_status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> SearchResponse:
    ctx = runtime.auth.authenticate(token)
    scopes = [Library(library)] if library else [Library.PRIMARY, Library.STAGING]
    results: dict[str, list] = defaultdict(list)
    for scope in scopes:
        try:
            runtime.auth.require_library_access(ctx, scope)
        except PermissionError:
            continue
        cards = runtime.repository.search(
            query=query,
            tags=tags,
            domain=domain,
            library=scope,
            status=status,
            verification_status=verification_status,
            limit=limit,
            offset=offset,
        )
        for card in cards:
            try:
                runtime.auth.require_read_card(ctx, card)
            except PermissionError:
                continue
            results[str(scope)].append(card)
    return SearchResponse(ok=True, message="Search completed without vector embeddings.", results=dict(results))

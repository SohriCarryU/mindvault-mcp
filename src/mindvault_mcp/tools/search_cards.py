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
    query_vector = runtime.embeddings.embed_query(query)
    scopes = [Library(library)] if library else [Library.PRIMARY, Library.STAGING]
    results: dict[str, list] = defaultdict(list)
    used_semantic_ranking = False
    for scope in scopes:
        try:
            runtime.auth.require_library_access(ctx, scope)
        except PermissionError:
            continue
        if query and runtime.embeddings.is_usable_vector(query_vector):
            candidate_limit = max(limit + offset, 100)
            candidates = runtime.repository.search(
                query=None,
                tags=tags,
                domain=domain,
                library=scope,
                status=status,
                verification_status=verification_status,
                limit=candidate_limit,
                offset=0,
            )
            readable_candidates = []
            for card in candidates:
                try:
                    runtime.auth.require_read_card(ctx, card)
                except PermissionError:
                    continue
                readable_candidates.append(card)
            ranked_cards = runtime.embeddings.rank_cards(runtime.repository, query_vector, readable_candidates)
            if ranked_cards:
                results[str(scope)].extend(ranked_cards[offset : offset + limit])
                used_semantic_ranking = True
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
    message = (
        "Search completed with semantic vector ranking."
        if used_semantic_ranking
        else "Search completed without vector embeddings."
    )
    return SearchResponse(ok=True, message=message, results=dict(results))

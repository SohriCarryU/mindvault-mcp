from __future__ import annotations

from mindvault_mcp.enums import CardStatus, Library
from mindvault_mcp.schemas import CandidateListResponse

from .common import ToolRuntime


def list_candidates(
    runtime: ToolRuntime,
    token: str,
    domain: str | None = None,
    tags: list[str] | None = None,
    min_confidence: float | None = None,
    limit: int = 20,
    offset: int = 0,
) -> CandidateListResponse:
    ctx = runtime.auth.authenticate(token)
    runtime.auth.require_library_access(ctx, Library.STAGING)
    cards = runtime.repository.search(
        domain=domain,
        tags=tags,
        library=Library.STAGING,
        status=CardStatus.CANDIDATE,
        limit=max(limit + offset, limit),
        offset=0,
    )
    visible = []
    for card in cards:
        try:
            runtime.auth.require_read_card(ctx, card)
            if min_confidence is not None and card.confidence < min_confidence:
                continue
            visible.append(card)
        except PermissionError:
            continue
    return CandidateListResponse(
        ok=True,
        message="Candidates listed.",
        candidates=visible[offset : offset + limit],
        limit=limit,
        offset=offset,
    )

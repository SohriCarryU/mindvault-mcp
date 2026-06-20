from __future__ import annotations

from mindvault_mcp.enums import CardStatus, Library
from mindvault_mcp.schemas import CandidateListResponse

from .common import ToolRuntime


def list_candidates(
    runtime: ToolRuntime,
    token: str,
    domain: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> CandidateListResponse:
    ctx = runtime.auth.authenticate(token)
    runtime.auth.require_library_access(ctx, Library.STAGING)
    cards = runtime.repository.search(
        domain=domain,
        library=Library.STAGING,
        status=CardStatus.CANDIDATE,
        limit=limit,
        offset=offset,
    )
    visible = []
    for card in cards:
        try:
            runtime.auth.require_read_card(ctx, card)
            visible.append(card)
        except PermissionError:
            continue
    return CandidateListResponse(ok=True, message="Candidates listed.", candidates=visible, limit=limit, offset=offset)

from __future__ import annotations

from mindvault_mcp.schemas import CardResponse

from .common import ToolRuntime


def reject_card(runtime: ToolRuntime, token: str, card_id: str, reason: str) -> CardResponse:
    ctx = runtime.auth.authenticate(token)
    card = runtime.repository.get(card_id)
    runtime.auth.require_write_library(ctx, card.library)
    runtime.auth.require_read_card(ctx, card)
    rejected = runtime.repository.reject(card_id, reason=reason)
    return CardResponse(ok=True, message="Candidate card rejected and retained in staging.", card=rejected)

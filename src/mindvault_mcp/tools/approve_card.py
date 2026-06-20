from __future__ import annotations

from mindvault_mcp.schemas import CardResponse

from .common import ToolRuntime


def approve_card(runtime: ToolRuntime, token: str, card_id: str) -> CardResponse:
    ctx = runtime.auth.authenticate(token)
    runtime.auth.require_approve(ctx)
    card = runtime.repository.get(card_id)
    runtime.auth.require_read_card(ctx, card)
    approved = runtime.repository.approve(card_id, source_agent=ctx.agent.agent_id)
    return CardResponse(ok=True, message="Card approved into primary.", card=approved)

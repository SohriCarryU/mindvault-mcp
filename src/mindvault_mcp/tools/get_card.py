from __future__ import annotations

from mindvault_mcp.schemas import CardResponse

from .common import ToolRuntime


def get_card(runtime: ToolRuntime, token: str, card_id: str) -> CardResponse:
    ctx = runtime.auth.authenticate(token)
    card = runtime.repository.get(card_id)
    runtime.auth.require_read_card(ctx, card)
    return CardResponse(ok=True, message="Card loaded.", card=card)

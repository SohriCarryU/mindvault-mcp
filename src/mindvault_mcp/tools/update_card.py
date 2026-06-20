from __future__ import annotations

from mindvault_mcp.schemas import CardResponse, UpdateCardFields

from .common import ToolRuntime


def update_card(
    runtime: ToolRuntime,
    token: str,
    card_id: str,
    fields: UpdateCardFields | dict,
) -> CardResponse:
    ctx = runtime.auth.authenticate(token)
    card = runtime.repository.get(card_id)
    runtime.auth.require_write_library(ctx, card.library)
    runtime.auth.require_read_card(ctx, card)
    patch = fields.patch_dict() if isinstance(fields, UpdateCardFields) else UpdateCardFields.model_validate(fields).patch_dict()
    updated = runtime.repository.update(card_id, patch)
    return CardResponse(ok=True, message="Card updated.", card=updated)

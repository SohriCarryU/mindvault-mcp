from __future__ import annotations

from pydantic import BaseModel

from mindvault_mcp.models import Card, VerificationQueueItem

from .common import ToolRuntime


class QueueVerificationResponse(BaseModel):
    ok: bool
    message: str = ""
    card: Card | None = None
    queue_item: VerificationQueueItem | None = None


def queue_verification(runtime: ToolRuntime, token: str, card_id: str, reason: str = "") -> QueueVerificationResponse:
    ctx = runtime.auth.authenticate(token)
    card = runtime.repository.get(card_id)
    runtime.auth.require_write_library(ctx, card.library)
    runtime.auth.require_read_card(ctx, card)
    item = runtime.verification.queue(card_id=card_id, queued_by=ctx.agent.agent_id, reason=reason)
    updated = runtime.repository.queue_verification(card_id, item=item)
    return QueueVerificationResponse(
        ok=True,
        message="Verification queued as a phase 2 placeholder; no external verification was run.",
        card=updated,
        queue_item=item,
    )

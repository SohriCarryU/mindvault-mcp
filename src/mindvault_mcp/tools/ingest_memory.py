from __future__ import annotations

from mindvault_mcp.schemas import CardResponse, IngestMetadata

from .common import ToolRuntime


def ingest_memory(runtime: ToolRuntime, token: str, text: str, metadata: IngestMetadata | dict | None = None) -> CardResponse:
    ctx = runtime.auth.authenticate(token)
    meta = metadata if isinstance(metadata, IngestMetadata) else IngestMetadata.model_validate(metadata or {})
    card = runtime.extractor.extract(text=text, metadata=meta, source_agent=ctx.agent.agent_id)
    runtime.auth.require_write_library(ctx, card.library)
    card.possible_duplicate_of = runtime.dedup.find_possible_duplicate(card)
    runtime.repository.save(card)
    return CardResponse(ok=True, message="Candidate card created.", card=card)

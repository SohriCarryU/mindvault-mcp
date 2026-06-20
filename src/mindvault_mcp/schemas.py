from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .enums import Library
from .models import Card


class ToolResponse(BaseModel):
    ok: bool
    message: str = ""


class CardResponse(ToolResponse):
    card: Card | None = None


class SearchResponse(ToolResponse):
    results: dict[str, list[Card]] = Field(default_factory=dict)


class CandidateListResponse(ToolResponse):
    candidates: list[Card] = Field(default_factory=list)
    limit: int
    offset: int


class IngestMetadata(BaseModel):
    tags: list[str] = Field(default_factory=list)
    domain: str = "general"
    source_agent: str | None = None
    privacy_level: int | None = None
    confidence: float | None = None
    valid_until: datetime | None = None
    library: Library | None = None


class UpdateCardFields(BaseModel):
    title: str | None = None
    problem: str | None = None
    context: str | None = None
    insight: str | None = None
    solution: str | None = None
    tags: list[str] | None = None
    domain: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    privacy_level: int | None = Field(default=None, ge=0)
    valid_until: datetime | None = None
    possible_duplicate_of: str | None = None

    def patch_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=True)

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .enums import CardStatus, Library, VerificationStatus


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_card_id() -> str:
    return f"card_{uuid4().hex}"


class Agent(BaseModel):
    agent_id: str
    trust_level: int = Field(ge=0)
    allowed_libraries: list[Library]


class Card(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    card_id: str = Field(default_factory=new_card_id)
    title: str
    problem: str = ""
    context: str = ""
    insight: str = ""
    solution: str = ""
    tags: list[str] = Field(default_factory=list)
    domain: str = "general"
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    status: CardStatus = CardStatus.CANDIDATE
    source_agent: str = "unknown"
    privacy_level: int = Field(default=0, ge=0)
    verification_status: VerificationStatus = VerificationStatus.NO_VERIFICATION_NEEDED
    valid_until: datetime | None = None
    possible_duplicate_of: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    library: Library = Library.STAGING

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            value = [part.strip() for part in value.split(",")]
        return sorted({str(tag).strip().lower() for tag in value if str(tag).strip()})

    def touch(self) -> None:
        self.updated_at = utc_now()

    def searchable_text(self) -> str:
        return "\n".join(
            [
                self.title,
                self.problem,
                self.context,
                self.insight,
                self.solution,
                self.domain,
                " ".join(self.tags),
            ]
        )


class VerificationQueueItem(BaseModel):
    card_id: str
    queued_by: str
    queued_at: datetime = Field(default_factory=utc_now)
    backend_mode: str = "none"
    reason: str = ""
    status: str = "pending"
    note: str = "Verification backend is not implemented in phase 2."

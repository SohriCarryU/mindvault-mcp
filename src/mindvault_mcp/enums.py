from enum import StrEnum


class Library(StrEnum):
    PRIMARY = "primary"
    STAGING = "staging"


class CardStatus(StrEnum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    ARCHIVED = "archived"
    REJECTED = "rejected"


class VerificationStatus(StrEnum):
    VERIFIED = "verified"
    NO_VERIFICATION_NEEDED = "no_verification_needed"
    PENDING_VERIFICATION = "pending_verification"
    EXPIRED = "expired"
    CONTESTED = "contested"


class ExtractionMode(StrEnum):
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"


class EmbeddingProvider(StrEnum):
    NONE = "none"
    LOCAL = "local"
    API = "api"

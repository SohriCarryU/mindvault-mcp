from __future__ import annotations

from mindvault_mcp.config import AppConfig
from mindvault_mcp.models import VerificationQueueItem


class VerificationService:
    def __init__(self, config: AppConfig):
        self.backend_mode = config.verification.backend_mode

    def queue(self, card_id: str, queued_by: str) -> VerificationQueueItem:
        return VerificationQueueItem(card_id=card_id, queued_by=queued_by, backend_mode=self.backend_mode)

from __future__ import annotations

from mindvault_mcp.enums import CardStatus, Library
from mindvault_mcp.models import Card


def test_repository_saves_markdown_and_index(runtime) -> None:
    card = Card(title="Repo card", problem="Sync storage", tags=["repo"])
    runtime.repository.save(card)
    loaded = runtime.repository.get(card.card_id)
    assert loaded.title == "Repo card"
    results = runtime.repository.search(query="Sync", library=Library.STAGING)
    assert [item.card_id for item in results] == [card.card_id]


def test_repository_approve_moves_staging_to_primary(runtime) -> None:
    card = Card(title="Candidate", problem="Promote me", library=Library.STAGING)
    runtime.repository.save(card)
    approved = runtime.repository.approve(card.card_id, source_agent="admin")
    assert approved.library == Library.PRIMARY
    assert approved.status == CardStatus.ACTIVE
    assert not (runtime.config.storage.staging_path / f"{card.card_id}.md").exists()
    assert (runtime.config.storage.primary_path / f"{card.card_id}.md").exists()

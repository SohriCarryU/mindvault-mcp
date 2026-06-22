from __future__ import annotations

from pathlib import Path

from mindvault_mcp.enums import CardStatus, Library
from mindvault_mcp.models import Card
from mindvault_mcp.storage import SQLiteIndex


def test_sqlite_index_upsert_search_delete(tmp_path: Path) -> None:
    index = SQLiteIndex(tmp_path / "index.sqlite")
    card = Card(
        title="SQLite memory",
        problem="Need queryable cards",
        tags=["sqlite", "storage"],
        domain="infra",
        library=Library.PRIMARY,
        status=CardStatus.ACTIVE,
    )
    index.upsert_card(card)
    assert index.get_card_location(card.card_id) == (card.card_id, Library.PRIMARY)
    assert index.search(query="queryable") == [(card.card_id, Library.PRIMARY)]
    assert index.search(tags=["sqlite"], domain="infra") == [(card.card_id, Library.PRIMARY)]
    index.delete_card(card.card_id)
    assert index.get_card_location(card.card_id) is None


def test_sqlite_index_upserts_and_reads_card_embedding(tmp_path: Path) -> None:
    index = SQLiteIndex(tmp_path / "index.sqlite")

    index.upsert_card_embedding(
        card_id="card-1",
        provider="local",
        vector=[0.1, 0.2],
        searchable_text_hash="hash-1",
        updated_at="2026-01-01T00:00:00+00:00",
    )

    stored = index.get_card_embedding("card-1", "local")

    assert stored == {
        "card_id": "card-1",
        "provider": "local",
        "dimension": 2,
        "vector": [0.1, 0.2],
        "searchable_text_hash": "hash-1",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }


def test_sqlite_index_deletes_card_embedding_with_card(tmp_path: Path) -> None:
    index = SQLiteIndex(tmp_path / "index.sqlite")
    card = Card(title="Embedding cache card")
    index.upsert_card(card)
    index.upsert_card_embedding(
        card_id=card.card_id,
        provider="local",
        vector=[0.1, 0.2],
        searchable_text_hash="hash-1",
        updated_at="2026-01-01T00:00:00+00:00",
    )

    index.delete_card(card.card_id)

    assert index.get_card_embedding(card.card_id, "local") is None

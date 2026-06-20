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

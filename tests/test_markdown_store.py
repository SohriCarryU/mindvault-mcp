from __future__ import annotations

from pathlib import Path

from mindvault_mcp.enums import Library
from mindvault_mcp.models import Card
from mindvault_mcp.storage import MarkdownStore


def test_markdown_store_writes_and_reads_card(tmp_path: Path) -> None:
    store = MarkdownStore(tmp_path / "primary", tmp_path / "staging")
    card = Card(title="Test card", problem="Problem", tags=["Python"], library=Library.STAGING)
    path = store.write_card(card)
    assert path.exists()
    loaded = store.read_card(Library.STAGING, card.card_id)
    assert loaded.card_id == card.card_id
    assert loaded.tags == ["python"]
    assert "# Test card" in path.read_text(encoding="utf-8")

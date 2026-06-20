from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from mindvault_mcp.enums import Library
from mindvault_mcp.models import Card


FRONTMATTER_BOUNDARY = "---"


class MarkdownStore:
    def __init__(self, primary_path: Path, staging_path: Path):
        self.paths = {
            Library.PRIMARY: primary_path,
            Library.STAGING: staging_path,
        }
        for path in self.paths.values():
            path.mkdir(parents=True, exist_ok=True)

    def _path_for(self, library: Library | str, card_id: str) -> Path:
        safe_id = re.sub(r"[^a-zA-Z0-9_.-]", "_", card_id)
        return self.paths[Library(library)] / f"{safe_id}.md"

    def write_card(self, card: Card) -> Path:
        path = self._path_for(card.library, card.card_id)
        data = card.model_dump(mode="json")
        body = self._render_body(card)
        frontmatter = yaml.safe_dump(data, sort_keys=True, allow_unicode=False)
        path.write_text(
            f"{FRONTMATTER_BOUNDARY}\n{frontmatter}{FRONTMATTER_BOUNDARY}\n\n{body}\n",
            encoding="utf-8",
        )
        return path

    def read_card(self, library: Library | str, card_id: str) -> Card:
        path = self._path_for(library, card_id)
        if not path.exists():
            raise FileNotFoundError(f"Card markdown not found: {path}")
        text = path.read_text(encoding="utf-8")
        meta = self._parse_frontmatter(text)
        return Card.model_validate(meta)

    def delete_card(self, library: Library | str, card_id: str) -> None:
        path = self._path_for(library, card_id)
        if path.exists():
            path.unlink()

    def list_cards(self, library: Library | str) -> list[Card]:
        cards: list[Card] = []
        for path in sorted(self.paths[Library(library)].glob("*.md")):
            meta = self._parse_frontmatter(path.read_text(encoding="utf-8"))
            cards.append(Card.model_validate(meta))
        return cards

    def _parse_frontmatter(self, text: str) -> dict[str, Any]:
        if not text.startswith(FRONTMATTER_BOUNDARY):
            raise ValueError("Card markdown is missing frontmatter.")
        parts = text.split(FRONTMATTER_BOUNDARY, 2)
        if len(parts) < 3:
            raise ValueError("Card markdown has invalid frontmatter.")
        return yaml.safe_load(parts[1]) or {}

    def _render_body(self, card: Card) -> str:
        sections = [
            ("Problem", card.problem),
            ("Context", card.context),
            ("Insight", card.insight),
            ("Solution", card.solution),
        ]
        lines = [f"# {card.title}", ""]
        for heading, value in sections:
            lines.extend([f"## {heading}", value or "_Not specified._", ""])
        return "\n".join(lines).rstrip()

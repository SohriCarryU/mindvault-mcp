from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

from mindvault_mcp.enums import Library
from mindvault_mcp.models import Card


class SQLiteIndex:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # TRUNCATE avoids delete-heavy rollback journal behavior, which is friendlier
        # to restricted workspaces while keeping SQLite's normal transactional path.
        conn.execute("PRAGMA journal_mode=TRUNCATE")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cards (
                    card_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    library TEXT NOT NULL,
                    status TEXT NOT NULL,
                    verification_status TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    privacy_level INTEGER NOT NULL,
                    source_agent TEXT NOT NULL,
                    searchable_text TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cards_library ON cards(library)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cards_status ON cards(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cards_verification ON cards(verification_status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_cards_domain ON cards(domain)")

    def upsert_card(self, card: Card) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO cards (
                    card_id, title, library, status, verification_status, domain,
                    tags_json, privacy_level, source_agent, searchable_text, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(card_id) DO UPDATE SET
                    title=excluded.title,
                    library=excluded.library,
                    status=excluded.status,
                    verification_status=excluded.verification_status,
                    domain=excluded.domain,
                    tags_json=excluded.tags_json,
                    privacy_level=excluded.privacy_level,
                    source_agent=excluded.source_agent,
                    searchable_text=excluded.searchable_text,
                    updated_at=excluded.updated_at
                """,
                (
                    card.card_id,
                    card.title,
                    str(card.library),
                    str(card.status),
                    str(card.verification_status),
                    card.domain,
                    json.dumps(card.tags),
                    card.privacy_level,
                    card.source_agent,
                    card.searchable_text(),
                    card.updated_at.isoformat(),
                ),
            )

    def delete_card(self, card_id: str) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM cards WHERE card_id = ?", (card_id,))

    def get_card_location(self, card_id: str) -> tuple[str, Library] | None:
        with self.connect() as conn:
            row = conn.execute("SELECT card_id, library FROM cards WHERE card_id = ?", (card_id,)).fetchone()
        if row is None:
            return None
        return row["card_id"], Library(row["library"])

    def search(
        self,
        query: str | None = None,
        tags: Iterable[str] | None = None,
        domain: str | None = None,
        library: Library | str | None = None,
        status: str | None = None,
        verification_status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[tuple[str, Library]]:
        clauses: list[str] = []
        params: list[object] = []
        if query:
            clauses.append("(searchable_text LIKE ? OR title LIKE ?)")
            needle = f"%{query}%"
            params.extend([needle, needle])
        if domain:
            clauses.append("domain = ?")
            params.append(domain)
        if library:
            clauses.append("library = ?")
            params.append(str(Library(library)))
        if status:
            clauses.append("status = ?")
            params.append(status)
        if verification_status:
            clauses.append("verification_status = ?")
            params.append(verification_status)
        for tag in tags or []:
            clauses.append("tags_json LIKE ?")
            params.append(f"%\"{tag.lower()}\"%")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"""
            SELECT card_id, library FROM cards
            {where}
            ORDER BY
                CASE library WHEN 'primary' THEN 0 ELSE 1 END,
                updated_at DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [(row["card_id"], Library(row["library"])) for row in rows]

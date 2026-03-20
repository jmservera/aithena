"""Collections schema migration: creates collections and collection_items tables.

This migration initialises a **separate** SQLite database for user document
collections.  It is called by ``collections_service.init_collections_db`` on
startup and does NOT participate in the auth migration framework.
"""

from __future__ import annotations

import sqlite3

VERSION = 1
DESCRIPTION = "Initial schema: collections and collection_items tables"


def upgrade(connection: sqlite3.Connection) -> None:
    """Create the collections schema with indexes and FK support."""
    connection.execute("PRAGMA foreign_keys = ON")

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS collections (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_collections_user_id ON collections (user_id)")

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS collection_items (
            id TEXT PRIMARY KEY,
            collection_id TEXT NOT NULL,
            document_id TEXT NOT NULL,
            position INTEGER,
            note TEXT,
            added_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE,
            UNIQUE (collection_id, document_id)
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_collection_items_collection_id ON collection_items (collection_id)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_collection_items_position ON collection_items (position)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_collection_items_document_id ON collection_items (document_id)"
    )

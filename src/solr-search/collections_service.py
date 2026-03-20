"""Collections service — SQLite CRUD for user document collections."""

from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def _connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Schema initialisation
# ---------------------------------------------------------------------------


def init_collections_db(db_path: Path) -> None:
    """Ensure the collections database and tables exist."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    from migrations import _collections_init as migration  # noqa: PLC0415 (late import)

    with sqlite3.connect(db_path) as connection:
        migration.upgrade(connection)
        connection.commit()
    logger.info("Collections DB initialised at %s", db_path)


# ---------------------------------------------------------------------------
# Internal: import alias for the migration module
# ---------------------------------------------------------------------------
# The migration file lives at migrations/001_collections_init.py which is
# not a valid Python identifier.  We re-export it under a private alias
# inside the migrations package so that a normal ``import`` works.
# The alias is set up in _register_collections_migration() below.


def _register_collections_migration() -> None:  # pragma: no cover — bootstrapping
    """Make ``migrations._collections_init`` importable."""
    import importlib
    import sys

    if "migrations._collections_init" not in sys.modules:
        mod = importlib.import_module("migrations.001_collections_init")
        sys.modules["migrations._collections_init"] = mod


_register_collections_migration()


# ---------------------------------------------------------------------------
# Collection CRUD
# ---------------------------------------------------------------------------


def create_collection(db_path: Path, user_id: str, name: str, description: str | None) -> dict:
    now = _utcnow()
    collection_id = _new_id()
    with _connect(db_path) as conn:
        conn.execute(
            "INSERT INTO collections (id, user_id, name, description, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (collection_id, user_id, name, description, now, now),
        )
        conn.commit()
    return {
        "id": collection_id,
        "user_id": user_id,
        "name": name,
        "description": description,
        "item_count": 0,
        "created_at": now,
        "updated_at": now,
    }


def list_collections(db_path: Path, user_id: str) -> list[dict]:
    with _connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT c.id, c.user_id, c.name, c.description, c.created_at, c.updated_at,
                   (SELECT COUNT(*) FROM collection_items ci WHERE ci.collection_id = c.id) AS item_count
            FROM collections c
            WHERE c.user_id = ?
            ORDER BY c.created_at DESC
            """,
            (user_id,),
        ).fetchall()
    return [
        {
            "id": r["id"],
            "user_id": r["user_id"],
            "name": r["name"],
            "description": r["description"],
            "item_count": r["item_count"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    ]


def get_collection(db_path: Path, collection_id: str, user_id: str) -> dict | None:
    """Return collection with items, or None if not found / not owned."""
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT id, user_id, name, description, created_at, updated_at FROM collections WHERE id = ?",
            (collection_id,),
        ).fetchone()
        if row is None or row["user_id"] != user_id:
            return None

        items = conn.execute(
            """
            SELECT id, collection_id, document_id, position, note, added_at, updated_at
            FROM collection_items
            WHERE collection_id = ?
            ORDER BY position ASC NULLS LAST, added_at ASC
            """,
            (collection_id,),
        ).fetchall()

    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "name": row["name"],
        "description": row["description"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "items": [
            {
                "id": i["id"],
                "collection_id": i["collection_id"],
                "document_id": i["document_id"],
                "position": i["position"],
                "note": i["note"],
                "added_at": i["added_at"],
                "updated_at": i["updated_at"],
            }
            for i in items
        ],
    }


def update_collection(
    db_path: Path, collection_id: str, user_id: str, *, name: str | None = None, description: str | None = None
) -> dict | None:
    """Update a collection's name/description. Returns None if not found/not owned."""
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT user_id FROM collections WHERE id = ?",
            (collection_id,),
        ).fetchone()
        if row is None or row["user_id"] != user_id:
            return None

        sets: list[str] = []
        params: list[str] = []
        if name is not None:
            sets.append("name = ?")
            params.append(name)
        if description is not None:
            sets.append("description = ?")
            params.append(description)

        if sets:
            now = _utcnow()
            sets.append("updated_at = ?")
            params.append(now)
            params.append(collection_id)
            conn.execute(f"UPDATE collections SET {', '.join(sets)} WHERE id = ?", params)  # noqa: S608
            conn.commit()

    return get_collection(db_path, collection_id, user_id)


def delete_collection(db_path: Path, collection_id: str, user_id: str) -> bool:
    """Delete a collection (cascade deletes items). Returns False if not found/not owned."""
    with _connect(db_path) as conn:
        row = conn.execute("SELECT user_id FROM collections WHERE id = ?", (collection_id,)).fetchone()
        if row is None or row["user_id"] != user_id:
            return False
        conn.execute("DELETE FROM collections WHERE id = ?", (collection_id,))
        conn.commit()
    return True


# ---------------------------------------------------------------------------
# Collection Items CRUD
# ---------------------------------------------------------------------------


def _verify_collection_owner(conn: sqlite3.Connection, collection_id: str, user_id: str) -> bool:
    row = conn.execute("SELECT user_id FROM collections WHERE id = ?", (collection_id,)).fetchone()
    return row is not None and row["user_id"] == user_id


def add_items(db_path: Path, collection_id: str, user_id: str, document_ids: list[str]) -> list[dict]:
    """Add documents to a collection, skipping duplicates. Returns added items."""
    now = _utcnow()
    added: list[dict] = []
    with _connect(db_path) as conn:
        if not _verify_collection_owner(conn, collection_id, user_id):
            return []

        # Determine the next position
        row = conn.execute(
            "SELECT MAX(position) AS max_pos FROM collection_items WHERE collection_id = ?",
            (collection_id,),
        ).fetchone()
        next_pos = (row["max_pos"] or 0) + 1 if row and row["max_pos"] is not None else 1

        for doc_id in document_ids:
            item_id = _new_id()
            try:
                conn.execute(
                    "INSERT INTO collection_items"
                    " (id, collection_id, document_id, position, note, added_at, updated_at)"
                    " VALUES (?, ?, ?, ?, NULL, ?, ?)",
                    (item_id, collection_id, doc_id, next_pos, now, now),
                )
                added.append(
                    {
                        "id": item_id,
                        "collection_id": collection_id,
                        "document_id": doc_id,
                        "position": next_pos,
                        "note": None,
                        "added_at": now,
                        "updated_at": now,
                    }
                )
                next_pos += 1
            except sqlite3.IntegrityError:
                # Duplicate (collection_id, document_id) — skip
                continue
        conn.commit()
    return added


def remove_item(db_path: Path, collection_id: str, user_id: str, item_id: str) -> bool:
    with _connect(db_path) as conn:
        if not _verify_collection_owner(conn, collection_id, user_id):
            return False
        cursor = conn.execute(
            "DELETE FROM collection_items WHERE id = ? AND collection_id = ?",
            (item_id, collection_id),
        )
        conn.commit()
    return cursor.rowcount > 0


def update_item(
    db_path: Path,
    collection_id: str,
    user_id: str,
    item_id: str,
    *,
    note: str | None = None,
    position: int | None = None,
    note_max_length: int = 1000,
) -> dict | None:
    """Update an item's note and/or position. Returns the updated item or None."""
    with _connect(db_path) as conn:
        if not _verify_collection_owner(conn, collection_id, user_id):
            return None

        row = conn.execute(
            "SELECT id FROM collection_items WHERE id = ? AND collection_id = ?",
            (item_id, collection_id),
        ).fetchone()
        if row is None:
            return None

        sets: list[str] = []
        params: list = []
        if note is not None:
            if len(note) > note_max_length:
                raise ValueError(f"Note exceeds maximum length of {note_max_length} characters")
            sets.append("note = ?")
            params.append(note)
        if position is not None:
            sets.append("position = ?")
            params.append(position)

        if sets:
            now = _utcnow()
            sets.append("updated_at = ?")
            params.append(now)
            params.append(item_id)
            conn.execute(f"UPDATE collection_items SET {', '.join(sets)} WHERE id = ?", params)  # noqa: S608
            conn.commit()

        updated = conn.execute(
            "SELECT id, collection_id, document_id, position, note, added_at, updated_at "
            "FROM collection_items WHERE id = ?",
            (item_id,),
        ).fetchone()
        if updated is None:
            return None  # pragma: no cover
        return {
            "id": updated["id"],
            "collection_id": updated["collection_id"],
            "document_id": updated["document_id"],
            "position": updated["position"],
            "note": updated["note"],
            "added_at": updated["added_at"],
            "updated_at": updated["updated_at"],
        }


def reorder_items(db_path: Path, collection_id: str, user_id: str, item_ids: list[str]) -> bool:
    """Re-assign positions 1..N according to the supplied item_ids order."""
    with _connect(db_path) as conn:
        if not _verify_collection_owner(conn, collection_id, user_id):
            return False

        now = _utcnow()
        for position, item_id in enumerate(item_ids, start=1):
            conn.execute(
                "UPDATE collection_items SET position = ?, updated_at = ? WHERE id = ? AND collection_id = ?",
                (position, now, item_id, collection_id),
            )
        conn.commit()
    return True

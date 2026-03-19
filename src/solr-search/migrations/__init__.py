"""Forward-only migration framework for the auth SQLite database.

Migrations are numbered sequentially starting from 2 (version 1 is the
initial schema created by ``init_auth_db``).  Each migration is a module
inside this package named ``mNNNN_<description>.py`` that exposes:

    VERSION: int          — target schema version
    DESCRIPTION: str      — short human-readable summary
    upgrade(conn): None   — receives an open sqlite3.Connection *inside*
                            a transaction; must NOT call ``conn.commit()``.

Migrations are applied in VERSION order.  The framework records each
applied version in the ``schema_version`` table after a successful commit.
Rollbacks are not supported — keep migrations additive.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
import sqlite3
from pathlib import Path
from types import ModuleType

logger = logging.getLogger(__name__)


def _discover_migrations() -> list[ModuleType]:
    """Import all ``mNNNN_*`` sub-modules and return them sorted by VERSION."""
    package_path = str(Path(__file__).resolve().parent)
    modules: list[ModuleType] = []
    for info in pkgutil.iter_modules([package_path]):
        if not info.name.startswith("m"):
            continue
        mod = importlib.import_module(f"migrations.{info.name}")
        if hasattr(mod, "VERSION") and hasattr(mod, "upgrade"):
            modules.append(mod)
    modules.sort(key=lambda m: m.VERSION)
    return modules


def apply_pending_migrations(db_path: Path) -> int:
    """Apply all migrations whose VERSION exceeds the current schema_version.

    Returns the number of migrations applied.
    """
    migrations = _discover_migrations()
    if not migrations:
        return 0

    applied = 0
    with sqlite3.connect(db_path) as connection:
        row = connection.execute("SELECT MAX(version) FROM schema_version").fetchone()
        current_version: int = int(row[0]) if row and row[0] is not None else 0

        for migration in migrations:
            if current_version >= migration.VERSION:
                continue

            description = getattr(migration, "DESCRIPTION", "")
            logger.info(
                "Applying migration %d: %s", migration.VERSION, description
            )
            migration.upgrade(connection)
            connection.execute(
                "INSERT INTO schema_version (version, description) VALUES (?, ?)",
                (migration.VERSION, description),
            )
            connection.commit()
            applied += 1
            logger.info("Migration %d applied successfully", migration.VERSION)

    if applied:
        logger.info("Applied %d migration(s); schema now at version %d", applied, migrations[-1].VERSION)
    else:
        logger.debug("Auth DB schema is up to date (version %d)", current_version)

    return applied

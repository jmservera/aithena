# Decision: Auth DB Migration Framework

**Author:** Brett (Infrastructure Architect)
**Date:** 2026-07-22
**Issue:** #557
**PR:** #571

## Context

The auth system uses an SQLite database at `AUTH_DB_PATH`. As features evolve, the schema will need changes. We need a strategy that is safe, forward-only, and doesn't require external tools.

## Decisions

1. **Schema versioning via `schema_version` table.** Every auth DB tracks its version. Version 1 is the initial schema (users table). This is the source of truth for migration state.

2. **Forward-only migrations.** Rollbacks are not supported. Migrations must be additive (add columns, add tables, add indexes). Destructive changes should be avoided or handled by creating new structures and migrating data forward.

3. **Migration naming convention:** `mNNNN_<description>.py` in `src/solr-search/migrations/`. Each module exposes `VERSION` (int), `DESCRIPTION` (str), and `upgrade(conn)` (function). Migrations are auto-discovered and applied in VERSION order on startup.

4. **Migrations run inside transactions.** The `upgrade()` function must NOT call `conn.commit()`. The framework commits after recording the version. If a migration fails, the transaction rolls back and the app will retry on next startup.

5. **Backup strategy:** Use SQLite `.backup` command via `scripts/backup_auth_db.sh`. This is safe to run while the app is serving traffic. Backups go to `/data/auth/backups/` by default.

6. **No external migration tools.** We chose a lightweight custom framework over Alembic because the auth DB is a single-file embedded SQLite database with a simple schema. The custom approach has zero dependencies and is self-contained.

## Impact

- **Parker/Dallas:** When adding auth features that need schema changes, create a new migration file following the template. Don't modify `init_auth_db` directly for schema evolution.
- **Brett:** Backup script is included in the container image. Production deployments should add a cron job for scheduled backups.
- **All:** The migration framework applies automatically on startup — no manual intervention needed for upgrades.

#!/bin/sh
# backup_auth_db.sh — Safe SQLite backup for the Aithena auth database.
#
# Usage:
#   ./backup_auth_db.sh                 # backs up to /data/auth/backups/
#   ./backup_auth_db.sh /my/backup/dir  # backs up to custom directory
#   BACKUP_DIR=/my/dir ./backup_auth_db.sh  # env-var override
#
# The script uses SQLite's `.backup` command for a consistent, non-locking
# snapshot.  It is safe to run while the application is serving traffic.
#
# To run inside the running solr-search container:
#   docker compose exec solr-search /app/scripts/backup_auth_db.sh

set -eu

AUTH_DB_PATH="${AUTH_DB_PATH:-/data/auth/users.db}"
BACKUP_DIR="${1:-${BACKUP_DIR:-/data/auth/backups}}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_FILE="${BACKUP_DIR}/users_${TIMESTAMP}.db"

if [ ! -f "$AUTH_DB_PATH" ]; then
    echo "ERROR: Auth database not found at ${AUTH_DB_PATH}" >&2
    exit 1
fi

if ! command -v sqlite3 >/dev/null 2>&1; then
    echo "ERROR: sqlite3 is not installed" >&2
    exit 1
fi

mkdir -p "$BACKUP_DIR"

sqlite3 "$AUTH_DB_PATH" ".backup '${BACKUP_FILE}'"

# Verify the backup is a valid SQLite database
if sqlite3 "$BACKUP_FILE" "PRAGMA integrity_check;" | grep -q "^ok$"; then
    BACKUP_SIZE="$(wc -c < "$BACKUP_FILE" | tr -d ' ')"
    echo "OK: Backup created at ${BACKUP_FILE} (${BACKUP_SIZE} bytes)"
else
    echo "ERROR: Backup integrity check failed for ${BACKUP_FILE}" >&2
    rm -f "$BACKUP_FILE"
    exit 1
fi

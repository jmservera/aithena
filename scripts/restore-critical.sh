#!/usr/bin/env bash
# =============================================================================
# Aithena BCDR — Tier 1: Critical Data Restore (Auth DBs + Secrets)
# =============================================================================
# Restores encrypted Auth SQLite DB, Collections SQLite DB, and .env secrets
# from a backup directory produced by backup-critical.sh.
#
# Usage:
#   ./scripts/restore-critical.sh              # restore all critical components
#   COMPONENT=auth ./scripts/restore-critical.sh   # restore only auth DB
#   DRY_RUN=1 ./scripts/restore-critical.sh        # preview without writing
#
# Environment variables (all have sensible defaults):
#   RESTORE_FROM            Backup directory to restore from (required)
#   COMPONENT               Component filter: auth|collections|secrets|all (default: all)
#   AUTH_DB_DIR             Host path to auth SQLite databases (default: /data/auth)
#   BACKUP_KEY              GPG passphrase file for AES-256 decryption (default: /etc/aithena/backup.key)
#   PROJECT_ROOT            Repository / project root on the host
#   LOG_FILE                Log file path (default: /var/log/aithena-restore-critical.log)
#   DRY_RUN                 Set to 1 to skip actual file operations
#
# Exit codes:
#   0  All restores succeeded
#   1  Fatal error (missing tools, missing backup, decryption failure)
#   2  Partial failure (some optional components missing — logged as warnings)
#
# See also: docs/prd/bcdr-plan.md §4.2
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
RESTORE_FROM="${RESTORE_FROM:?RESTORE_FROM must be set to the backup directory}"
COMPONENT="${COMPONENT:-all}"
AUTH_DB_DIR="${AUTH_DB_DIR:-/data/auth}"
BACKUP_KEY="${BACKUP_KEY:-/etc/aithena/backup.key}"
PROJECT_ROOT="${PROJECT_ROOT:-/source/aithena}"
DRY_RUN="${DRY_RUN:-0}"

# Restrictive umask — restored files must not be world-readable
umask 077

TIMESTAMP="$(date -u +%Y%m%d-%H%M)"
LOG_FILE="${LOG_FILE:-/var/log/aithena-restore-critical.log}"
TMPDIR_BASE="${TMPDIR:-/tmp}"
WORK_DIR=""          # set in main, cleaned up by trap
EXIT_CODE=0          # escalated to 2 on non-fatal warnings

# --- Ensure log file is writable; fall back to project-local if not ---
_init_log() {
    mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
    if ! touch "$LOG_FILE" 2>/dev/null; then
        LOG_FILE="${PROJECT_ROOT}/restore-critical.log"
        mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
        if ! touch "$LOG_FILE" 2>/dev/null; then
            LOG_FILE="/dev/null"
        fi
    fi
}
_init_log

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
log() {
    local level="$1"; shift
    local msg
    msg="$(date -u '+%Y-%m-%dT%H:%M:%SZ') [${level}] $*"
    echo "$msg" >&2
    echo "$msg" >> "$LOG_FILE" 2>/dev/null || true
}

log_info()  { log "INFO"  "$@"; }
log_warn()  { log "WARN"  "$@"; }
log_error() { log "ERROR" "$@"; }

# ---------------------------------------------------------------------------
# Cleanup trap — remove temp work directory on exit / signal
# ---------------------------------------------------------------------------
cleanup() {
    if [[ -n "${WORK_DIR}" && -d "${WORK_DIR}" ]]; then
        rm -rf "${WORK_DIR}"
        log_info "Cleaned up temp directory ${WORK_DIR}"
    fi
}
trap cleanup EXIT INT TERM

# ---------------------------------------------------------------------------
# Dependency checks
# ---------------------------------------------------------------------------
require_cmd() {
    if ! command -v "$1" &>/dev/null; then
        log_error "Required command '$1' not found. Install it and retry."
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# verify_checksum — validate SHA-256 sidecar for a backup file
# ---------------------------------------------------------------------------
verify_checksum() {
    local file="$1"
    local checksum_file="${file}.sha256"

    if [[ ! -f "$checksum_file" ]]; then
        log_warn "Checksum sidecar not found: ${checksum_file}"
        return 1
    fi

    pushd "$(dirname "$checksum_file")" > /dev/null
    if sha256sum --check "$(basename "$checksum_file")" &>/dev/null; then
        log_info "Checksum verified: ${file}"
        popd > /dev/null
        return 0
    else
        log_error "Checksum verification FAILED: ${file}"
        popd > /dev/null
        return 1
    fi
}

# ---------------------------------------------------------------------------
# find_latest_backup — find the most recent backup file matching a pattern
# ---------------------------------------------------------------------------
find_latest_backup() {
    local dir="$1"
    local pattern="$2"

    find "$dir" -maxdepth 1 -name "$pattern" -type f -print0 2>/dev/null \
        | xargs -0 ls -t 2>/dev/null \
        | head -1
}

# ---------------------------------------------------------------------------
# restore_auth_db — decrypt GPG backup, restore SQLite, verify
# ---------------------------------------------------------------------------
restore_auth_db() {
    log_info "Restoring auth database..."

    local backup_file
    backup_file="$(find_latest_backup "$RESTORE_FROM" "auth-*.db.gpg")"

    if [[ -z "$backup_file" ]]; then
        if [[ "$DRY_RUN" == "1" ]]; then
            log_info "[DRY_RUN] No auth backup found in ${RESTORE_FROM} — skipping (dry-run)"
            return 0
        fi
        log_error "No auth backup found in ${RESTORE_FROM} matching auth-*.db.gpg"
        return 1
    fi

    log_info "Found auth backup: ${backup_file}"

    # Verify checksum (non-fatal in dry-run — backup may be a mock placeholder)
    verify_checksum "$backup_file" || {
        if [[ "$DRY_RUN" == "1" ]]; then
            log_warn "Auth backup checksum not available — continuing (dry-run)"
        else
            log_error "Auth backup integrity check failed — aborting restore"
            return 1
        fi
    }

    if [[ "$DRY_RUN" == "1" ]]; then
        log_info "[DRY_RUN] Would restore auth DB from ${backup_file} → ${AUTH_DB_DIR}/users.db"
        return 0
    fi

    # Decrypt to temp directory
    local decrypted="${WORK_DIR}/auth-restored.db"
    gpg --decrypt --batch --yes --pinentry-mode loopback --no-tty \
        --passphrase-file "$BACKUP_KEY" \
        --output "$decrypted" "$backup_file" 2>/dev/null || {
        log_error "Failed to decrypt auth backup: ${backup_file}"
        return 1
    }

    # Verify decrypted DB is a valid SQLite file
    if ! sqlite3 "$decrypted" "SELECT COUNT(*) FROM sqlite_master;" &>/dev/null; then
        log_error "Decrypted auth DB is not a valid SQLite database"
        return 1
    fi

    # Move into place
    mkdir -p "$AUTH_DB_DIR"
    cp "$decrypted" "${AUTH_DB_DIR}/users.db"
    chmod 600 "${AUTH_DB_DIR}/users.db"

    # Post-restore verification
    local user_count
    user_count="$(sqlite3 "${AUTH_DB_DIR}/users.db" "SELECT COUNT(*) FROM users;" 2>/dev/null)" || {
        log_error "Post-restore verification failed: cannot query users table"
        return 1
    }
    log_info "Auth DB restored: ${user_count} user(s) verified"

    rm -f "$decrypted"
}

# ---------------------------------------------------------------------------
# restore_collections_db — decrypt GPG backup, restore SQLite
# ---------------------------------------------------------------------------
restore_collections_db() {
    log_info "Restoring collections database..."

    local backup_file
    backup_file="$(find_latest_backup "$RESTORE_FROM" "collections-*.db.gpg")"

    if [[ -z "$backup_file" ]]; then
        if [[ "$DRY_RUN" == "1" ]]; then
            log_info "[DRY_RUN] No collections backup found in ${RESTORE_FROM} — skipping (dry-run)"
            return 0
        fi
        log_warn "No collections backup found in ${RESTORE_FROM} — skipping (optional)"
        EXIT_CODE=2
        return 0
    fi

    log_info "Found collections backup: ${backup_file}"

    # Verify checksum (non-fatal in dry-run — backup may be a mock placeholder)
    verify_checksum "$backup_file" || {
        if [[ "$DRY_RUN" == "1" ]]; then
            log_warn "Collections backup checksum not available — continuing (dry-run)"
        else
            log_error "Collections backup integrity check failed — aborting restore"
            return 1
        fi
    }

    if [[ "$DRY_RUN" == "1" ]]; then
        log_info "[DRY_RUN] Would restore collections DB from ${backup_file} → ${AUTH_DB_DIR}/collections.db"
        return 0
    fi

    # Decrypt to temp directory
    local decrypted="${WORK_DIR}/collections-restored.db"
    gpg --decrypt --batch --yes --pinentry-mode loopback --no-tty \
        --passphrase-file "$BACKUP_KEY" \
        --output "$decrypted" "$backup_file" 2>/dev/null || {
        log_error "Failed to decrypt collections backup: ${backup_file}"
        return 1
    }

    # Verify decrypted DB is a valid SQLite file
    if ! sqlite3 "$decrypted" "SELECT COUNT(*) FROM sqlite_master;" &>/dev/null; then
        log_error "Decrypted collections DB is not a valid SQLite database"
        return 1
    fi

    # Move into place
    mkdir -p "$AUTH_DB_DIR"
    cp "$decrypted" "${AUTH_DB_DIR}/collections.db"
    chmod 600 "${AUTH_DB_DIR}/collections.db"

    log_info "Collections DB restored successfully"
    rm -f "$decrypted"
}

# ---------------------------------------------------------------------------
# restore_secrets — decrypt GPG backup, restore .env file
# ---------------------------------------------------------------------------
restore_secrets() {
    log_info "Restoring secrets (.env)..."

    local backup_file
    backup_file="$(find_latest_backup "$RESTORE_FROM" "env-*.gpg")"

    if [[ -z "$backup_file" ]]; then
        if [[ "$DRY_RUN" == "1" ]]; then
            log_info "[DRY_RUN] No secrets backup found in ${RESTORE_FROM} — skipping (dry-run)"
            return 0
        fi
        log_error "No secrets backup found in ${RESTORE_FROM} matching env-*.gpg"
        return 1
    fi

    log_info "Found secrets backup: ${backup_file}"

    # Verify checksum (non-fatal in dry-run — backup may be a mock placeholder)
    verify_checksum "$backup_file" || {
        if [[ "$DRY_RUN" == "1" ]]; then
            log_warn "Secrets backup checksum not available — continuing (dry-run)"
        else
            log_error "Secrets backup integrity check failed — aborting restore"
            return 1
        fi
    }

    if [[ "$DRY_RUN" == "1" ]]; then
        log_info "[DRY_RUN] Would restore .env from ${backup_file} → ${PROJECT_ROOT}/.env"
        return 0
    fi

    # Decrypt to temp directory
    local decrypted="${WORK_DIR}/env-restored"
    gpg --decrypt --batch --yes --pinentry-mode loopback --no-tty \
        --passphrase-file "$BACKUP_KEY" \
        --output "$decrypted" "$backup_file" 2>/dev/null || {
        log_error "Failed to decrypt secrets backup: ${backup_file}"
        return 1
    }

    # Move into place
    mkdir -p "$PROJECT_ROOT"
    cp "$decrypted" "${PROJECT_ROOT}/.env"
    chmod 600 "${PROJECT_ROOT}/.env"

    log_info "Secrets (.env) restored successfully"
    rm -f "$decrypted"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    # --- Pre-flight: flock required before lock guard ---
    require_cmd flock

    # Concurrency guard — only one restore instance at a time
    local lock_dir
    lock_dir="$(dirname "$RESTORE_FROM")"
    mkdir -p "$lock_dir"
    local lock_file="${lock_dir}/.restore-critical.lock"
    exec 9>"$lock_file"
    if ! flock -n 9; then
        log_error "Another restore instance is already running (lock: ${lock_file})"
        exit 1
    fi

    log_info "========== Aithena Critical Restore START (${TIMESTAMP}) =========="
    log_info "RESTORE_FROM=${RESTORE_FROM}  COMPONENT=${COMPONENT}  DRY_RUN=${DRY_RUN}"

    # --- Pre-flight checks ---
    require_cmd gpg
    require_cmd sqlite3
    require_cmd sha256sum
    require_cmd find

    if [[ ! -d "$RESTORE_FROM" ]]; then
        log_error "Backup directory not found: ${RESTORE_FROM}"
        exit 1
    fi

    if [[ ! -f "$BACKUP_KEY" ]]; then
        if [[ "$DRY_RUN" == "1" ]]; then
            log_warn "Encryption key not found: ${BACKUP_KEY} (skipped — dry-run mode)"
        else
            log_error "Encryption key not found: ${BACKUP_KEY}"
            exit 1
        fi
    fi

    # --- Temp working directory (cleaned up by trap) ---
    WORK_DIR="$(mktemp -d "${TMPDIR_BASE}/aithena-restore-critical-XXXXXX")"
    log_info "Work directory: ${WORK_DIR}"

    # --- Restore components based on COMPONENT filter ---
    case "$COMPONENT" in
        all)
            restore_auth_db || exit 1
            restore_collections_db || exit 1
            restore_secrets || exit 1
            ;;
        auth)
            restore_auth_db || exit 1
            ;;
        collections)
            restore_collections_db || exit 1
            ;;
        secrets)
            restore_secrets || exit 1
            ;;
        *)
            log_info "No critical-tier components requested (component=${COMPONENT})"
            ;;
    esac

    log_info "========== Aithena Critical Restore END   (exit=${EXIT_CODE}) =========="
    return "$EXIT_CODE"
}

main "$@"

#!/usr/bin/env bash
# =============================================================================
# Aithena BCDR — Tier 1: Critical Data Backup
# =============================================================================
# Backs up irreplaceable data: Auth SQLite DB, Collections SQLite DB, .env
# secrets.  Designed to run every 30 minutes via cron on the HOST.
#
# Usage:
#   ./scripts/backup-critical.sh              # normal run
#   DRY_RUN=1 ./scripts/backup-critical.sh    # log actions without writing
#
# Environment variables (all have sensible defaults):
#   AUTH_DB_DIR             Host path to auth SQLite databases
#   BACKUP_DIR              Where encrypted backups are stored
#   BACKUP_KEY              GPG passphrase file for AES-256 encryption
#   BACKUP_RETENTION_DAYS   Days to keep old backups (default: 7)
#   PROJECT_ROOT            Repository / project root on the host
#   LOG_FILE                Log file path (default: /var/log/aithena-backup-critical.log)
#   DRY_RUN                 Set to 1 to skip actual file operations
#
# Exit codes:
#   0  All mandatory backups succeeded
#   1  Fatal error (missing tools, missing key, encryption failure)
#   2  Partial failure (some optional files missing — logged as warnings)
#
# See also: docs/prd/bcdr-plan.md §4.1
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
AUTH_DB_DIR="${AUTH_DB_DIR:-/data/auth}"
BACKUP_DIR="${BACKUP_DIR:-/source/backups/critical}"
BACKUP_KEY="${BACKUP_KEY:-/etc/aithena/backup.key}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"
PROJECT_ROOT="${PROJECT_ROOT:-/source/aithena}"
DRY_RUN="${DRY_RUN:-0}"

# Restrictive umask — encrypted backups must not be world-readable
umask 077

# Validate BACKUP_RETENTION_DAYS is a positive integer
if ! [[ "$BACKUP_RETENTION_DAYS" =~ ^[0-9]+$ ]] || [[ "$BACKUP_RETENTION_DAYS" -lt 0 ]]; then
    echo "ERROR: BACKUP_RETENTION_DAYS must be a non-negative integer, got '${BACKUP_RETENTION_DAYS}'" >&2
    exit 1
fi

TIMESTAMP="$(date -u +%Y%m%d-%H%M)"
LOG_FILE="${LOG_FILE:-/var/log/aithena-backup-critical.log}"
TMPDIR_BASE="${TMPDIR:-/tmp}"
WORK_DIR=""          # set in main, cleaned up by trap
EXIT_CODE=0          # escalated to 2 on non-fatal warnings

# --- Ensure log file is writable; fall back to project-local if not ---
_init_log() {
    mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
    if ! touch "$LOG_FILE" 2>/dev/null; then
        LOG_FILE="${PROJECT_ROOT}/backup-critical.log"
        mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
        touch "$LOG_FILE" 2>/dev/null || true
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
    echo "$msg" | tee -a "$LOG_FILE" >&2
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
# backup_sqlite <src_db> <dest_basename> <required>
#   Uses SQLite .backup for an atomic, non-blocking copy, then encrypts with
#   GPG AES-256 and writes a SHA-256 checksum sidecar.
#   <required>: "required" → fail hard; "optional" → warn and continue.
# ---------------------------------------------------------------------------
backup_sqlite() {
    local src="$1"
    local dest_base="$2"
    local importance="$3"

    local raw_copy="${WORK_DIR}/${dest_base}.db"
    local enc_dest="${BACKUP_DIR}/${dest_base}-${TIMESTAMP}.db.gpg"
    local checksum_dest="${BACKUP_DIR}/${dest_base}-${TIMESTAMP}.db.gpg.sha256"

    if [[ ! -f "$src" ]]; then
        if [[ "$importance" == "required" ]]; then
            log_error "Required database not found: ${src}"
            exit 1
        else
            log_warn "Optional database not found: ${src} — skipping"
            EXIT_CODE=2
            return 0
        fi
    fi

    log_info "Backing up SQLite database: ${src}"

    if [[ "$DRY_RUN" == "1" ]]; then
        log_info "[DRY_RUN] Would backup ${src} → ${enc_dest}"
        return 0
    fi

    # Atomic SQLite backup — safe even while the DB is in use
    sqlite3 "$src" ".backup '${raw_copy}'"
    log_info "SQLite .backup completed: ${src} → ${raw_copy}"

    # Encrypt with GPG AES-256
    gpg --symmetric \
        --cipher-algo AES256 \
        --batch \
        --yes \
        --pinentry-mode loopback \
        --no-tty \
        --passphrase-file "$BACKUP_KEY" \
        --output "$enc_dest" \
        "$raw_copy"
    log_info "Encrypted: ${enc_dest}"

    # SHA-256 checksum sidecar
    sha256sum "$enc_dest" > "$checksum_dest"
    log_info "Checksum written: ${checksum_dest}"

    # Remove plaintext copy from work dir immediately
    rm -f "$raw_copy"
}

# ---------------------------------------------------------------------------
# backup_file <src_path> <dest_basename> <required>
#   Encrypts a plain file (e.g. .env) with GPG AES-256 and writes a SHA-256
#   checksum sidecar.  No SQLite step needed.
# ---------------------------------------------------------------------------
backup_file() {
    local src="$1"
    local dest_base="$2"
    local importance="$3"

    local enc_dest="${BACKUP_DIR}/${dest_base}-${TIMESTAMP}.gpg"
    local checksum_dest="${BACKUP_DIR}/${dest_base}-${TIMESTAMP}.gpg.sha256"

    if [[ ! -f "$src" ]]; then
        if [[ "$importance" == "required" ]]; then
            log_error "Required file not found: ${src}"
            exit 1
        else
            log_warn "Optional file not found: ${src} — skipping"
            EXIT_CODE=2
            return 0
        fi
    fi

    log_info "Backing up file: ${src}"

    if [[ "$DRY_RUN" == "1" ]]; then
        log_info "[DRY_RUN] Would backup ${src} → ${enc_dest}"
        return 0
    fi

    gpg --symmetric \
        --cipher-algo AES256 \
        --batch \
        --yes \
        --pinentry-mode loopback \
        --no-tty \
        --passphrase-file "$BACKUP_KEY" \
        --output "$enc_dest" \
        "$src"
    log_info "Encrypted: ${enc_dest}"

    sha256sum "$enc_dest" > "$checksum_dest"
    log_info "Checksum written: ${checksum_dest}"
}

# ---------------------------------------------------------------------------
# purge_old_backups — removes files older than $BACKUP_RETENTION_DAYS
# ---------------------------------------------------------------------------
purge_old_backups() {
    log_info "Purging backups older than ${BACKUP_RETENTION_DAYS} days from ${BACKUP_DIR}"

    if [[ "$DRY_RUN" == "1" ]]; then
        local count
        count="$(find "$BACKUP_DIR" -maxdepth 1 -type f \( -name '*.gpg' -o -name '*.sha256' \) -mtime "+${BACKUP_RETENTION_DAYS}" | wc -l)"
        log_info "[DRY_RUN] Would purge ${count} file(s)"
        return 0
    fi

    local deleted=0
    while IFS= read -r -d '' file; do
        rm -f "$file"
        log_info "Purged: ${file}"
        ((deleted++)) || true
    done < <(find "$BACKUP_DIR" -maxdepth 1 -type f \( -name '*.gpg' -o -name '*.sha256' \) -mtime "+${BACKUP_RETENTION_DAYS}" -print0)

    log_info "Purged ${deleted} expired file(s)"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    # Concurrency guard — only one backup instance at a time
    local lock_file="${BACKUP_DIR}/.backup-critical.lock"
    mkdir -p "$BACKUP_DIR"
    exec 9>"$lock_file"
    if ! flock -n 9; then
        log_error "Another backup instance is already running (lock: ${lock_file})"
        exit 1
    fi

    log_info "========== Aithena Critical Backup START (${TIMESTAMP}) =========="
    log_info "AUTH_DB_DIR=${AUTH_DB_DIR}  BACKUP_DIR=${BACKUP_DIR}  RETENTION=${BACKUP_RETENTION_DAYS}d"

    # --- Pre-flight checks ---
    require_cmd sqlite3
    require_cmd gpg
    require_cmd sha256sum
    require_cmd find

    if [[ ! -f "$BACKUP_KEY" ]]; then
        log_error "Encryption key not found: ${BACKUP_KEY}"
        log_error "Generate one with: sudo mkdir -p /etc/aithena && openssl rand -base64 32 | sudo tee ${BACKUP_KEY} && sudo chmod 600 ${BACKUP_KEY}"
        exit 1
    fi

    # Verify backup key is not world/group-readable
    local key_perms
    key_perms="$(stat -c '%a' "$BACKUP_KEY" 2>/dev/null || stat -f '%Lp' "$BACKUP_KEY" 2>/dev/null)"
    if [[ "${key_perms: -2:1}" != "0" || "${key_perms: -1}" != "0" ]]; then
        log_error "Backup key ${BACKUP_KEY} is too permissive (mode ${key_perms}). Run: chmod 600 ${BACKUP_KEY}"
        exit 1
    fi

    # --- Ensure backup directory exists ---
    mkdir -p "$BACKUP_DIR"

    # --- Temp working directory (cleaned up by trap) ---
    WORK_DIR="$(mktemp -d "${TMPDIR_BASE}/aithena-backup-XXXXXX")"
    log_info "Work directory: ${WORK_DIR}"

    # --- Backup SQLite databases ---
    backup_sqlite "${AUTH_DB_DIR}/users.db"       "auth"        "required"
    backup_sqlite "${AUTH_DB_DIR}/collections.db"  "collections" "optional"

    # --- Backup .env secrets ---
    backup_file "${PROJECT_ROOT}/.env" "env" "required"

    # --- Retention purge ---
    purge_old_backups

    log_info "========== Aithena Critical Backup END   (exit=${EXIT_CODE}) =========="
    return "$EXIT_CODE"
}

main "$@"

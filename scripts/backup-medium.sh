#!/usr/bin/env bash
# =============================================================================
# Aithena BCDR — Tier 3: Medium-Priority Data Backup (Redis + RabbitMQ)
# =============================================================================
# Backs up Redis RDB snapshots (via BGSAVE + container copy) and RabbitMQ
# definitions (via Management API export).  Designed to run daily at 3 AM UTC
# via cron on the HOST.
#
# Usage:
#   ./scripts/backup-medium.sh              # normal run
#   DRY_RUN=1 ./scripts/backup-medium.sh    # log actions without writing
#
# Environment variables (all have sensible defaults):
#   REDIS_CONTAINER         Docker container name (default: redis)
#   REDIS_RDB_PATH          In-container path to dump.rdb (default: /data/dump.rdb)
#   REDIS_BGSAVE_TIMEOUT    Seconds to wait for BGSAVE to complete (default: 120)
#   RABBITMQ_CONTAINER      Docker container name (default: rabbitmq)
#   RABBITMQ_URL            RabbitMQ Management API base URL (default: http://localhost:15672)
#   RABBITMQ_USER           Management API username (default: guest)
#   RABBITMQ_PASS           Management API password (default: guest)
#   RABBITMQ_HEALTH_TIMEOUT Seconds to wait for RabbitMQ health check (default: 30)
#   BACKUP_DIR              Host directory for backups (default: /source/backups/medium)
#   BACKUP_RETENTION_DAYS   Days to keep old backups (default: 14)
#   PROJECT_ROOT            Repository / project root on the host
#   LOG_FILE                Log file path (default: /var/log/aithena-backup-medium.log)
#   DRY_RUN                 Set to 1 to skip actual file operations
#
# Exit codes:
#   0  All backups succeeded
#   1  Fatal error (missing tools, health check failure, backup failure)
#   2  Partial failure (some optional components unavailable — logged as warnings)
#
# See also: docs/prd/bcdr-plan.md §4.2 — Tier 3
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
REDIS_CONTAINER="${REDIS_CONTAINER:-redis}"
REDIS_RDB_PATH="${REDIS_RDB_PATH:-/data/dump.rdb}"
REDIS_BGSAVE_TIMEOUT="${REDIS_BGSAVE_TIMEOUT:-120}"
RABBITMQ_CONTAINER="${RABBITMQ_CONTAINER:-rabbitmq}"
RABBITMQ_URL="${RABBITMQ_URL:-http://localhost:15672}"
RABBITMQ_USER="${RABBITMQ_USER:-guest}"
RABBITMQ_PASS="${RABBITMQ_PASS:-guest}"
RABBITMQ_HEALTH_TIMEOUT="${RABBITMQ_HEALTH_TIMEOUT:-30}"
BACKUP_DIR="${BACKUP_DIR:-/source/backups/medium}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
PROJECT_ROOT="${PROJECT_ROOT:-/source/aithena}"
DRY_RUN="${DRY_RUN:-0}"

# Restrictive umask — backup files must not be world-readable
umask 077

# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------
_validate_positive_int() {
    local name="$1" value="$2"
    if ! [[ "$value" =~ ^[0-9]+$ ]] || [[ "$value" -lt 1 ]]; then
        echo "ERROR: ${name} must be a positive integer, got '${value}'" >&2
        exit 1
    fi
}

_validate_non_negative_int() {
    local name="$1" value="$2"
    if ! [[ "$value" =~ ^[0-9]+$ ]]; then
        echo "ERROR: ${name} must be a non-negative integer, got '${value}'" >&2
        exit 1
    fi
}

_validate_url() {
    local name="$1" value="$2"
    if ! [[ "$value" =~ ^https?:// ]]; then
        echo "ERROR: ${name} must be a valid HTTP(S) URL, got '${value}'" >&2
        exit 1
    fi
}

_validate_non_negative_int "BACKUP_RETENTION_DAYS"  "$BACKUP_RETENTION_DAYS"
_validate_positive_int     "REDIS_BGSAVE_TIMEOUT"   "$REDIS_BGSAVE_TIMEOUT"
_validate_positive_int     "RABBITMQ_HEALTH_TIMEOUT" "$RABBITMQ_HEALTH_TIMEOUT"
_validate_url              "RABBITMQ_URL"           "$RABBITMQ_URL"

TIMESTAMP="$(date -u +%Y%m%d-%H%M)"
LOG_FILE="${LOG_FILE:-/var/log/aithena-backup-medium.log}"
TMPDIR_BASE="${TMPDIR:-/tmp}"
WORK_DIR=""          # set in main, cleaned up by trap
EXIT_CODE=0          # escalated to 2 on non-fatal warnings

# --- Ensure log file is writable; fall back to project-local if not ---
_init_log() {
    mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
    if ! touch "$LOG_FILE" 2>/dev/null; then
        LOG_FILE="${PROJECT_ROOT}/backup-medium.log"
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
# check_redis_health — verify Redis container is running and responsive
# ---------------------------------------------------------------------------
check_redis_health() {
    log_info "Checking Redis health..."

    local response=""
    if response=$(docker exec "${REDIS_CONTAINER}" redis-cli PING 2>&1); then
        if [[ "$response" == "PONG" ]]; then
            log_info "Redis is healthy (PING → PONG)"
            return 0
        fi
    fi

    log_error "Redis health check failed: ${response}"
    return 1
}

# ---------------------------------------------------------------------------
# check_rabbitmq_health — verify RabbitMQ Management API is reachable
# ---------------------------------------------------------------------------
check_rabbitmq_health() {
    log_info "Checking RabbitMQ Management API health (timeout: ${RABBITMQ_HEALTH_TIMEOUT}s)..."

    local deadline=$((SECONDS + RABBITMQ_HEALTH_TIMEOUT))

    while [[ $SECONDS -lt $deadline ]]; do
        local response=""
        if response=$(curl -sf --max-time 10 \
            -u "${RABBITMQ_USER}:${RABBITMQ_PASS}" \
            "${RABBITMQ_URL}/api/healthchecks/node" 2>/dev/null); then
            if echo "$response" | grep -q '"status":"ok"'; then
                log_info "RabbitMQ Management API is healthy"
                return 0
            fi
        fi
        if [[ $SECONDS -lt $deadline ]]; then
            log_warn "RabbitMQ not ready, retrying in 5s..."
            sleep 5
        fi
    done

    log_error "RabbitMQ health check failed after ${RABBITMQ_HEALTH_TIMEOUT}s"
    return 1
}

# ---------------------------------------------------------------------------
# backup_redis — trigger BGSAVE and copy RDB dump from container
# ---------------------------------------------------------------------------
backup_redis() {
    local archive="${BACKUP_DIR}/redis-dump-${TIMESTAMP}.rdb"
    local compressed="${archive}.gz"
    local checksum="${compressed}.sha256"

    log_info "Starting Redis RDB backup"

    if [[ "$DRY_RUN" == "1" ]]; then
        log_info "[DRY_RUN] Would trigger BGSAVE and copy RDB dump"
        return 0
    fi

    # Record last save time before triggering BGSAVE
    local last_save=""
    last_save=$(docker exec "${REDIS_CONTAINER}" redis-cli LASTSAVE 2>&1) || {
        log_error "Failed to query Redis LASTSAVE: ${last_save}"
        return 1
    }

    # Trigger background save
    local bgsave_response=""
    bgsave_response=$(docker exec "${REDIS_CONTAINER}" redis-cli BGSAVE 2>&1) || {
        log_error "Failed to trigger Redis BGSAVE: ${bgsave_response}"
        return 1
    }
    log_info "BGSAVE triggered: ${bgsave_response}"

    # Wait for BGSAVE to complete by polling LASTSAVE
    local deadline=$((SECONDS + REDIS_BGSAVE_TIMEOUT))
    while [[ $SECONDS -lt $deadline ]]; do
        local current_save=""
        current_save=$(docker exec "${REDIS_CONTAINER}" redis-cli LASTSAVE 2>&1) || {
            log_warn "Failed to poll LASTSAVE, retrying..."
            sleep 2
            continue
        }
        if [[ "$current_save" != "$last_save" ]]; then
            log_info "BGSAVE completed (LASTSAVE changed: ${last_save} → ${current_save})"
            break
        fi
        if [[ $SECONDS -ge $deadline ]]; then
            log_error "BGSAVE did not complete within ${REDIS_BGSAVE_TIMEOUT}s"
            return 1
        fi
        sleep 2
    done

    # Copy RDB file from container to host working directory
    local stage_file="${WORK_DIR}/dump.rdb"
    docker cp "${REDIS_CONTAINER}:${REDIS_RDB_PATH}" "$stage_file" 2>&1 || {
        log_error "Failed to copy RDB dump from container '${REDIS_CONTAINER}:${REDIS_RDB_PATH}'"
        return 1
    }
    log_info "Copied RDB dump from container to staging"

    # Compress the RDB dump
    gzip -c "$stage_file" > "$compressed" || {
        log_error "Failed to compress RDB dump"
        return 1
    }

    # SHA-256 checksum sidecar
    sha256sum "$compressed" > "$checksum"
    log_info "Redis backup archived: ${compressed}"
    log_info "Checksum written: ${checksum}"

    # Clean staging file
    rm -f "$stage_file"
}

# ---------------------------------------------------------------------------
# backup_rabbitmq — export definitions via Management API
# ---------------------------------------------------------------------------
backup_rabbitmq() {
    local definitions_file="${BACKUP_DIR}/rabbitmq-definitions-${TIMESTAMP}.json"
    local compressed="${definitions_file}.gz"
    local checksum="${compressed}.sha256"

    log_info "Starting RabbitMQ definitions export"

    if [[ "$DRY_RUN" == "1" ]]; then
        log_info "[DRY_RUN] Would export RabbitMQ definitions via Management API"
        return 0
    fi

    # Export definitions via Management API
    local stage_file="${WORK_DIR}/definitions.json"
    local http_code=""
    http_code=$(curl -sf --max-time 60 -w "%{http_code}" -o "$stage_file" \
        -u "${RABBITMQ_USER}:${RABBITMQ_PASS}" \
        "${RABBITMQ_URL}/api/definitions" 2>&1) || {
        log_error "Failed to export RabbitMQ definitions (HTTP ${http_code})"
        return 1
    }

    # Validate the exported file is non-empty and valid JSON
    if [[ ! -s "$stage_file" ]]; then
        log_error "RabbitMQ definitions export returned empty response"
        return 1
    fi

    # Basic JSON validity check — definitions must contain rabbit_version key
    if ! grep -q '"rabbit_version"' "$stage_file"; then
        log_warn "RabbitMQ definitions export may be incomplete (missing rabbit_version key)"
        EXIT_CODE=2
    fi

    # Compress the definitions file
    gzip -c "$stage_file" > "$compressed" || {
        log_error "Failed to compress RabbitMQ definitions"
        return 1
    }

    # SHA-256 checksum sidecar
    sha256sum "$compressed" > "$checksum"
    log_info "RabbitMQ definitions archived: ${compressed}"
    log_info "Checksum written: ${checksum}"

    # Clean staging file
    rm -f "$stage_file"
}

# ---------------------------------------------------------------------------
# purge_old_backups — removes files older than $BACKUP_RETENTION_DAYS
# ---------------------------------------------------------------------------
purge_old_backups() {
    local dir="$1"
    local label="$2"

    log_info "Purging ${label} backups older than ${BACKUP_RETENTION_DAYS} days from ${dir}"

    if [[ ! -d "$dir" ]]; then
        log_info "No ${label} backup directory found — nothing to purge"
        return 0
    fi

    if [[ "$DRY_RUN" == "1" ]]; then
        local count
        count="$(find "$dir" -maxdepth 1 -type f \( -name '*.rdb.gz' -o -name '*.json.gz' -o -name '*.sha256' \) -mtime "+${BACKUP_RETENTION_DAYS}" | wc -l)"
        log_info "[DRY_RUN] Would purge ${count} ${label} file(s)"
        return 0
    fi

    local deleted=0
    while IFS= read -r -d '' file; do
        rm -f "$file"
        log_info "Purged: ${file}"
        ((deleted++)) || true
    done < <(find "$dir" -maxdepth 1 -type f \( -name '*.rdb.gz' -o -name '*.json.gz' -o -name '*.sha256' \) -mtime "+${BACKUP_RETENTION_DAYS}" -print0)

    log_info "Purged ${deleted} expired ${label} file(s)"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    # Concurrency guard — only one backup instance at a time
    local lock_file="${BACKUP_DIR}/.backup-medium.lock"
    mkdir -p "$BACKUP_DIR"
    exec 9>"$lock_file"
    if ! flock -n 9; then
        log_error "Another backup instance is already running (lock: ${lock_file})"
        exit 1
    fi

    log_info "========== Aithena Medium-Priority Backup START (${TIMESTAMP}) =========="
    log_info "REDIS_CONTAINER=${REDIS_CONTAINER}  RABBITMQ_URL=${RABBITMQ_URL}  RETENTION=${BACKUP_RETENTION_DAYS}d"
    log_info "BACKUP_DIR=${BACKUP_DIR}"

    # --- Pre-flight checks ---
    require_cmd curl
    require_cmd gzip
    require_cmd sha256sum
    require_cmd find
    require_cmd docker

    # --- Temp working directory (cleaned up by trap) ---
    WORK_DIR="$(mktemp -d "${TMPDIR_BASE}/aithena-backup-medium-XXXXXX")"
    log_info "Work directory: ${WORK_DIR}"

    # --- Backup Redis ---
    if check_redis_health; then
        backup_redis || exit 1
    else
        log_warn "Redis unavailable — skipping Redis backup"
        EXIT_CODE=2
    fi

    # --- Backup RabbitMQ ---
    if check_rabbitmq_health; then
        backup_rabbitmq || exit 1
    else
        log_warn "RabbitMQ unavailable — skipping RabbitMQ backup"
        EXIT_CODE=2
    fi

    # --- Retention purge ---
    purge_old_backups "$BACKUP_DIR" "medium-tier"

    log_info "========== Aithena Medium-Priority Backup END   (exit=${EXIT_CODE}) =========="
    return "$EXIT_CODE"
}

main "$@"

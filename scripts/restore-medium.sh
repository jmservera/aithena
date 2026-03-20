#!/usr/bin/env bash
# =============================================================================
# Aithena BCDR — Tier 3: Medium-Priority Data Restore (Redis + RabbitMQ)
# =============================================================================
# Restores Redis RDB snapshots (copy into container + SHUTDOWN NOSAVE + restart)
# and RabbitMQ definitions (via Management API import) from a backup directory
# produced by backup-medium.sh.
#
# Usage:
#   ./scripts/restore-medium.sh                           # restore all medium-tier
#   COMPONENT=redis    ./scripts/restore-medium.sh        # restore only Redis
#   COMPONENT=rabbitmq ./scripts/restore-medium.sh        # restore only RabbitMQ
#   DRY_RUN=1          ./scripts/restore-medium.sh        # preview without writing
#
# Environment variables (all have sensible defaults):
#   RESTORE_FROM            Backup directory to restore from (required)
#   COMPONENT               Component filter: redis|rabbitmq|all (default: all)
#   REDIS_CONTAINER         Docker container name (default: redis)
#   REDIS_RDB_PATH          In-container path to dump.rdb (default: /data/dump.rdb)
#   RABBITMQ_CONTAINER      Docker container name (default: rabbitmq)
#   RABBITMQ_URL            RabbitMQ Management API base URL (default: http://localhost:15672)
#   RABBITMQ_USER           Management API username (default: guest)
#   RABBITMQ_PASS           Management API password (default: guest)
#   RABBITMQ_HEALTH_TIMEOUT Seconds to wait for RabbitMQ health check (default: 30)
#   PROJECT_ROOT            Repository / project root on the host
#   LOG_FILE                Log file path (default: /var/log/aithena-restore-medium.log)
#   DRY_RUN                 Set to 1 to skip actual file operations
#
# Exit codes:
#   0  All restores succeeded
#   1  Fatal error (missing tools, backup not found, restore failure)
#   2  Partial failure (some services unavailable — logged as warnings)
#
# See also: docs/prd/bcdr-plan.md §4.2 — Tier 3
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
RESTORE_FROM="${RESTORE_FROM:?RESTORE_FROM must be set to the backup directory}"
COMPONENT="${COMPONENT:-all}"
REDIS_CONTAINER="${REDIS_CONTAINER:-redis}"
REDIS_RDB_PATH="${REDIS_RDB_PATH:-/data/dump.rdb}"
RABBITMQ_CONTAINER="${RABBITMQ_CONTAINER:-rabbitmq}"
RABBITMQ_URL="${RABBITMQ_URL:-http://localhost:15672}"
RABBITMQ_USER="${RABBITMQ_USER:-guest}"
RABBITMQ_PASS="${RABBITMQ_PASS:-guest}"
RABBITMQ_HEALTH_TIMEOUT="${RABBITMQ_HEALTH_TIMEOUT:-30}"
PROJECT_ROOT="${PROJECT_ROOT:-/source/aithena}"
DRY_RUN="${DRY_RUN:-0}"

# Restrictive umask — restored files must not be world-readable
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

_validate_url() {
    local name="$1" value="$2"
    if ! [[ "$value" =~ ^https?:// ]]; then
        echo "ERROR: ${name} must be a valid HTTP(S) URL, got '${value}'" >&2
        exit 1
    fi
}

_validate_positive_int "RABBITMQ_HEALTH_TIMEOUT" "$RABBITMQ_HEALTH_TIMEOUT"
_validate_url          "RABBITMQ_URL"            "$RABBITMQ_URL"

TIMESTAMP="$(date -u +%Y%m%d-%H%M)"
LOG_FILE="${LOG_FILE:-/var/log/aithena-restore-medium.log}"
TMPDIR_BASE="${TMPDIR:-/tmp}"
WORK_DIR=""          # set in main, cleaned up by trap
EXIT_CODE=0          # escalated to 2 on non-fatal warnings

# --- Ensure log file is writable; fall back to project-local if not ---
_init_log() {
    mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
    if ! touch "$LOG_FILE" 2>/dev/null; then
        LOG_FILE="${PROJECT_ROOT}/restore-medium.log"
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
# restore_redis — decompress RDB and copy into container
# ---------------------------------------------------------------------------
restore_redis() {
    log_info "Starting Redis RDB restore..."

    local compressed
    compressed="$(find_latest_backup "$RESTORE_FROM" "redis-dump-*.rdb.gz")"

    if [[ -z "$compressed" ]]; then
        log_error "No Redis backup found in ${RESTORE_FROM} matching redis-dump-*.rdb.gz"
        return 1
    fi

    log_info "Found Redis backup: ${compressed}"

    # Verify checksum before restore
    verify_checksum "$compressed" || {
        log_error "Redis backup integrity check failed — aborting restore"
        return 1
    }

    if [[ "$DRY_RUN" == "1" ]]; then
        log_info "[DRY_RUN] Would restore Redis RDB from ${compressed}"
        return 0
    fi

    # Decompress RDB to staging
    local stage_file="${WORK_DIR}/dump.rdb"
    gzip -dc "$compressed" > "$stage_file" || {
        log_error "Failed to decompress Redis RDB: ${compressed}"
        return 1
    }
    log_info "Decompressed Redis RDB to staging"

    # Copy RDB into container
    docker cp "$stage_file" "${REDIS_CONTAINER}:${REDIS_RDB_PATH}" 2>&1 || {
        log_error "Failed to copy RDB dump into container '${REDIS_CONTAINER}:${REDIS_RDB_PATH}'"
        return 1
    }
    log_info "Copied RDB dump into Redis container"

    # Restart Redis to load the new RDB
    docker restart "${REDIS_CONTAINER}" 2>&1 || {
        log_error "Failed to restart Redis container"
        return 1
    }

    # Wait briefly and verify Redis is back
    sleep 3
    local response=""
    if response=$(docker exec "${REDIS_CONTAINER}" redis-cli PING 2>&1); then
        if [[ "$response" == "PONG" ]]; then
            log_info "Redis restarted and healthy after restore"
        else
            log_warn "Redis restarted but health check unexpected: ${response}"
            EXIT_CODE=2
        fi
    else
        log_warn "Redis may still be loading RDB — verify manually"
        EXIT_CODE=2
    fi

    rm -f "$stage_file"
}

# ---------------------------------------------------------------------------
# restore_rabbitmq — import definitions via Management API
# ---------------------------------------------------------------------------
restore_rabbitmq() {
    log_info "Starting RabbitMQ definitions restore..."

    local compressed
    compressed="$(find_latest_backup "$RESTORE_FROM" "rabbitmq-definitions-*.json.gz")"

    if [[ -z "$compressed" ]]; then
        log_error "No RabbitMQ backup found in ${RESTORE_FROM} matching rabbitmq-definitions-*.json.gz"
        return 1
    fi

    log_info "Found RabbitMQ backup: ${compressed}"

    # Verify checksum before restore
    verify_checksum "$compressed" || {
        log_error "RabbitMQ backup integrity check failed — aborting restore"
        return 1
    }

    if [[ "$DRY_RUN" == "1" ]]; then
        log_info "[DRY_RUN] Would restore RabbitMQ definitions from ${compressed}"
        return 0
    fi

    # Decompress definitions to staging
    local stage_file="${WORK_DIR}/definitions.json"
    gzip -dc "$compressed" > "$stage_file" || {
        log_error "Failed to decompress RabbitMQ definitions: ${compressed}"
        return 1
    }

    # Validate JSON structure
    if command -v python3 &>/dev/null; then
        if ! python3 -c "import json; d=json.load(open('$stage_file')); assert 'rabbit_version' in d" 2>/dev/null; then
            log_warn "RabbitMQ definitions may be incomplete or invalid JSON"
            EXIT_CODE=2
        fi
    elif ! grep -q '"rabbit_version"' "$stage_file"; then
        log_warn "RabbitMQ definitions may be incomplete (missing rabbit_version key)"
        EXIT_CODE=2
    fi

    # Import definitions via Management API
    local http_code=""
    http_code=$(curl -sf --max-time 60 -w "%{http_code}" -o /dev/null \
        -u "${RABBITMQ_USER}:${RABBITMQ_PASS}" \
        -H "Content-Type: application/json" \
        -X POST \
        -d "@${stage_file}" \
        "${RABBITMQ_URL}/api/definitions" 2>/dev/null) || {
        log_error "Failed to import RabbitMQ definitions (HTTP ${http_code})"
        return 1
    }

    if [[ "$http_code" =~ ^2 ]]; then
        log_info "RabbitMQ definitions imported successfully (HTTP ${http_code})"
    else
        log_error "RabbitMQ definitions import failed (HTTP ${http_code})"
        return 1
    fi

    rm -f "$stage_file"
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
    local lock_file="${lock_dir}/.restore-medium.lock"
    exec 9>"$lock_file"
    if ! flock -n 9; then
        log_error "Another restore instance is already running (lock: ${lock_file})"
        exit 1
    fi

    log_info "========== Aithena Medium-Priority Restore START (${TIMESTAMP}) =========="
    log_info "RESTORE_FROM=${RESTORE_FROM}  COMPONENT=${COMPONENT}  DRY_RUN=${DRY_RUN}"
    log_info "REDIS_CONTAINER=${REDIS_CONTAINER}  RABBITMQ_URL=${RABBITMQ_URL}"

    # --- Pre-flight checks ---
    require_cmd curl
    require_cmd gzip
    require_cmd sha256sum
    require_cmd find
    require_cmd docker

    if [[ ! -d "$RESTORE_FROM" ]]; then
        log_error "Backup directory not found: ${RESTORE_FROM}"
        exit 1
    fi

    # --- Temp working directory (cleaned up by trap) ---
    WORK_DIR="$(mktemp -d "${TMPDIR_BASE}/aithena-restore-medium-XXXXXX")"
    log_info "Work directory: ${WORK_DIR}"

    # --- Restore components based on COMPONENT filter ---
    case "$COMPONENT" in
        all)
            if check_redis_health; then
                restore_redis || exit 1
            else
                log_warn "Redis unavailable — skipping Redis restore"
                EXIT_CODE=2
            fi

            if check_rabbitmq_health; then
                restore_rabbitmq || exit 1
            else
                log_warn "RabbitMQ unavailable — skipping RabbitMQ restore"
                EXIT_CODE=2
            fi
            ;;
        redis)
            check_redis_health || exit 1
            restore_redis || exit 1
            ;;
        rabbitmq)
            check_rabbitmq_health || exit 1
            restore_rabbitmq || exit 1
            ;;
        *)
            log_info "No medium-tier components requested (component=${COMPONENT})"
            ;;
    esac

    log_info "========== Aithena Medium-Priority Restore END   (exit=${EXIT_CODE}) =========="
    return "$EXIT_CODE"
}

main "$@"

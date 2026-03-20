#!/usr/bin/env bash
# =============================================================================
# Aithena BCDR — Tier 2: High-Priority Data Backup (Solr + ZooKeeper)
# =============================================================================
# Backs up Solr index snapshots (via Collections API BACKUP) and ZooKeeper
# ensemble state (tar + compression of volume directories).  Designed to run
# daily at 2 AM UTC via cron on the HOST.
#
# Usage:
#   ./scripts/backup-high.sh              # normal run
#   DRY_RUN=1 ./scripts/backup-high.sh    # log actions without writing
#
# Environment variables (all have sensible defaults):
#   SOLR_URL                Solr HTTP base URL (default: http://localhost:8983)
#   SOLR_COLLECTION         Collection to backup (default: books)
#   SOLR_BACKUP_LOCATION    In-container backup path (default: /var/solr/backups)
#   SOLR_CONTAINER          Docker container name for retrieval (default: solr)
#   SOLR_BACKUP_DIR         Host directory for Solr backups (default: /source/backups/high)
#   ZK_BACKUP_DIR           Host directory for ZK backups (default: /source/backups/zookeeper)
#   ZK_VOLUME_BASE          Host path to ZK volume root (default: /source/volumes)
#   ZK_NODES                Number of ZooKeeper nodes (default: 3)
#   BACKUP_RETENTION_DAYS   Days to keep old backups (default: 30)
#   SOLR_HEALTH_TIMEOUT     Seconds to wait for Solr health check (default: 30)
#   SOLR_BACKUP_TIMEOUT     Max seconds for Solr BACKUP API call (default: 600)
#   PROJECT_ROOT            Repository / project root on the host
#   LOG_FILE                Log file path (default: /var/log/aithena-backup-high.log)
#   DRY_RUN                 Set to 1 to skip actual file operations
#
# Exit codes:
#   0  All backups succeeded
#   1  Fatal error (missing tools, health check failure, backup failure)
#   2  Partial failure (some optional components missing — logged as warnings)
#
# See also: docs/prd/bcdr-plan.md §4.1 — Tier 2
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SOLR_URL="${SOLR_URL:-http://localhost:8983}"
SOLR_COLLECTION="${SOLR_COLLECTION:-books}"
SOLR_BACKUP_LOCATION="${SOLR_BACKUP_LOCATION:-/var/solr/backups}"
SOLR_CONTAINER="${SOLR_CONTAINER:-solr}"
SOLR_BACKUP_DIR="${SOLR_BACKUP_DIR:-/source/backups/high}"
ZK_BACKUP_DIR="${ZK_BACKUP_DIR:-/source/backups/zookeeper}"
ZK_VOLUME_BASE="${ZK_VOLUME_BASE:-/source/volumes}"
ZK_NODES="${ZK_NODES:-3}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
SOLR_HEALTH_TIMEOUT="${SOLR_HEALTH_TIMEOUT:-30}"
SOLR_BACKUP_TIMEOUT="${SOLR_BACKUP_TIMEOUT:-600}"
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

_validate_non_negative_int "BACKUP_RETENTION_DAYS" "$BACKUP_RETENTION_DAYS"
_validate_positive_int     "ZK_NODES"              "$ZK_NODES"
_validate_positive_int     "SOLR_HEALTH_TIMEOUT"   "$SOLR_HEALTH_TIMEOUT"
_validate_positive_int     "SOLR_BACKUP_TIMEOUT"   "$SOLR_BACKUP_TIMEOUT"
_validate_url              "SOLR_URL"              "$SOLR_URL"

TIMESTAMP="$(date -u +%Y%m%d-%H%M)"
LOG_FILE="${LOG_FILE:-/var/log/aithena-backup-high.log}"
TMPDIR_BASE="${TMPDIR:-/tmp}"
WORK_DIR=""          # set in main, cleaned up by trap
EXIT_CODE=0          # escalated to 2 on non-fatal warnings

# --- Ensure log file is writable; fall back to project-local if not ---
_init_log() {
    mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
    if ! touch "$LOG_FILE" 2>/dev/null; then
        LOG_FILE="${PROJECT_ROOT}/backup-high.log"
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
# check_solr_health — verify Solr cluster is up and has live nodes
# ---------------------------------------------------------------------------
check_solr_health() {
    log_info "Checking Solr cluster health (timeout: ${SOLR_HEALTH_TIMEOUT}s)..."

    local deadline=$((SECONDS + SOLR_HEALTH_TIMEOUT))

    while [[ $SECONDS -lt $deadline ]]; do
        local response=""
        if response=$(curl -sf --max-time 10 \
            "${SOLR_URL}/solr/admin/collections?action=CLUSTERSTATUS&wt=json" 2>/dev/null); then
            # Look for live_nodes array with at least one entry
            if echo "$response" | grep -q '"live_nodes"'; then
                local live_count
                live_count=$(echo "$response" | grep -co '_solr"' || true)
                if [[ "$live_count" -ge 1 ]]; then
                    log_info "Solr cluster healthy: ${live_count} live node(s)"
                    return 0
                fi
            fi
        fi
        if [[ $SECONDS -lt $deadline ]]; then
            log_warn "Solr not ready, retrying in 5s..."
            sleep 5
        fi
    done

    log_error "Solr cluster health check failed after ${SOLR_HEALTH_TIMEOUT}s"
    return 1
}

# ---------------------------------------------------------------------------
# backup_solr — trigger Collections API BACKUP and retrieve to host
# ---------------------------------------------------------------------------
backup_solr() {
    local backup_name="${SOLR_COLLECTION}-${TIMESTAMP}"
    local archive="${SOLR_BACKUP_DIR}/${backup_name}.tar.gz"
    local checksum="${archive}.sha256"

    log_info "Starting Solr collection backup: ${backup_name}"

    if [[ "$DRY_RUN" == "1" ]]; then
        log_info "[DRY_RUN] Would backup Solr collection '${SOLR_COLLECTION}' as '${backup_name}'"
        return 0
    fi

    # Trigger backup via Solr Collections API
    local response=""
    response=$(curl -sf --max-time "$SOLR_BACKUP_TIMEOUT" \
        "${SOLR_URL}/solr/admin/collections?action=BACKUP&name=${backup_name}&collection=${SOLR_COLLECTION}&location=${SOLR_BACKUP_LOCATION}&wt=json" 2>&1) || {
        log_error "Solr BACKUP API call failed: ${response}"
        return 1
    }

    if ! echo "$response" | grep -q '"status":0'; then
        log_error "Solr BACKUP API returned error: ${response}"
        return 1
    fi
    log_info "Solr BACKUP API returned success for ${backup_name}"

    # Copy backup from Solr container to host working directory
    local stage_dir="${WORK_DIR}/${backup_name}"
    mkdir -p "$stage_dir"

    docker cp "${SOLR_CONTAINER}:${SOLR_BACKUP_LOCATION}/${backup_name}/." "$stage_dir/" 2>&1 || {
        log_error "Failed to copy Solr backup from container '${SOLR_CONTAINER}'"
        return 1
    }
    log_info "Copied Solr backup from container to staging"

    # Create compressed archive
    tar -czf "$archive" -C "$WORK_DIR" "$backup_name" 2>&1 || {
        log_error "Failed to create Solr backup archive: ${archive}"
        return 1
    }

    # SHA-256 checksum sidecar
    sha256sum "$archive" > "$checksum"
    log_info "Solr backup archived: ${archive}"
    log_info "Checksum written: ${checksum}"

    # Clean staging directory
    rm -rf "$stage_dir"
}

# ---------------------------------------------------------------------------
# backup_zookeeper — tar + compress each ZK node's data directories
# ---------------------------------------------------------------------------
backup_zookeeper() {
    log_info "Starting ZooKeeper backup for ${ZK_NODES} node(s)"

    local i
    for i in $(seq 1 "$ZK_NODES"); do
        local src="${ZK_VOLUME_BASE}/zoo-data${i}"
        local archive="${ZK_BACKUP_DIR}/zoo-data${i}-${TIMESTAMP}.tar.gz"
        local checksum="${archive}.sha256"

        if [[ ! -d "$src" ]]; then
            log_warn "ZooKeeper data directory not found: ${src} — skipping node ${i}"
            EXIT_CODE=2
            continue
        fi

        if [[ "$DRY_RUN" == "1" ]]; then
            log_info "[DRY_RUN] Would backup ${src} → ${archive}"
            continue
        fi

        tar --sparse -czf "$archive" -C "$ZK_VOLUME_BASE" "zoo-data${i}" 2>&1 || {
            log_error "Failed to tar ZooKeeper node ${i} data from ${src}"
            return 1
        }

        sha256sum "$archive" > "$checksum"
        log_info "ZooKeeper node ${i} backed up: ${archive}"
        log_info "Checksum written: ${checksum}"
    done
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
        count="$(find "$dir" -maxdepth 1 -type f \( -name '*.tar.gz' -o -name '*.sha256' \) -mtime "+${BACKUP_RETENTION_DAYS}" | wc -l)"
        log_info "[DRY_RUN] Would purge ${count} ${label} file(s)"
        return 0
    fi

    local deleted=0
    while IFS= read -r -d '' file; do
        rm -f "$file"
        log_info "Purged: ${file}"
        ((deleted++)) || true
    done < <(find "$dir" -maxdepth 1 -type f \( -name '*.tar.gz' -o -name '*.sha256' \) -mtime "+${BACKUP_RETENTION_DAYS}" -print0)

    log_info "Purged ${deleted} expired ${label} file(s)"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    # Concurrency guard — only one backup instance at a time
    local lock_file="${SOLR_BACKUP_DIR}/.backup-high.lock"
    mkdir -p "$SOLR_BACKUP_DIR" "$ZK_BACKUP_DIR"
    exec 9>"$lock_file"
    if ! flock -n 9; then
        log_error "Another backup instance is already running (lock: ${lock_file})"
        exit 1
    fi

    log_info "========== Aithena High-Priority Backup START (${TIMESTAMP}) =========="
    log_info "SOLR_URL=${SOLR_URL}  COLLECTION=${SOLR_COLLECTION}  RETENTION=${BACKUP_RETENTION_DAYS}d"
    log_info "SOLR_BACKUP_DIR=${SOLR_BACKUP_DIR}  ZK_BACKUP_DIR=${ZK_BACKUP_DIR}"

    # --- Pre-flight checks ---
    require_cmd curl
    require_cmd tar
    require_cmd sha256sum
    require_cmd find
    require_cmd docker

    # --- Temp working directory (cleaned up by trap) ---
    WORK_DIR="$(mktemp -d "${TMPDIR_BASE}/aithena-backup-high-XXXXXX")"
    log_info "Work directory: ${WORK_DIR}"

    # --- Verify Solr cluster health before starting ---
    check_solr_health || exit 1

    # --- Backup Solr collection ---
    backup_solr || exit 1

    # --- Backup ZooKeeper data ---
    backup_zookeeper || exit 1

    # --- Retention purge ---
    purge_old_backups "$SOLR_BACKUP_DIR" "Solr"
    purge_old_backups "$ZK_BACKUP_DIR" "ZooKeeper"

    log_info "========== Aithena High-Priority Backup END   (exit=${EXIT_CODE}) =========="
    return "$EXIT_CODE"
}

main "$@"

#!/usr/bin/env bash
# =============================================================================
# Aithena BCDR — Tier 2: High-Priority Data Restore (Solr + ZooKeeper)
# =============================================================================
# Restores Solr index snapshots (via Collections API RESTORE) and ZooKeeper
# ensemble state (extract tar archives to volume directories) from a backup
# directory produced by backup-high.sh.
#
# Usage:
#   ./scripts/restore-high.sh                         # restore all high-tier
#   COMPONENT=solr ./scripts/restore-high.sh          # restore only Solr
#   COMPONENT=zk   ./scripts/restore-high.sh          # restore only ZooKeeper
#   DRY_RUN=1      ./scripts/restore-high.sh          # preview without writing
#
# Environment variables (all have sensible defaults):
#   RESTORE_FROM            Backup directory for Solr backups (required)
#   ZK_RESTORE_FROM         Backup directory for ZK backups (default: derived from RESTORE_FROM)
#   COMPONENT               Component filter: solr|zk|all (default: all)
#   SOLR_URL                Solr HTTP base URL (default: http://localhost:8983)
#   SOLR_COLLECTION         Collection to restore (default: books)
#   SOLR_BACKUP_LOCATION    In-container backup path (default: /var/solr/backups)
#   SOLR_CONTAINER          Docker container name (default: solr)
#   SOLR_HEALTH_TIMEOUT     Seconds to wait for Solr health check (default: 30)
#   SOLR_RESTORE_TIMEOUT    Max seconds for Solr RESTORE API call (default: 600)
#   SEARCH_API_URL          Search API base URL for post-restore verification (default: http://localhost:8080)
#   SEARCH_VERIFY_QUERY     Query string for search verification (default: *)
#   ZK_VOLUME_BASE          Host path to ZK volume root (default: /source/volumes)
#   ZK_NODES                Number of ZooKeeper nodes (default: 3)
#   PROJECT_ROOT            Repository / project root on the host
#   LOG_FILE                Log file path (default: /var/log/aithena-restore-high.log)
#   DRY_RUN                 Set to 1 to skip actual file operations
#
# Exit codes:
#   0  All restores succeeded
#   1  Fatal error (missing tools, backup not found, restore failure)
#   2  Partial failure (some optional components missing — logged as warnings)
#
# See also: docs/prd/bcdr-plan.md §4.2 — Tier 2
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
RESTORE_FROM="${RESTORE_FROM:?RESTORE_FROM must be set to the Solr backup directory}"
ZK_RESTORE_FROM="${ZK_RESTORE_FROM:-}"
COMPONENT="${COMPONENT:-all}"
SOLR_URL="${SOLR_URL:-http://localhost:8983}"
SOLR_COLLECTION="${SOLR_COLLECTION:-books}"
SOLR_BACKUP_LOCATION="${SOLR_BACKUP_LOCATION:-/var/solr/backups}"
SOLR_CONTAINER="${SOLR_CONTAINER:-solr}"
SOLR_HEALTH_TIMEOUT="${SOLR_HEALTH_TIMEOUT:-30}"
SOLR_RESTORE_TIMEOUT="${SOLR_RESTORE_TIMEOUT:-600}"
SEARCH_API_URL="${SEARCH_API_URL:-http://localhost:8080}"
SEARCH_VERIFY_QUERY="${SEARCH_VERIFY_QUERY:-*}"
ZK_VOLUME_BASE="${ZK_VOLUME_BASE:-/source/volumes}"
ZK_NODES="${ZK_NODES:-3}"
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

_validate_positive_int "ZK_NODES"             "$ZK_NODES"
_validate_positive_int "SOLR_HEALTH_TIMEOUT"  "$SOLR_HEALTH_TIMEOUT"
_validate_positive_int "SOLR_RESTORE_TIMEOUT" "$SOLR_RESTORE_TIMEOUT"
_validate_url          "SOLR_URL"             "$SOLR_URL"

TIMESTAMP="$(date -u +%Y%m%d-%H%M)"
LOG_FILE="${LOG_FILE:-/var/log/aithena-restore-high.log}"
TMPDIR_BASE="${TMPDIR:-/tmp}"
WORK_DIR=""          # set in main, cleaned up by trap
EXIT_CODE=0          # escalated to 2 on non-fatal warnings

# --- Ensure log file is writable; fall back to project-local if not ---
_init_log() {
    mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
    if ! touch "$LOG_FILE" 2>/dev/null; then
        LOG_FILE="${PROJECT_ROOT}/restore-high.log"
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
# check_solr_health — verify Solr cluster is up and has live nodes
# ---------------------------------------------------------------------------
check_solr_health() {
    log_info "Checking Solr cluster health (timeout: ${SOLR_HEALTH_TIMEOUT}s)..."

    local deadline=$((SECONDS + SOLR_HEALTH_TIMEOUT))

    while [[ $SECONDS -lt $deadline ]]; do
        local response=""
        if response=$(curl -sf --max-time 10 \
            "${SOLR_URL}/solr/admin/collections?action=CLUSTERSTATUS&wt=json" 2>/dev/null); then
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
# verify_search_api — call the search API after restore and validate results
# ---------------------------------------------------------------------------
verify_search_api() {
    log_info "Verifying search API at ${SEARCH_API_URL}..."

    # Step 1: Check the health endpoint is reachable
    local health_response=""
    health_response=$(curl -sf --max-time 15 "${SEARCH_API_URL}/health" 2>/dev/null) || {
        log_error "Search API health check FAILED: ${SEARCH_API_URL}/health unreachable"
        return 1
    }
    log_info "Search API health endpoint reachable"

    # Step 2: Call the search endpoint with a test query and verify the response
    local search_response=""
    local http_code=""
    http_code=$(curl -sf --max-time 30 -w "%{http_code}" \
        -o "${WORK_DIR}/search_verify.json" \
        "${SEARCH_API_URL}/v1/search?q=${SEARCH_VERIFY_QUERY}&page_size=1" 2>/dev/null) || {
        log_error "Search API verification FAILED: request to /v1/search returned HTTP ${http_code}"
        return 1
    }

    if [[ ! "$http_code" =~ ^2 ]]; then
        log_error "Search API verification FAILED: /v1/search returned HTTP ${http_code}"
        return 1
    fi

    # Step 3: Validate the response contains expected structure (total field)
    if command -v python3 &>/dev/null; then
        local total=""
        total=$(python3 -c "
import json, sys
try:
    d = json.load(open('${WORK_DIR}/search_verify.json'))
    print(d.get('total', d.get('numFound', -1)))
except Exception as e:
    print(-1, file=sys.stderr)
    sys.exit(1)
" 2>/dev/null) || total="-1"

        if [[ "$total" == "-1" ]]; then
            log_error "Search API verification FAILED: response is not valid JSON or missing total field"
            return 1
        fi
        log_info "Search API verified: /v1/search returned HTTP ${http_code}, total=${total} result(s)"
    elif grep -q '"total"' "${WORK_DIR}/search_verify.json" 2>/dev/null || \
         grep -q '"numFound"' "${WORK_DIR}/search_verify.json" 2>/dev/null; then
        log_info "Search API verified: /v1/search returned HTTP ${http_code} with results"
    else
        log_error "Search API verification FAILED: response missing expected result fields"
        return 1
    fi

    rm -f "${WORK_DIR}/search_verify.json"
}

# ---------------------------------------------------------------------------
# restore_solr — extract archive, copy to container, trigger RESTORE API
# ---------------------------------------------------------------------------
restore_solr() {
    log_info "Starting Solr collection restore..."

    local archive
    archive="$(find_latest_backup "$RESTORE_FROM" "${SOLR_COLLECTION}-*.tar.gz")"

    if [[ -z "$archive" ]]; then
        log_error "No Solr backup archive found in ${RESTORE_FROM} matching ${SOLR_COLLECTION}-*.tar.gz"
        return 1
    fi

    log_info "Found Solr backup: ${archive}"

    # Verify checksum before restore
    verify_checksum "$archive" || {
        log_error "Solr backup integrity check failed — aborting restore"
        return 1
    }

    if [[ "$DRY_RUN" == "1" ]]; then
        log_info "[DRY_RUN] Would restore Solr collection '${SOLR_COLLECTION}' from ${archive}"
        return 0
    fi

    # Extract archive to staging directory
    local backup_name
    backup_name="$(tar -tzf "$archive" 2>/dev/null | head -1 | cut -d/ -f1)"
    if [[ -z "$backup_name" ]]; then
        log_error "Cannot determine backup name from archive: ${archive}"
        return 1
    fi

    tar -xzf "$archive" -C "$WORK_DIR" || {
        log_error "Failed to extract Solr backup archive: ${archive}"
        return 1
    }
    log_info "Extracted Solr backup: ${backup_name}"

    # Copy backup data into Solr container
    docker cp "${WORK_DIR}/${backup_name}/." "${SOLR_CONTAINER}:${SOLR_BACKUP_LOCATION}/${backup_name}/" 2>&1 || {
        log_error "Failed to copy Solr backup into container '${SOLR_CONTAINER}'"
        return 1
    }
    log_info "Copied backup into Solr container at ${SOLR_BACKUP_LOCATION}/${backup_name}"

    # Delete existing collection before restore (if it exists)
    local delete_response=""
    delete_response=$(curl -sf --max-time 30 \
        "${SOLR_URL}/solr/admin/collections?action=DELETE&name=${SOLR_COLLECTION}&wt=json" 2>&1) || {
        log_warn "Could not delete existing collection '${SOLR_COLLECTION}' (may not exist): ${delete_response}"
    }

    # Trigger restore via Solr Collections API
    local response=""
    response=$(curl -sf --max-time "$SOLR_RESTORE_TIMEOUT" \
        "${SOLR_URL}/solr/admin/collections?action=RESTORE&name=${backup_name}&collection=${SOLR_COLLECTION}&location=${SOLR_BACKUP_LOCATION}&wt=json" 2>&1) || {
        log_error "Solr RESTORE API call failed: ${response}"
        return 1
    }

    if ! echo "$response" | grep -q '"status":0'; then
        log_error "Solr RESTORE API returned error: ${response}"
        return 1
    fi
    log_info "Solr RESTORE API returned success for ${SOLR_COLLECTION}"

    # Post-restore verification — check collection exists in cluster status
    sleep 5
    local status_response=""
    status_response=$(curl -sf --max-time 30 \
        "${SOLR_URL}/solr/admin/collections?action=CLUSTERSTATUS&wt=json" 2>/dev/null) || {
        log_error "Post-restore verification FAILED: cannot reach Solr cluster status API"
        return 1
    }

    if echo "$status_response" | grep -q "\"${SOLR_COLLECTION}\""; then
        log_info "Post-restore verification: collection '${SOLR_COLLECTION}' present in cluster"
    else
        log_error "Post-restore verification FAILED: collection '${SOLR_COLLECTION}' not found in cluster"
        return 1
    fi

    # Clean up on-node restore data
    docker exec "${SOLR_CONTAINER}" rm -rf "${SOLR_BACKUP_LOCATION}/${backup_name}" 2>/dev/null || \
        log_warn "Could not clean up restore data at ${SOLR_BACKUP_LOCATION}/${backup_name}"

    # Clean staging directory
    rm -rf "${WORK_DIR:?}/${backup_name}"
}

# ---------------------------------------------------------------------------
# restore_zookeeper — extract tar archives to volume directories
# ---------------------------------------------------------------------------
restore_zookeeper() {
    log_info "Starting ZooKeeper restore for ${ZK_NODES} node(s)"

    local zk_dir="${ZK_RESTORE_FROM:-${RESTORE_FROM}}"
    local i
    local restored=0

    for i in $(seq 1 "$ZK_NODES"); do
        local archive
        archive="$(find_latest_backup "$zk_dir" "zoo-data${i}-*.tar.gz")"

        if [[ -z "$archive" ]]; then
            log_warn "No ZooKeeper backup found for node ${i} in ${zk_dir} — skipping"
            EXIT_CODE=2
            continue
        fi

        log_info "Found ZK node ${i} backup: ${archive}"

        # Verify checksum
        verify_checksum "$archive" || {
            log_error "ZK node ${i} backup integrity check failed — skipping"
            EXIT_CODE=2
            continue
        }

        if [[ "$DRY_RUN" == "1" ]]; then
            log_info "[DRY_RUN] Would restore ZK node ${i} from ${archive} → ${ZK_VOLUME_BASE}/zoo-data${i}"
            continue
        fi

        local dest="${ZK_VOLUME_BASE}/zoo-data${i}"

        # Remove existing data before restore
        if [[ -d "$dest" ]]; then
            rm -rf "$dest"
            log_info "Removed existing ZK node ${i} data at ${dest}"
        fi

        # Extract archive
        tar -xzf "$archive" -C "$ZK_VOLUME_BASE" || {
            log_error "Failed to extract ZK node ${i} backup: ${archive}"
            return 1
        }

        log_info "ZooKeeper node ${i} restored to ${dest}"
        ((restored++)) || true
    done

    if [[ "$DRY_RUN" != "1" ]]; then
        log_info "ZooKeeper restore complete: ${restored}/${ZK_NODES} node(s) restored"
    fi
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
    local lock_file="${lock_dir}/.restore-high.lock"
    exec 9>"$lock_file"
    if ! flock -n 9; then
        log_error "Another restore instance is already running (lock: ${lock_file})"
        exit 1
    fi

    log_info "========== Aithena High-Priority Restore START (${TIMESTAMP}) =========="
    log_info "RESTORE_FROM=${RESTORE_FROM}  COMPONENT=${COMPONENT}  DRY_RUN=${DRY_RUN}"
    log_info "SOLR_URL=${SOLR_URL}  COLLECTION=${SOLR_COLLECTION}"

    # --- Pre-flight checks ---
    require_cmd curl
    require_cmd tar
    require_cmd sha256sum
    require_cmd find
    require_cmd docker

    if [[ ! -d "$RESTORE_FROM" ]]; then
        log_error "Backup directory not found: ${RESTORE_FROM}"
        exit 1
    fi

    # --- Temp working directory (cleaned up by trap) ---
    WORK_DIR="$(mktemp -d "${TMPDIR_BASE}/aithena-restore-high-XXXXXX")"
    log_info "Work directory: ${WORK_DIR}"

    # --- Restore components based on COMPONENT filter ---
    case "$COMPONENT" in
        all)
            # Verify Solr cluster health before restore
            check_solr_health || exit 1
            restore_solr || exit 1
            verify_search_api || exit 1
            restore_zookeeper || exit 1
            ;;
        solr)
            check_solr_health || exit 1
            restore_solr || exit 1
            verify_search_api || exit 1
            ;;
        zk)
            restore_zookeeper || exit 1
            ;;
        *)
            log_info "No high-tier components requested (component=${COMPONENT})"
            ;;
    esac

    log_info "========== Aithena High-Priority Restore END   (exit=${EXIT_CODE}) =========="
    return "$EXIT_CODE"
}

main "$@"

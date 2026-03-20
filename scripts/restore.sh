#!/usr/bin/env bash
# =============================================================================
# Aithena BCDR — Restore Orchestrator
# =============================================================================
# Coordinates restore across all three tiers:
#   Tier 1 (Critical) — Auth DBs + secrets          (restore-critical.sh)
#   Tier 2 (High)     — Solr indexes + ZooKeeper    (restore-high.sh)
#   Tier 3 (Medium)   — Redis RDB + RabbitMQ defs   (restore-medium.sh)
#
# Usage:
#   ./scripts/restore.sh --from /source/backups
#   ./scripts/restore.sh --from /source/backups --component solr --dry-run
#   ./scripts/restore.sh --from /source/backups --tier high
#   ./scripts/restore.sh --from /source/backups --component all --skip-safety-backup
#
# Options:
#   --from <path>           Backup base directory to restore from (required)
#   --tier <critical|high|medium|all>
#                           Tier to restore (default: all)
#   --component <auth|collections|secrets|solr|zk|redis|rabbitmq|all>
#                           Component to restore (overrides --tier; default: unset)
#   --dry-run               Log actions without writing files
#   --skip-safety-backup    Skip safety backup of current state before restore
#   --help                  Show this help message
#
# Workflow:
#   1. Pre-flight: validate backup directory, verify checksums
#   2. Safety backup of current state (unless --skip-safety-backup)
#   3. Dispatch to tier-specific restore scripts
#   4. Report results
#
# Environment variables:
#   BACKUP_DEST             Base directory for safety backup (default: /source/backups)
#   PROJECT_ROOT            Repository / project root on the host
#   DRY_RUN                 Set to 1 to skip actual file operations
#   LOG_FILE                Orchestrator log file (default: /var/log/aithena-restore.log)
#
# Exit codes:
#   0  All requested restores succeeded
#   1  At least one tier had a fatal error
#   2  At least one tier had a partial failure (warnings only)
#
# See also:
#   scripts/restore-critical.sh  — Tier 1
#   scripts/restore-high.sh      — Tier 2
#   scripts/restore-medium.sh    — Tier 3
#   scripts/backup.sh            — Backup orchestrator
#   docs/prd/bcdr-plan.md        — BCDR plan
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BACKUP_DEST="${BACKUP_DEST:-/source/backups}"
PROJECT_ROOT="${PROJECT_ROOT:-/source/aithena}"
DRY_RUN="${DRY_RUN:-0}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

TIMESTAMP="$(date -u +%Y%m%d-%H%M)"
LOG_FILE="${LOG_FILE:-/var/log/aithena-restore.log}"

# Restrictive umask — restored files must not be world-readable
umask 077

# --- Ensure log file is writable; fall back to project-local if not ---
_init_log() {
    mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
    if ! touch "$LOG_FILE" 2>/dev/null; then
        LOG_FILE="${PROJECT_ROOT}/restore.log"
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
    msg="$(date -u '+%Y-%m-%dT%H:%M:%SZ') [${level}] [orchestrator] $*"
    echo "$msg" >&2
    echo "$msg" >> "$LOG_FILE" 2>/dev/null || true
}

log_info()  { log "INFO"  "$@"; }
log_warn()  { log "WARN"  "$@"; }
log_error() { log "ERROR" "$@"; }

# ---------------------------------------------------------------------------
# Usage / help
# ---------------------------------------------------------------------------
usage() {
    sed -n '/^# Usage:/,/^# =====/{ /^# =====/d; s/^# \{0,2\}//; p }' "${BASH_SOURCE[0]}"
    exit 0
}

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
# Component → Tier mapping
# ---------------------------------------------------------------------------
component_to_tier() {
    local component="$1"
    case "$component" in
        auth|collections|secrets) echo "critical" ;;
        solr|zk)                  echo "high"     ;;
        redis|rabbitmq)           echo "medium"   ;;
        all)                      echo "all"       ;;
        *)
            log_error "Unknown component: ${component}"
            exit 1
            ;;
    esac
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
TIER=""
COMPONENT=""
RESTORE_FROM=""
SKIP_SAFETY_BACKUP=0

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --from)
                if [[ $# -lt 2 ]]; then
                    log_error "--from requires a path argument"
                    exit 1
                fi
                RESTORE_FROM="$2"
                shift 2
                ;;
            --tier)
                if [[ $# -lt 2 ]]; then
                    log_error "--tier requires a value: critical|high|medium|all"
                    exit 1
                fi
                TIER="$2"
                shift 2
                ;;
            --component)
                if [[ $# -lt 2 ]]; then
                    log_error "--component requires a value: auth|collections|secrets|solr|zk|redis|rabbitmq|all"
                    exit 1
                fi
                COMPONENT="$2"
                shift 2
                ;;
            --dry-run)
                DRY_RUN=1
                shift
                ;;
            --skip-safety-backup)
                SKIP_SAFETY_BACKUP=1
                shift
                ;;
            --help|-h)
                usage
                ;;
            *)
                log_error "Unknown option: $1"
                log_error "Usage: $0 --from /path/to/backup [--tier critical|high|medium|all] [--component ...] [--dry-run]"
                exit 1
                ;;
        esac
    done

    # --from is required
    if [[ -z "$RESTORE_FROM" ]]; then
        log_error "--from is required. Specify the backup directory to restore from."
        log_error "Usage: $0 --from /path/to/backup [--tier ...] [--component ...] [--dry-run]"
        exit 1
    fi

    # Resolve --component to --tier if component is set
    if [[ -n "$COMPONENT" ]]; then
        case "$COMPONENT" in
            auth|collections|secrets|solr|zk|redis|rabbitmq|all) ;;
            *)
                log_error "Invalid component '${COMPONENT}'. Must be: auth|collections|secrets|solr|zk|redis|rabbitmq|all"
                exit 1
                ;;
        esac
        if [[ -z "$TIER" ]]; then
            TIER="$(component_to_tier "$COMPONENT")"
        fi
    fi

    # Default tier to "all" if neither --tier nor --component was specified
    if [[ -z "$TIER" ]]; then
        TIER="all"
    fi

    case "$TIER" in
        critical|high|medium|all) ;;
        *)
            log_error "Invalid tier '${TIER}'. Must be: critical|high|medium|all"
            exit 1
            ;;
    esac
}

# ---------------------------------------------------------------------------
# validate_backup_dir — verify the backup directory exists and has content
# ---------------------------------------------------------------------------
validate_backup_dir() {
    if [[ ! -d "$RESTORE_FROM" ]]; then
        log_error "Backup directory not found: ${RESTORE_FROM}"
        exit 1
    fi

    # Check that the directory has at least some files
    local file_count
    file_count="$(find "$RESTORE_FROM" -maxdepth 2 -type f 2>/dev/null | head -1 | wc -l)"
    if [[ "$file_count" -eq 0 ]]; then
        log_warn "Backup directory appears empty: ${RESTORE_FROM}"
    fi

    log_info "Backup directory validated: ${RESTORE_FROM}"
}

# ---------------------------------------------------------------------------
# safety_backup — create a backup of current state before restoring
# ---------------------------------------------------------------------------
safety_backup() {
    if [[ "$SKIP_SAFETY_BACKUP" == "1" ]]; then
        log_info "Safety backup skipped (--skip-safety-backup)"
        return 0
    fi

    local safety_dest="${BACKUP_DEST}/pre-restore-${TIMESTAMP}"
    log_info "Creating safety backup at ${safety_dest}..."

    local backup_script="${SCRIPT_DIR}/backup.sh"
    if [[ ! -x "$backup_script" ]]; then
        log_warn "Backup script not found or not executable: ${backup_script} — skipping safety backup"
        return 0
    fi

    if [[ "$DRY_RUN" == "1" ]]; then
        log_info "[DRY_RUN] Would create safety backup at ${safety_dest}"
        return 0
    fi

    local safety_rc=0
    env DRY_RUN=0 BACKUP_DEST="$safety_dest" PROJECT_ROOT="$PROJECT_ROOT" \
        bash "$backup_script" --tier all --dest "$safety_dest" || safety_rc=$?

    case "$safety_rc" in
        0) log_info "Safety backup completed successfully at ${safety_dest}" ;;
        2) log_warn "Safety backup completed with warnings at ${safety_dest}" ;;
        *)
            log_error "Safety backup FAILED (exit ${safety_rc}) — aborting restore"
            log_error "Fix the backup issue first or use --skip-safety-backup to override"
            return 1
            ;;
    esac
}

# ---------------------------------------------------------------------------
# run_tier — execute a single tier restore script
# ---------------------------------------------------------------------------
run_tier() {
    local tier_name="$1"
    local script_path="${SCRIPT_DIR}/restore-${tier_name}.sh"

    if [[ ! -f "$script_path" ]]; then
        log_error "Tier script not found: ${script_path}"
        return 1
    fi

    if [[ ! -x "$script_path" ]]; then
        log_error "Tier script not executable: ${script_path}. Run: chmod +x ${script_path}"
        return 1
    fi

    log_info "--- Restoring tier: ${tier_name} ---"

    # Build environment overrides for the tier script
    local tier_env=()
    tier_env+=("DRY_RUN=${DRY_RUN}")
    tier_env+=("PROJECT_ROOT=${PROJECT_ROOT}")

    # Pass component filter if set (and relevant to this tier)
    local tier_component="all"
    if [[ -n "$COMPONENT" && "$COMPONENT" != "all" ]]; then
        tier_component="$COMPONENT"
    fi
    tier_env+=("COMPONENT=${tier_component}")

    # Map RESTORE_FROM to the appropriate tier-specific directories
    case "$tier_name" in
        critical)
            tier_env+=("RESTORE_FROM=${RESTORE_FROM}/critical")
            ;;
        high)
            tier_env+=("RESTORE_FROM=${RESTORE_FROM}/high")
            tier_env+=("ZK_RESTORE_FROM=${RESTORE_FROM}/zookeeper")
            ;;
        medium)
            tier_env+=("RESTORE_FROM=${RESTORE_FROM}/medium")
            ;;
    esac

    local tier_rc=0
    env "${tier_env[@]}" bash "$script_path" || tier_rc=$?

    case "$tier_rc" in
        0) log_info "Tier ${tier_name} restore completed successfully" ;;
        2) log_warn "Tier ${tier_name} restore completed with warnings (exit ${tier_rc})" ;;
        *) log_error "Tier ${tier_name} restore FAILED (exit ${tier_rc})" ;;
    esac

    return "$tier_rc"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    parse_args "$@"

    # --- Pre-flight: dependency checks before lock ---
    require_cmd flock
    require_cmd bash

    # Concurrency guard — only one orchestrator instance at a time
    local lock_dir="${BACKUP_DEST}"
    mkdir -p "$lock_dir"
    local lock_file="${lock_dir}/.restore-orchestrator.lock"
    exec 9>"$lock_file"
    if ! flock -n 9; then
        log_error "Another restore instance is already running (lock: ${lock_file})"
        exit 1
    fi

    log_info "========== Aithena Restore Orchestrator START (${TIMESTAMP}) =========="
    log_info "RESTORE_FROM=${RESTORE_FROM}  TIER=${TIER}  COMPONENT=${COMPONENT:-all}  DRY_RUN=${DRY_RUN}"

    # --- Pre-flight: validate backup directory ---
    validate_backup_dir

    # --- Safety backup before restore ---
    safety_backup || exit 1

    # --- Determine which tiers to run ---
    local tiers=()
    case "$TIER" in
        all)      tiers=(critical high medium) ;;
        critical) tiers=(critical) ;;
        high)     tiers=(high) ;;
        medium)   tiers=(medium) ;;
    esac

    # Track worst-case exit code: 1 (fatal) > 2 (partial) > 0 (ok)
    local worst_rc=0

    for tier in "${tiers[@]}"; do
        local tier_rc=0
        run_tier "$tier" || tier_rc=$?

        # Priority: fatal (1) beats partial (2) beats ok (0)
        if [[ $tier_rc -eq 1 ]]; then
            worst_rc=1
        elif [[ $tier_rc -eq 2 && $worst_rc -eq 0 ]]; then
            worst_rc=2
        fi
    done

    case "$worst_rc" in
        0) log_info "========== Aithena Restore Orchestrator END   (ALL OK) ==========" ;;
        2) log_warn "========== Aithena Restore Orchestrator END   (WARNINGS) ==========" ;;
        *) log_error "========== Aithena Restore Orchestrator END   (FAILURES) ==========" ;;
    esac

    return "$worst_rc"
}

main "$@"

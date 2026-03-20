#!/usr/bin/env bash
# =============================================================================
# Aithena BCDR — Backup Orchestrator
# =============================================================================
# Coordinates all three backup tiers:
#   Tier 1 (Critical) — Auth DBs + secrets          (backup-critical.sh)
#   Tier 2 (High)     — Solr indexes + ZooKeeper    (backup-high.sh)
#   Tier 3 (Medium)   — Redis RDB + RabbitMQ defs   (backup-medium.sh)
#
# Usage:
#   ./scripts/backup.sh                         # run all tiers
#   ./scripts/backup.sh --tier critical         # run only tier 1
#   ./scripts/backup.sh --tier high --dry-run   # dry-run tier 2
#   ./scripts/backup.sh --tier all --dest /mnt/backups
#
# Options:
#   --tier <critical|high|medium|all>   Tier to run (default: all)
#   --dest <path>                       Override base backup directory
#   --dry-run                           Log actions without writing files
#   --help                              Show this help message
#
# Cron examples (add via: sudo crontab -e):
#   # Tier 1 — Critical: every 30 minutes
#   */30 * * * *  /path/to/scripts/backup.sh --tier critical >> /var/log/aithena-backup.log 2>&1
#
#   # Tier 2 — High: daily at 02:00 UTC
#   0 2 * * *     /path/to/scripts/backup.sh --tier high >> /var/log/aithena-backup.log 2>&1
#
#   # Tier 3 — Medium: daily at 03:00 UTC
#   0 3 * * *     /path/to/scripts/backup.sh --tier medium >> /var/log/aithena-backup.log 2>&1
#
#   # All tiers — weekly full backup, Sundays at 01:00 UTC
#   0 1 * * 0     /path/to/scripts/backup.sh --tier all >> /var/log/aithena-backup.log 2>&1
#
# Initial deployment:
#   1. Ensure tier scripts are executable:
#        chmod +x scripts/backup-critical.sh scripts/backup-high.sh scripts/backup-medium.sh scripts/backup.sh
#   2. Create backup key for critical tier:
#        sudo mkdir -p /etc/aithena
#        openssl rand -base64 32 | sudo tee /etc/aithena/backup.key > /dev/null
#        sudo chmod 600 /etc/aithena/backup.key
#   3. Create backup directories (or let scripts auto-create):
#        sudo mkdir -p /source/backups/{critical,high,medium,zookeeper}
#   4. Install cron entries (see examples above)
#   5. Verify with a dry-run:
#        ./scripts/backup.sh --tier all --dry-run
#
# Environment variables:
#   BACKUP_DEST             Base directory for orchestrator lock and --dest default (default: /source/backups)
#   DRY_RUN                 Set to 1 to skip actual file operations (forwarded to tier scripts)
#   PROJECT_ROOT            Repository / project root on the host (forwarded to tier scripts)
#   LOG_FILE                Orchestrator log file (default: /var/log/aithena-backup.log)
#
#   Tier-specific variables (e.g. BACKUP_DIR, SOLR_BACKUP_DIR) are set by the
#   orchestrator only when --dest is used. Otherwise, tier scripts use their own defaults.
#   See individual scripts for tier-specific configuration.
#
# Exit codes:
#   0  All requested tiers succeeded
#   1  At least one tier had a fatal error
#   2  At least one tier had a partial failure (warnings only)
#
# See also:
#   scripts/backup-critical.sh  — Tier 1
#   scripts/backup-high.sh      — Tier 2
#   scripts/backup-medium.sh    — Tier 3
#   docs/prd/bcdr-plan.md       — BCDR plan
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
LOG_FILE="${LOG_FILE:-/var/log/aithena-backup.log}"

# Restrictive umask — backup files must not be world-readable
umask 077

# --- Ensure log file is writable; fall back to project-local if not ---
_init_log() {
    mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
    if ! touch "$LOG_FILE" 2>/dev/null; then
        LOG_FILE="${PROJECT_ROOT}/backup.log"
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
# Dependency checks (run before flock)
# ---------------------------------------------------------------------------
require_cmd() {
    if ! command -v "$1" &>/dev/null; then
        log_error "Required command '$1' not found. Install it and retry."
        exit 1
    fi
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
TIER="all"
DEST_OVERRIDE=""

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --tier)
                if [[ $# -lt 2 ]]; then
                    log_error "--tier requires a value: critical|high|medium|all"
                    exit 1
                fi
                TIER="$2"
                shift 2
                ;;
            --dest)
                if [[ $# -lt 2 ]]; then
                    log_error "--dest requires a path argument"
                    exit 1
                fi
                DEST_OVERRIDE="$2"
                shift 2
                ;;
            --dry-run)
                DRY_RUN=1
                shift
                ;;
            --help|-h)
                usage
                ;;
            *)
                log_error "Unknown option: $1"
                log_error "Usage: $0 [--tier critical|high|medium|all] [--dest /path] [--dry-run]"
                exit 1
                ;;
        esac
    done

    case "$TIER" in
        critical|high|medium|all) ;;
        *)
            log_error "Invalid tier '${TIER}'. Must be: critical|high|medium|all"
            exit 1
            ;;
    esac

    if [[ -n "$DEST_OVERRIDE" ]]; then
        BACKUP_DEST="$DEST_OVERRIDE"
    fi
}

# ---------------------------------------------------------------------------
# run_tier — execute a single tier script and capture its exit code
# ---------------------------------------------------------------------------
run_tier() {
    local tier_name="$1"
    local script_path="${SCRIPT_DIR}/backup-${tier_name}.sh"

    if [[ ! -f "$script_path" ]]; then
        log_error "Tier script not found: ${script_path}"
        return 1
    fi

    if [[ ! -x "$script_path" ]]; then
        log_error "Tier script not executable: ${script_path}. Run: chmod +x ${script_path}"
        return 1
    fi

    log_info "--- Running tier: ${tier_name} ---"

    # Build environment overrides for the tier script
    local tier_env=()
    tier_env+=("DRY_RUN=${DRY_RUN}")
    tier_env+=("PROJECT_ROOT=${PROJECT_ROOT}")

    # Map BACKUP_DEST to the appropriate tier-specific env vars
    case "$tier_name" in
        critical)
            tier_env+=("BACKUP_DIR=${BACKUP_DEST}/critical")
            ;;
        high)
            tier_env+=("SOLR_BACKUP_DIR=${BACKUP_DEST}/high")
            tier_env+=("ZK_BACKUP_DIR=${BACKUP_DEST}/zookeeper")
            ;;
        medium)
            tier_env+=("BACKUP_DIR=${BACKUP_DEST}/medium")
            ;;
    esac

    local tier_rc=0
    env "${tier_env[@]}" bash "$script_path" || tier_rc=$?

    case "$tier_rc" in
        0) log_info "Tier ${tier_name} completed successfully" ;;
        2) log_warn "Tier ${tier_name} completed with warnings (exit ${tier_rc})" ;;
        *) log_error "Tier ${tier_name} FAILED (exit ${tier_rc})" ;;
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
    local lock_file="${lock_dir}/.backup-orchestrator.lock"
    exec 9>"$lock_file"
    if ! flock -n 9; then
        log_error "Another orchestrator instance is already running (lock: ${lock_file})"
        exit 1
    fi

    log_info "========== Aithena Backup Orchestrator START (${TIMESTAMP}) =========="
    log_info "TIER=${TIER}  BACKUP_DEST=${BACKUP_DEST}  DRY_RUN=${DRY_RUN}"

    # Determine which tiers to run
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
        0) log_info "========== Aithena Backup Orchestrator END   (ALL OK) ==========" ;;
        2) log_warn "========== Aithena Backup Orchestrator END   (WARNINGS) ==========" ;;
        *) log_error "========== Aithena Backup Orchestrator END   (FAILURES) ==========" ;;
    esac

    return "$worst_rc"
}

main "$@"

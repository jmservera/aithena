#!/usr/bin/env bash
# =============================================================================
# Aithena BCDR — Backup Integrity Verification
# =============================================================================
# Validates backup integrity by checking SHA-256 checksums, GPG encryption
# structure, and per-tier completeness.  Can run standalone for monitoring
# or be called by restore.sh as a pre-restore gate.
#
# Usage:
#   ./scripts/verify-backup.sh /source/backups/critical/   # verify one tier
#   ./scripts/verify-backup.sh /source/backups/             # verify all tiers
#   ./scripts/verify-backup.sh --tier high /source/backups/high/
#   ./scripts/verify-backup.sh --latest /source/backups/critical/
#   ./scripts/verify-backup.sh --help
#
# Options:
#   --tier <critical|high|medium|auto>
#               Tier to verify (default: auto — detect from directory name,
#               or scan subdirectories if given the base backup directory)
#   --latest    Only verify the most recent backup set per component
#   --dry-run   Log what would be checked without actually verifying
#   --help      Show this help message
#
# Environment variables:
#   BACKUP_KEY              GPG passphrase file for decryption test (optional;
#                           without it, only GPG packet structure is checked)
#   ZK_NODES                Expected number of ZooKeeper nodes (default: 3)
#   LOG_FILE                Log file path (default: /var/log/aithena-verify-backup.log)
#   PROJECT_ROOT            Repository / project root on the host
#   DRY_RUN                 Set to 1 to skip actual verification
#
# Exit codes:
#   0  All checks passed
#   1  Fatal — checksum mismatch, missing required files, or corrupt GPG
#   2  Partial — warnings (missing optional files, missing checksum sidecars)
#
# See also:
#   scripts/backup-critical.sh  — Tier 1 (generates .sha256 + .gpg)
#   scripts/backup-high.sh      — Tier 2 (generates .sha256 + .tar.gz)
#   scripts/backup-medium.sh    — Tier 3 (generates .sha256 + .rdb.gz/.json.gz)
#   scripts/restore.sh          — Calls this script pre-restore
#   docs/prd/bcdr-plan.md       — BCDR plan §8.3
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BACKUP_KEY="${BACKUP_KEY:-}"
ZK_NODES="${ZK_NODES:-3}"
PROJECT_ROOT="${PROJECT_ROOT:-/source/aithena}"
DRY_RUN="${DRY_RUN:-0}"

umask 077

TIMESTAMP="$(date -u +%Y%m%d-%H%M)"
LOG_FILE="${LOG_FILE:-/var/log/aithena-verify-backup.log}"

# --- Ensure log file is writable; fall back to project-local if not ---
_init_log() {
    mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
    if ! touch "$LOG_FILE" 2>/dev/null; then
        LOG_FILE="${PROJECT_ROOT}/verify-backup.log"
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
    msg="$(date -u '+%Y-%m-%dT%H:%M:%SZ') [${level}] [verify] $*"
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
# Counters & state
# ---------------------------------------------------------------------------
PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0
EXIT_CODE=0    # 0=ok, escalated to 2 (warn) or 1 (fatal)

record_pass() {
    ((PASS_COUNT++)) || true
    log_info "PASS  $1"
}

record_fail() {
    ((FAIL_COUNT++)) || true
    EXIT_CODE=1
    log_error "FAIL  $1"
}

record_warn() {
    ((WARN_COUNT++)) || true
    if [[ "$EXIT_CODE" -eq 0 ]]; then EXIT_CODE=2; fi
    log_warn "WARN  $1"
}

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
TIER="auto"
LATEST_ONLY=0
BACKUP_DIR=""

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --tier)
                if [[ $# -lt 2 ]]; then
                    log_error "--tier requires a value: critical|high|medium|auto"
                    exit 1
                fi
                TIER="$2"
                shift 2
                ;;
            --latest)
                LATEST_ONLY=1
                shift
                ;;
            --dry-run)
                DRY_RUN=1
                shift
                ;;
            --help|-h)
                usage
                ;;
            -*)
                log_error "Unknown option: $1"
                log_error "Usage: $0 [--tier critical|high|medium|auto] [--latest] [--dry-run] <backup-directory>"
                exit 1
                ;;
            *)
                if [[ -n "$BACKUP_DIR" ]]; then
                    log_error "Multiple directories specified. Provide exactly one backup directory."
                    exit 1
                fi
                BACKUP_DIR="$1"
                shift
                ;;
        esac
    done

    if [[ -z "$BACKUP_DIR" ]]; then
        log_error "Backup directory is required."
        log_error "Usage: $0 [--tier critical|high|medium|auto] [--latest] [--dry-run] <backup-directory>"
        exit 1
    fi

    # Trim trailing slash for consistent basename matching
    BACKUP_DIR="${BACKUP_DIR%/}"

    if [[ ! -d "$BACKUP_DIR" ]]; then
        log_error "Backup directory not found: ${BACKUP_DIR}"
        exit 1
    fi

    case "$TIER" in
        critical|high|medium|auto) ;;
        *)
            log_error "Invalid tier '${TIER}'. Must be: critical|high|medium|auto"
            exit 1
            ;;
    esac
}

# ---------------------------------------------------------------------------
# detect_tier — infer tier from directory name
# ---------------------------------------------------------------------------
detect_tier() {
    local dir_name
    dir_name="$(basename "$BACKUP_DIR")"

    case "$dir_name" in
        critical)  echo "critical" ;;
        high)      echo "high"     ;;
        medium)    echo "medium"   ;;
        zookeeper) echo "high"     ;;
        *)         echo "base"     ;;
    esac
}

# ---------------------------------------------------------------------------
# find_latest_file — find the most recent file matching a pattern
# ---------------------------------------------------------------------------
find_latest_file() {
    local dir="$1"
    local pattern="$2"

    find "$dir" -maxdepth 1 -name "$pattern" -type f -print0 2>/dev/null \
        | xargs -0 ls -t 2>/dev/null \
        | head -1
}

# ---------------------------------------------------------------------------
# verify_checksum — validate a single .sha256 sidecar
#   Returns 0 on success, 1 on failure
# ---------------------------------------------------------------------------
verify_single_checksum() {
    local checksum_file="$1"
    local dir
    dir="$(dirname "$checksum_file")"
    local base
    base="$(basename "$checksum_file")"

    # The checksum file references the data file by relative name
    pushd "$dir" > /dev/null
    if sha256sum --check "$base" &>/dev/null; then
        popd > /dev/null
        return 0
    else
        popd > /dev/null
        return 1
    fi
}

# ---------------------------------------------------------------------------
# verify_all_checksums — find and verify every .sha256 file in a directory
# ---------------------------------------------------------------------------
verify_all_checksums() {
    local dir="$1"
    local label="${2:-}"
    local found=0

    while IFS= read -r -d '' sha_file; do
        found=1
        local data_file="${sha_file%.sha256}"
        local rel_name
        rel_name="$(basename "$data_file")"

        if [[ "$DRY_RUN" == "1" ]]; then
            log_info "[DRY_RUN] Would verify checksum: ${rel_name}"
            continue
        fi

        if [[ ! -f "$data_file" ]]; then
            record_fail "Checksum references missing file: ${rel_name} (${label})"
            continue
        fi

        if verify_single_checksum "$sha_file"; then
            record_pass "Checksum OK: ${rel_name} (${label})"
        else
            record_fail "Checksum MISMATCH: ${rel_name} (${label})"
        fi
    done < <(find "$dir" -maxdepth 1 -name '*.sha256' -type f -print0 2>/dev/null)

    if [[ "$found" -eq 0 && "$DRY_RUN" != "1" ]]; then
        record_warn "No .sha256 checksum files found in ${dir} (${label})"
    fi
}

# ---------------------------------------------------------------------------
# verify_gpg_files — validate GPG encryption integrity
#   Level 1 (no key): check file is recognized as GPG-encrypted data
#   Level 2 (with key): full decrypt-to-null to verify passphrase + integrity
# ---------------------------------------------------------------------------
verify_gpg_files() {
    local dir="$1"
    local label="${2:-}"
    local found=0

    while IFS= read -r -d '' gpg_file; do
        found=1
        local rel_name
        rel_name="$(basename "$gpg_file")"

        if [[ "$DRY_RUN" == "1" ]]; then
            log_info "[DRY_RUN] Would verify GPG integrity: ${rel_name}"
            continue
        fi

        # Level 1: Verify file is recognized as GPG-encrypted data
        local file_type=""
        file_type="$(file -b "$gpg_file" 2>/dev/null)"
        if ! echo "$file_type" | grep -qi 'gpg\|pgp\|encrypted'; then
            record_fail "Not a valid GPG file: ${rel_name} (${label}) — detected as: ${file_type}"
            continue
        fi

        # Level 2: If backup key is available, verify decryption succeeds
        if [[ -n "$BACKUP_KEY" && -f "$BACKUP_KEY" ]]; then
            if gpg --batch --yes --pinentry-mode loopback --no-tty \
                   --passphrase-file "$BACKUP_KEY" \
                   --decrypt --output /dev/null "$gpg_file" 2>/dev/null; then
                record_pass "GPG decryption OK: ${rel_name} (${label})"
            else
                record_fail "GPG decryption FAILED: ${rel_name} (${label})"
            fi
        else
            record_pass "GPG structure OK: ${rel_name} (${label})"
        fi
    done < <(find "$dir" -maxdepth 1 -name '*.gpg' -type f -print0 2>/dev/null)

    if [[ "$found" -eq 0 ]]; then
        log_info "No GPG-encrypted files found in ${dir} (${label}) — skipping GPG checks"
    fi
}

# ---------------------------------------------------------------------------
# Tier-specific completeness checks
# ---------------------------------------------------------------------------
check_completeness_critical() {
    local dir="$1"
    log_info "Checking critical-tier completeness in ${dir}"

    # Required: auth DB backup
    local auth_file
    if [[ "$LATEST_ONLY" == "1" ]]; then
        auth_file="$(find_latest_file "$dir" "auth-*.db.gpg")"
    else
        auth_file="$(find "$dir" -maxdepth 1 -name "auth-*.db.gpg" -type f -print -quit 2>/dev/null)"
    fi
    if [[ -n "$auth_file" ]]; then
        record_pass "Required file present: auth DB backup"
    else
        record_fail "Required file MISSING: auth-*.db.gpg"
    fi

    # Required: .env secrets backup
    local env_file
    if [[ "$LATEST_ONLY" == "1" ]]; then
        env_file="$(find_latest_file "$dir" "env-*.gpg")"
    else
        env_file="$(find "$dir" -maxdepth 1 -name "env-*.gpg" ! -name "*.sha256" -type f -print -quit 2>/dev/null)"
    fi
    if [[ -n "$env_file" ]]; then
        record_pass "Required file present: secrets (.env) backup"
    else
        record_fail "Required file MISSING: env-*.gpg"
    fi

    # Optional: collections DB backup
    local coll_file
    if [[ "$LATEST_ONLY" == "1" ]]; then
        coll_file="$(find_latest_file "$dir" "collections-*.db.gpg")"
    else
        coll_file="$(find "$dir" -maxdepth 1 -name "collections-*.db.gpg" -type f -print -quit 2>/dev/null)"
    fi
    if [[ -n "$coll_file" ]]; then
        record_pass "Optional file present: collections DB backup"
    else
        record_warn "Optional file missing: collections-*.db.gpg"
    fi
}

check_completeness_high() {
    local dir="$1"
    local zk_dir="${2:-}"
    log_info "Checking high-tier completeness in ${dir}"

    # Required: Solr collection backup
    local solr_file
    if [[ "$LATEST_ONLY" == "1" ]]; then
        solr_file="$(find_latest_file "$dir" "*.tar.gz")"
    else
        solr_file="$(find "$dir" -maxdepth 1 -name "*.tar.gz" -type f -print -quit 2>/dev/null)"
    fi
    if [[ -n "$solr_file" ]]; then
        record_pass "Required file present: Solr collection backup"
    else
        record_fail "Required file MISSING: Solr *.tar.gz archive"
    fi

    # ZooKeeper backups — check in zk_dir or adjacent zookeeper/ directory
    if [[ -z "$zk_dir" ]]; then
        local parent
        parent="$(dirname "$dir")"
        if [[ -d "${parent}/zookeeper" ]]; then
            zk_dir="${parent}/zookeeper"
        fi
    fi

    if [[ -n "$zk_dir" && -d "$zk_dir" ]]; then
        log_info "Checking ZooKeeper backups in ${zk_dir}"
        local i zk_found=0
        for i in $(seq 1 "$ZK_NODES"); do
            local zk_file
            if [[ "$LATEST_ONLY" == "1" ]]; then
                zk_file="$(find_latest_file "$zk_dir" "zoo-data${i}-*.tar.gz")"
            else
                zk_file="$(find "$zk_dir" -maxdepth 1 -name "zoo-data${i}-*.tar.gz" -type f -print -quit 2>/dev/null)"
            fi
            if [[ -n "$zk_file" ]]; then
                record_pass "ZooKeeper node ${i} backup present"
                ((zk_found++)) || true
            else
                record_warn "ZooKeeper node ${i} backup missing: zoo-data${i}-*.tar.gz"
            fi
        done
        # Also verify ZK checksums
        verify_all_checksums "$zk_dir" "zookeeper"
    else
        record_warn "ZooKeeper backup directory not found — cannot check ZK completeness"
    fi
}

check_completeness_medium() {
    local dir="$1"
    log_info "Checking medium-tier completeness in ${dir}"

    # Expected: Redis RDB backup
    local redis_file
    if [[ "$LATEST_ONLY" == "1" ]]; then
        redis_file="$(find_latest_file "$dir" "redis-dump-*.rdb.gz")"
    else
        redis_file="$(find "$dir" -maxdepth 1 -name "redis-dump-*.rdb.gz" -type f -print -quit 2>/dev/null)"
    fi
    if [[ -n "$redis_file" ]]; then
        record_pass "Expected file present: Redis RDB backup"
    else
        record_warn "Expected file missing: redis-dump-*.rdb.gz (Redis may have been unavailable)"
    fi

    # Expected: RabbitMQ definitions backup
    local rabbit_file
    if [[ "$LATEST_ONLY" == "1" ]]; then
        rabbit_file="$(find_latest_file "$dir" "rabbitmq-definitions-*.json.gz")"
    else
        rabbit_file="$(find "$dir" -maxdepth 1 -name "rabbitmq-definitions-*.json.gz" -type f -print -quit 2>/dev/null)"
    fi
    if [[ -n "$rabbit_file" ]]; then
        record_pass "Expected file present: RabbitMQ definitions backup"
    else
        record_warn "Expected file missing: rabbitmq-definitions-*.json.gz (RabbitMQ may have been unavailable)"
    fi
}

# ---------------------------------------------------------------------------
# verify_tier — run all checks for a single tier directory
# ---------------------------------------------------------------------------
verify_tier() {
    local tier="$1"
    local dir="$2"
    local zk_dir="${3:-}"

    log_info "━━━ Verifying tier: ${tier} in ${dir} ━━━"

    if [[ ! -d "$dir" ]]; then
        record_warn "Tier directory not found: ${dir} — skipping ${tier}"
        return 0
    fi

    # 1. Checksum verification
    verify_all_checksums "$dir" "$tier"

    # 2. GPG integrity (critical tier only has GPG files)
    verify_gpg_files "$dir" "$tier"

    # 3. Completeness
    case "$tier" in
        critical) check_completeness_critical "$dir" ;;
        high)     check_completeness_high "$dir" "$zk_dir" ;;
        medium)   check_completeness_medium "$dir" ;;
    esac
}

# ---------------------------------------------------------------------------
# print_summary — formatted report
# ---------------------------------------------------------------------------
print_summary() {
    local total=$((PASS_COUNT + FAIL_COUNT + WARN_COUNT))
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Backup Verification Report"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Directory : ${BACKUP_DIR}"
    echo "  Timestamp : ${TIMESTAMP}"
    echo "  Checks    : ${total} total"
    echo "  ✅ Passed  : ${PASS_COUNT}"
    if [[ "$WARN_COUNT" -gt 0 ]]; then
        echo "  ⚠️  Warnings: ${WARN_COUNT}"
    fi
    if [[ "$FAIL_COUNT" -gt 0 ]]; then
        echo "  ❌ Failed  : ${FAIL_COUNT}"
    fi
    echo ""
    case "$EXIT_CODE" in
        0) echo "  Result: ✅ PASS — all integrity checks passed" ;;
        2) echo "  Result: ⚠️  PARTIAL — passed with warnings" ;;
        *) echo "  Result: ❌ FAIL — integrity errors detected" ;;
    esac
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    parse_args "$@"

    # --- Pre-flight checks ---
    require_cmd sha256sum
    require_cmd find

    # GPG is only required if encrypted files will be checked
    local has_gpg=0
    if command -v gpg &>/dev/null; then
        has_gpg=1
    fi

    # Concurrency guard
    local lock_dir="${BACKUP_DIR}"
    mkdir -p "$lock_dir" 2>/dev/null || true
    local lock_file="${lock_dir}/.verify-backup.lock"
    if command -v flock &>/dev/null; then
        exec 9>"$lock_file"
        if ! flock -n 9; then
            log_error "Another verification instance is already running (lock: ${lock_file})"
            exit 1
        fi
    fi

    log_info "========== Aithena Backup Verification START (${TIMESTAMP}) =========="
    log_info "BACKUP_DIR=${BACKUP_DIR}  TIER=${TIER}  LATEST_ONLY=${LATEST_ONLY}  DRY_RUN=${DRY_RUN}"

    if [[ "$has_gpg" -eq 0 ]]; then
        log_warn "gpg not found — GPG integrity checks will be skipped"
    fi

    # --- Determine what to verify ---
    if [[ "$TIER" != "auto" ]]; then
        # Explicit tier — verify the given directory as that tier
        case "$TIER" in
            high)
                local zk_dir=""
                local parent
                parent="$(dirname "$BACKUP_DIR")"
                if [[ -d "${parent}/zookeeper" ]]; then
                    zk_dir="${parent}/zookeeper"
                fi
                verify_tier "$TIER" "$BACKUP_DIR" "$zk_dir"
                ;;
            *)
                verify_tier "$TIER" "$BACKUP_DIR"
                ;;
        esac
    else
        local detected
        detected="$(detect_tier)"

        if [[ "$detected" == "base" ]]; then
            # Base directory — scan for tier subdirectories
            log_info "Base backup directory detected — scanning subdirectories"

            local found_any=0
            if [[ -d "${BACKUP_DIR}/critical" ]]; then
                verify_tier "critical" "${BACKUP_DIR}/critical"
                found_any=1
            fi
            if [[ -d "${BACKUP_DIR}/high" ]]; then
                local zk_dir=""
                if [[ -d "${BACKUP_DIR}/zookeeper" ]]; then
                    zk_dir="${BACKUP_DIR}/zookeeper"
                fi
                verify_tier "high" "${BACKUP_DIR}/high" "$zk_dir"
                found_any=1
            fi
            if [[ -d "${BACKUP_DIR}/medium" ]]; then
                verify_tier "medium" "${BACKUP_DIR}/medium"
                found_any=1
            fi

            if [[ "$found_any" -eq 0 ]]; then
                # No tier subdirectories — verify as a flat directory
                log_info "No tier subdirectories found — verifying flat directory"
                verify_all_checksums "$BACKUP_DIR" "flat"
                verify_gpg_files "$BACKUP_DIR" "flat"
            fi
        else
            # Detected a specific tier directory
            case "$detected" in
                high)
                    local zk_dir=""
                    local parent
                    parent="$(dirname "$BACKUP_DIR")"
                    if [[ -d "${parent}/zookeeper" ]]; then
                        zk_dir="${parent}/zookeeper"
                    fi
                    verify_tier "$detected" "$BACKUP_DIR" "$zk_dir"
                    ;;
                *)
                    verify_tier "$detected" "$BACKUP_DIR"
                    ;;
            esac
        fi
    fi

    # --- Summary ---
    print_summary

    log_info "========== Aithena Backup Verification END   (exit=${EXIT_CODE}) =========="
    return "$EXIT_CODE"
}

main "$@"

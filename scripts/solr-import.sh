#!/usr/bin/env bash
# =============================================================================
# Aithena — Solr Collection Import
# =============================================================================
# Imports JSONL data (exported by solr-export.sh) into a Solr collection.
# Supports both Solr 9 and Solr 10 targets with automatic schema transformation.
#
# Usage:
#   ./scripts/solr-import.sh --source /source/exports/books-20260401-120000/data.jsonl
#   ./scripts/solr-import.sh --source data.jsonl --collection books
#   ./scripts/solr-import.sh --source data.jsonl --create-collection
#   ./scripts/solr-import.sh --source data.jsonl --configset-dir /path/to/configset
#   ./scripts/solr-import.sh --source data.jsonl --dry-run
#
# Options:
#   --source <path>           Path to JSONL file to import (required)
#   --collection <name>       Target collection name (default: books)
#   --batch-size <n>          Documents per update request (default: 100)
#   --create-collection       Create collection if it does not exist
#   --num-shards <n>          Shards for new collection (default: 1)
#   --replication-factor <n>  Replication factor for new collection (default: 1)
#   --configset-dir <path>    Upload configset from directory before creating collection
#   --configset-name <name>   Configset name (default: same as collection)
#   --transform-schema        Force HNSW param transformation for Solr 10
#   --no-transform            Skip automatic schema transformation
#   --max-retries <n>         Max retries per batch on failure (default: 3)
#   --retry-delay <n>         Seconds between retries (default: 5)
#   --resume                  Resume from last successful batch (skip already-imported docs)
#   --dry-run                 Validate data and log actions without importing
#   --help                    Show this help message
#
# Environment variables:
#   SOLR_URL                  Solr HTTP base URL (default: http://localhost:8983)
#   SOLR_AUTH_USER            Solr Basic Auth username (optional)
#   SOLR_AUTH_PASS            Solr Basic Auth password (optional)
#   SOLR_ADMIN_USER           Fallback admin username if SOLR_AUTH_USER is unset
#   SOLR_ADMIN_PASS           Fallback admin password if SOLR_AUTH_PASS is unset
#   SOLR_HEALTH_TIMEOUT       Seconds to wait for Solr health (default: 30)
#   PROJECT_ROOT              Repository root (default: /source/aithena)
#   LOG_FILE                  Log file (default: /var/log/aithena-solr-import.log)
#   DRY_RUN                   Set to 1 to skip actual writes
#
# Schema transformation (Solr 9 → 10):
#   When the target is Solr 10, HNSW parameters in DenseVectorField definitions
#   are automatically renamed:
#     hnswMaxConnections  →  maxConnections
#     hnswBeamWidth       →  beamWidth
#   Use --no-transform to disable or --transform-schema to force.
#
# Exit codes:
#   0  Import succeeded
#   1  Fatal error
#   2  Partial failure (some batches failed after retries)
#
# See also:
#   scripts/solr-export.sh          — Export counterpart
#   docs/migration/solr-9-to-10.md  — Solr 10 migration plan
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SOLR_URL="${SOLR_URL:-http://localhost:8983}"
COLLECTION="${COLLECTION:-books}"
BATCH_SIZE="${BATCH_SIZE:-100}"
SOURCE_FILE=""
CREATE_COLLECTION=0
NUM_SHARDS="${NUM_SHARDS:-1}"
REPLICATION_FACTOR="${REPLICATION_FACTOR:-1}"
CONFIGSET_DIR=""
CONFIGSET_NAME=""
TRANSFORM_SCHEMA=""  # empty = auto-detect, "yes" = force, "no" = skip
MAX_RETRIES="${MAX_RETRIES:-3}"
RETRY_DELAY="${RETRY_DELAY:-5}"
RESUME=0
DRY_RUN="${DRY_RUN:-0}"
SOLR_HEALTH_TIMEOUT="${SOLR_HEALTH_TIMEOUT:-30}"
PROJECT_ROOT="${PROJECT_ROOT:-/source/aithena}"

TIMESTAMP="$(date -u +%Y%m%d-%H%M%S)"
LOG_FILE="${LOG_FILE:-/var/log/aithena-solr-import.log}"
EXIT_CODE=0

# Restrictive umask — imports may reference sensitive data paths
umask 077

# --- Resolve Solr auth: prefer SOLR_AUTH_USER/PASS, fall back to SOLR_ADMIN ---
SOLR_USER="${SOLR_AUTH_USER:-${SOLR_ADMIN_USER:-}}"
SOLR_PASS="${SOLR_AUTH_PASS:-${SOLR_ADMIN_PASS:-}}"

# --- Ensure log file is writable; fall back to project-local if not ---
_init_log() {
    mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
    if ! touch "$LOG_FILE" 2>/dev/null; then
        LOG_FILE="${PROJECT_ROOT}/solr-import.log"
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
    msg="$(date -u '+%Y-%m-%dT%H:%M:%SZ') [${level}] [solr-import] $*"
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
# Argument parsing
# ---------------------------------------------------------------------------
parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --source)
                [[ $# -lt 2 ]] && { log_error "--source requires a file path"; exit 1; }
                SOURCE_FILE="$2"; shift 2 ;;
            --collection)
                [[ $# -lt 2 ]] && { log_error "--collection requires a value"; exit 1; }
                COLLECTION="$2"; shift 2 ;;
            --batch-size)
                [[ $# -lt 2 ]] && { log_error "--batch-size requires a number"; exit 1; }
                BATCH_SIZE="$2"; shift 2 ;;
            --create-collection)
                CREATE_COLLECTION=1; shift ;;
            --num-shards)
                [[ $# -lt 2 ]] && { log_error "--num-shards requires a number"; exit 1; }
                NUM_SHARDS="$2"; shift 2 ;;
            --replication-factor)
                [[ $# -lt 2 ]] && { log_error "--replication-factor requires a number"; exit 1; }
                REPLICATION_FACTOR="$2"; shift 2 ;;
            --configset-dir)
                [[ $# -lt 2 ]] && { log_error "--configset-dir requires a path"; exit 1; }
                CONFIGSET_DIR="$2"; shift 2 ;;
            --configset-name)
                [[ $# -lt 2 ]] && { log_error "--configset-name requires a value"; exit 1; }
                CONFIGSET_NAME="$2"; shift 2 ;;
            --transform-schema)
                TRANSFORM_SCHEMA="yes"; shift ;;
            --no-transform)
                TRANSFORM_SCHEMA="no"; shift ;;
            --max-retries)
                [[ $# -lt 2 ]] && { log_error "--max-retries requires a number"; exit 1; }
                MAX_RETRIES="$2"; shift 2 ;;
            --retry-delay)
                [[ $# -lt 2 ]] && { log_error "--retry-delay requires a number"; exit 1; }
                RETRY_DELAY="$2"; shift 2 ;;
            --resume)
                RESUME=1; shift ;;
            --dry-run)
                DRY_RUN=1; shift ;;
            --help|-h)
                usage ;;
            *)
                log_error "Unknown option: $1"
                log_error "Run: $0 --help"
                exit 1 ;;
        esac
    done

    # Validate required args
    if [[ -z "$SOURCE_FILE" ]]; then
        log_error "--source is required"
        log_error "Run: $0 --help"
        exit 1
    fi

    if [[ ! -f "$SOURCE_FILE" ]]; then
        log_error "Source file not found: ${SOURCE_FILE}"
        exit 1
    fi

    # Validate batch size
    if ! [[ "$BATCH_SIZE" =~ ^[0-9]+$ ]] || [[ "$BATCH_SIZE" -lt 1 ]]; then
        log_error "BATCH_SIZE must be a positive integer, got '${BATCH_SIZE}'"
        exit 1
    fi

    # Validate numeric options
    if ! [[ "$MAX_RETRIES" =~ ^[0-9]+$ ]]; then
        log_error "--max-retries must be a non-negative integer, got '${MAX_RETRIES}'"
        exit 1
    fi
    if ! [[ "$RETRY_DELAY" =~ ^[0-9]+$ ]]; then
        log_error "--retry-delay must be a non-negative integer, got '${RETRY_DELAY}'"
        exit 1
    fi
    if ! [[ "$NUM_SHARDS" =~ ^[0-9]+$ ]] || [[ "$NUM_SHARDS" -lt 1 ]]; then
        log_error "--num-shards must be a positive integer, got '${NUM_SHARDS}'"
        exit 1
    fi
    if ! [[ "$REPLICATION_FACTOR" =~ ^[0-9]+$ ]] || [[ "$REPLICATION_FACTOR" -lt 1 ]]; then
        log_error "--replication-factor must be a positive integer, got '${REPLICATION_FACTOR}'"
        exit 1
    fi

    # Default configset name to collection name
    if [[ -z "$CONFIGSET_NAME" ]]; then
        CONFIGSET_NAME="$COLLECTION"
    fi
}

# ---------------------------------------------------------------------------
# Netrc-based auth helpers — avoid leaking credentials via process list
# ---------------------------------------------------------------------------
_SOLR_NETRC=""

create_solr_netrc() {
    if [[ -n "$SOLR_USER" && -n "$SOLR_PASS" ]]; then
        _SOLR_NETRC="$(mktemp "${PROJECT_ROOT}/.solr-netrc-XXXXXX")"
        chmod 0600 "$_SOLR_NETRC"
        local host
        host=$(echo "$SOLR_URL" | sed -E 's|^https?://||; s|:[0-9]+.*||; s|/.*||')
        printf 'machine %s login %s password %s\n' "$host" "$SOLR_USER" "$SOLR_PASS" > "$_SOLR_NETRC"
    fi
}

cleanup_solr_netrc() {
    if [[ -n "$_SOLR_NETRC" && -f "$_SOLR_NETRC" ]]; then
        rm -f "$_SOLR_NETRC"
        _SOLR_NETRC=""
    fi
}

trap cleanup_solr_netrc EXIT

# ---------------------------------------------------------------------------
# solr_curl — wrapper that adds auth if configured (via netrc file)
# ---------------------------------------------------------------------------
solr_curl() {
    local curl_args=(-sf --max-time 120)
    if [[ -n "$SOLR_USER" && -n "$SOLR_PASS" ]]; then
        create_solr_netrc
        curl_args+=(--netrc-file "$_SOLR_NETRC")
    fi
    local rc=0
    curl "${curl_args[@]}" "$@" || rc=$?
    cleanup_solr_netrc
    return $rc
}

# solr_curl_verbose — like solr_curl but without -f (so we can inspect HTTP errors)
solr_curl_verbose() {
    local curl_args=(-s --max-time 120)
    if [[ -n "$SOLR_USER" && -n "$SOLR_PASS" ]]; then
        create_solr_netrc
        curl_args+=(--netrc-file "$_SOLR_NETRC")
    fi
    local rc=0
    curl "${curl_args[@]}" "$@" || rc=$?
    cleanup_solr_netrc
    return $rc
}

# ---------------------------------------------------------------------------
# detect_solr_version — query Solr system info to determine major version
# ---------------------------------------------------------------------------
SOLR_MAJOR_VERSION=""

detect_solr_version() {
    log_info "Detecting Solr version..."

    local response=""
    response=$(solr_curl "${SOLR_URL}/solr/admin/info/system?wt=json" 2>&1) || {
        log_warn "Could not query Solr system info — version detection failed"
        return 1
    }

    local spec_version=""
    if command -v python3 &>/dev/null; then
        spec_version=$(python3 -c "
import json, sys
data = json.loads(sys.stdin.read())
print(data.get('lucene', {}).get('solr-spec-version', ''))
" <<< "$response" 2>/dev/null) || true
    elif command -v jq &>/dev/null; then
        spec_version=$(echo "$response" | jq -r '.lucene["solr-spec-version"] // ""' 2>/dev/null) || true
    else
        spec_version=$(echo "$response" | grep -o '"solr-spec-version":"[^"]*"' | head -1 | sed 's/"solr-spec-version":"//;s/"$//')
    fi

    if [[ -z "$spec_version" ]]; then
        log_warn "Could not parse Solr version from system info"
        return 1
    fi

    SOLR_MAJOR_VERSION="${spec_version%%.*}"
    log_info "Detected Solr version: ${spec_version} (major: ${SOLR_MAJOR_VERSION})"
}

# ---------------------------------------------------------------------------
# should_transform_schema — decide whether to apply HNSW param renames
# ---------------------------------------------------------------------------
should_transform_schema() {
    if [[ "$TRANSFORM_SCHEMA" == "yes" ]]; then
        return 0
    fi
    if [[ "$TRANSFORM_SCHEMA" == "no" ]]; then
        return 1
    fi
    # Auto-detect: transform if Solr major version >= 10
    if [[ -n "$SOLR_MAJOR_VERSION" ]] && [[ "$SOLR_MAJOR_VERSION" -ge 10 ]]; then
        return 0
    fi
    return 1
}

# ---------------------------------------------------------------------------
# check_solr_health — verify Solr is up
# ---------------------------------------------------------------------------
check_solr_health() {
    log_info "Checking Solr health (timeout: ${SOLR_HEALTH_TIMEOUT}s)..."

    local deadline=$((SECONDS + SOLR_HEALTH_TIMEOUT))

    while [[ $SECONDS -lt $deadline ]]; do
        if solr_curl "${SOLR_URL}/solr/admin/info/system?wt=json" &>/dev/null; then
            log_info "Solr is reachable"
            return 0
        fi
        if [[ $SECONDS -lt $deadline ]]; then
            log_warn "Solr not ready, retrying in 5s..."
            sleep 5
        fi
    done

    log_error "Solr health check failed after ${SOLR_HEALTH_TIMEOUT}s"
    return 1
}

# ---------------------------------------------------------------------------
# collection_exists — check if the target collection exists
# ---------------------------------------------------------------------------
collection_exists() {
    local response=""
    response=$(solr_curl "${SOLR_URL}/solr/admin/collections?action=LIST&wt=json" 2>&1) || {
        log_error "Failed to list collections"
        return 1
    }

    if echo "$response" | grep -q "\"${COLLECTION}\""; then
        return 0
    fi
    return 1
}

# ---------------------------------------------------------------------------
# upload_configset — upload a configset directory to Solr via API
# ---------------------------------------------------------------------------
upload_configset() {
    local config_dir="$1"
    local config_name="$2"

    log_info "Uploading configset '${config_name}' from ${config_dir}..."

    if [[ ! -d "$config_dir" ]]; then
        log_error "Configset directory not found: ${config_dir}"
        return 1
    fi

    if [[ "$DRY_RUN" == "1" ]]; then
        log_info "[DRY_RUN] Would upload configset '${config_name}' from ${config_dir}"
        return 0
    fi

    # Create a ZIP of the configset directory
    local zip_file="${PROJECT_ROOT}/.configset-upload-${TIMESTAMP}.zip"
    (cd "$config_dir" && zip -r "$zip_file" . -x '.*') &>/dev/null || {
        log_error "Failed to create configset ZIP from ${config_dir}"
        return 1
    }

    # Upload via Configsets API
    local response=""
    response=$(solr_curl_verbose \
        -X PUT \
        --header "Content-Type: application/octet-stream" \
        --data-binary "@${zip_file}" \
        "${SOLR_URL}/api/cluster/configs/${config_name}" 2>&1) || {
        rm -f "$zip_file"
        log_error "Failed to upload configset: ${response}"
        return 1
    }

    rm -f "$zip_file"

    # Check for errors in response
    if echo "$response" | grep -qi '"error"'; then
        log_error "Configset upload error: ${response}"
        return 1
    fi

    log_info "Configset '${config_name}' uploaded successfully"
}

# ---------------------------------------------------------------------------
# create_solr_collection — create collection via Collections API
# ---------------------------------------------------------------------------
create_solr_collection() {
    log_info "Creating collection '${COLLECTION}' (shards=${NUM_SHARDS}, rf=${REPLICATION_FACTOR}, configset=${CONFIGSET_NAME})..."

    if [[ "$DRY_RUN" == "1" ]]; then
        log_info "[DRY_RUN] Would create collection '${COLLECTION}'"
        return 0
    fi

    local response=""
    response=$(solr_curl_verbose \
        "${SOLR_URL}/solr/admin/collections?action=CREATE&name=${COLLECTION}&numShards=${NUM_SHARDS}&replicationFactor=${REPLICATION_FACTOR}&collection.configName=${CONFIGSET_NAME}&wt=json" 2>&1) || {
        log_error "Failed to create collection: ${response}"
        return 1
    }

    if echo "$response" | grep -qi '"error"'; then
        log_error "Collection creation error: ${response}"
        return 1
    fi

    log_info "Collection '${COLLECTION}' created successfully"
}

# ---------------------------------------------------------------------------
# count_lines — count total lines in source file
# ---------------------------------------------------------------------------
count_lines() {
    wc -l < "$SOURCE_FILE" | tr -d ' '
}

# ---------------------------------------------------------------------------
# transform_batch_for_solr10 — rename HNSW params in document JSON
# ---------------------------------------------------------------------------
transform_batch_for_solr10() {
    local input="$1"
    # Rename HNSW parameters that may appear in exported document data.
    # The primary renames for Solr 10:
    #   hnswMaxConnections → maxConnections
    #   hnswBeamWidth      → beamWidth
    if command -v python3 &>/dev/null; then
        python3 -c "
import sys

RENAMES = {
    'hnswMaxConnections': 'maxConnections',
    'hnswBeamWidth': 'beamWidth',
}

data = sys.stdin.read()
for old_key, new_key in RENAMES.items():
    data = data.replace(old_key, new_key)
print(data, end='')
" <<< "$input"
    else
        echo "$input" | sed \
            -e 's/hnswMaxConnections/maxConnections/g' \
            -e 's/hnswBeamWidth/beamWidth/g'
    fi
}

# ---------------------------------------------------------------------------
# send_batch — POST a batch of documents to Solr /update endpoint
# ---------------------------------------------------------------------------
send_batch() {
    local payload="$1"
    local attempt=0
    local max_attempts=$((MAX_RETRIES + 1))

    while [[ $attempt -lt $max_attempts ]]; do
        attempt=$((attempt + 1))

        local curl_args=(-s --max-time 300 -w "\n%{http_code}")
        if [[ -n "$SOLR_USER" && -n "$SOLR_PASS" ]]; then
            create_solr_netrc
            curl_args+=(--netrc-file "$_SOLR_NETRC")
        fi

        local raw_output=""
        raw_output=$(curl "${curl_args[@]}" \
            -X POST \
            -H "Content-Type: application/json" \
            -d "$payload" \
            "${SOLR_URL}/solr/${COLLECTION}/update?commit=true" 2>&1) || true
        cleanup_solr_netrc

        # Extract HTTP code (last line) and response body
        local http_code
        http_code=$(echo "$raw_output" | tail -1)
        local response
        response=$(echo "$raw_output" | sed '$d')

        if [[ "$http_code" == "200" ]]; then
            return 0
        fi

        if [[ $attempt -lt $max_attempts ]]; then
            log_warn "Batch update failed (HTTP ${http_code}, attempt ${attempt}/${max_attempts}), retrying in ${RETRY_DELAY}s..."
            sleep "$RETRY_DELAY"
        else
            log_error "Batch update failed after ${max_attempts} attempts (HTTP ${http_code}): ${response}"
            return 1
        fi
    done
}

# ---------------------------------------------------------------------------
# import_data — read JSONL file and import in batches
# ---------------------------------------------------------------------------
import_data() {
    local total_lines
    total_lines=$(count_lines)
    log_info "Source file: ${SOURCE_FILE} (${total_lines} documents)"

    if [[ "$total_lines" -eq 0 ]]; then
        log_warn "Source file is empty — nothing to import"
        return 0
    fi

    local do_transform=0
    if should_transform_schema; then
        do_transform=1
        log_info "Schema transformation enabled (Solr 10 HNSW param renames)"
    fi

    if [[ "$DRY_RUN" == "1" ]]; then
        log_info "[DRY_RUN] Would import ${total_lines} documents into '${COLLECTION}' in batches of ${BATCH_SIZE}"

        # Validate that source file contains valid JSON lines
        local invalid_lines=0
        local line_num=0
        while IFS= read -r line || [[ -n "$line" ]]; do
            line_num=$((line_num + 1))
            if [[ -z "$line" ]]; then
                continue
            fi
            if command -v python3 &>/dev/null; then
                echo "$line" | python3 -c "import json,sys; json.loads(sys.stdin.read().strip())" 2>/dev/null || {
                    invalid_lines=$((invalid_lines + 1))
                    if [[ $invalid_lines -le 5 ]]; then
                        log_warn "Invalid JSON at line ${line_num}"
                    fi
                }
            fi
        done < "$SOURCE_FILE"

        if [[ $invalid_lines -gt 0 ]]; then
            log_warn "[DRY_RUN] Found ${invalid_lines} invalid JSON line(s) out of ${total_lines}"
        else
            log_info "[DRY_RUN] All ${total_lines} lines contain valid JSON"
        fi
        return 0
    fi

    # Progress tracking file for --resume support
    local progress_file="${SOURCE_FILE}.import-progress"
    local skip_lines=0

    if [[ "$RESUME" -eq 1 && -f "$progress_file" ]]; then
        skip_lines=$(cat "$progress_file" 2>/dev/null || echo "0")
        if [[ "$skip_lines" -gt 0 ]]; then
            log_info "Resuming from line ${skip_lines} (previously imported)"
        fi
    fi

    local imported=0
    local failed_batches=0
    local batch_docs=""
    local batch_count=0
    local line_num=0
    local skipped=0

    while IFS= read -r line || [[ -n "$line" ]]; do
        line_num=$((line_num + 1))

        # Skip empty lines
        if [[ -z "$line" ]]; then
            continue
        fi

        # Resume support: skip already-imported lines
        if [[ $line_num -le $skip_lines ]]; then
            skipped=$((skipped + 1))
            continue
        fi

        # Accumulate docs into batch
        if [[ -z "$batch_docs" ]]; then
            batch_docs="$line"
        else
            batch_docs="${batch_docs},${line}"
        fi
        batch_count=$((batch_count + 1))

        # Send batch when full
        if [[ $batch_count -ge $BATCH_SIZE ]]; then
            local payload="[${batch_docs}]"

            if [[ $do_transform -eq 1 ]]; then
                payload=$(transform_batch_for_solr10 "$payload")
            fi

            if send_batch "$payload"; then
                imported=$((imported + batch_count))
                echo "$line_num" > "$progress_file"
            else
                failed_batches=$((failed_batches + 1))
                EXIT_CODE=2
                log_warn "Batch failed at lines $((line_num - batch_count + 1))-${line_num}"
            fi

            batch_docs=""
            batch_count=0

            # Progress reporting
            local total_processed=$((imported + skipped))
            if [[ $((total_processed % (BATCH_SIZE * 10))) -lt $BATCH_SIZE ]]; then
                log_info "Progress: ${imported}/${total_lines} documents imported"
            fi
        fi
    done < "$SOURCE_FILE"

    # Send remaining docs in the last partial batch
    if [[ $batch_count -gt 0 ]]; then
        local payload="[${batch_docs}]"

        if [[ $do_transform -eq 1 ]]; then
            payload=$(transform_batch_for_solr10 "$payload")
        fi

        if send_batch "$payload"; then
            imported=$((imported + batch_count))
            echo "$line_num" > "$progress_file"
        else
            failed_batches=$((failed_batches + 1))
            EXIT_CODE=2
            log_warn "Final batch failed at lines $((line_num - batch_count + 1))-${line_num}"
        fi
    fi

    # Clean up progress file on full success
    if [[ $failed_batches -eq 0 && -f "$progress_file" ]]; then
        rm -f "$progress_file"
    fi

    log_info "Import complete: ${imported}/${total_lines} documents imported"
    if [[ $skipped -gt 0 ]]; then
        log_info "Skipped ${skipped} previously imported documents (--resume)"
    fi
    if [[ $failed_batches -gt 0 ]]; then
        log_warn "${failed_batches} batch(es) failed — use --resume to retry"
    fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    parse_args "$@"

    log_info "========== Aithena Solr Import START (${TIMESTAMP}) =========="
    log_info "SOLR_URL=${SOLR_URL}  COLLECTION=${COLLECTION}  SOURCE=${SOURCE_FILE}"
    log_info "BATCH_SIZE=${BATCH_SIZE}  MAX_RETRIES=${MAX_RETRIES}  DRY_RUN=${DRY_RUN}"
    if [[ -n "$SOLR_USER" ]]; then
        log_info "Auth: Basic Auth as ${SOLR_USER}"
    else
        log_info "Auth: none (set SOLR_AUTH_USER/SOLR_AUTH_PASS for authenticated access)"
    fi

    # --- Pre-flight checks ---
    require_cmd curl

    if ! command -v python3 &>/dev/null && ! command -v jq &>/dev/null; then
        log_error "Either python3 or jq is required to parse JSON. Install one and retry."
        exit 1
    fi

    # --- Verify Solr is reachable ---
    check_solr_health || exit 1

    # --- Detect Solr version ---
    detect_solr_version || log_warn "Could not detect Solr version — schema transformation will be skipped unless --transform-schema is set"

    # --- Upload configset if requested ---
    if [[ -n "$CONFIGSET_DIR" ]]; then
        upload_configset "$CONFIGSET_DIR" "$CONFIGSET_NAME" || exit 1
    fi

    # --- Create collection if requested ---
    if [[ "$CREATE_COLLECTION" -eq 1 ]]; then
        if collection_exists; then
            log_info "Collection '${COLLECTION}' already exists — skipping creation"
        else
            create_solr_collection || exit 1
        fi
    else
        # Verify collection exists
        if ! collection_exists; then
            log_error "Collection '${COLLECTION}' does not exist. Use --create-collection to create it."
            exit 1
        fi
        log_info "Collection '${COLLECTION}' exists"
    fi

    # --- Import data ---
    import_data

    log_info "========== Aithena Solr Import END (exit=${EXIT_CODE}) =========="

    return "$EXIT_CODE"
}

main "$@"

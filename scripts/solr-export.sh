#!/usr/bin/env bash
# =============================================================================
# Aithena — Solr Collection Export / Backup
# =============================================================================
# Exports Solr collection data (JSON Lines) and configset (ZIP) for migration,
# disaster recovery, or Solr 9→10 upgrade preparation.
#
# Usage:
#   ./scripts/solr-export.sh                                      # export default collection
#   ./scripts/solr-export.sh --collection books --dest /mnt/exports
#   ./scripts/solr-export.sh --since 2026-01-01T00:00:00Z         # incremental by date
#   ./scripts/solr-export.sh --data-only                          # skip configset export
#   ./scripts/solr-export.sh --config-only                        # skip data export
#   ./scripts/solr-export.sh --dry-run                            # log actions, write nothing
#
# Options:
#   --collection <name>     Collection to export (default: books)
#   --dest <path>           Output directory (default: /source/exports)
#   --since <ISO-8601>      Export only docs with date >= this value (incremental)
#   --batch-size <n>        Documents per cursor page (default: 500)
#   --data-only             Export data only, skip configset
#   --config-only           Export configset only, skip data
#   --dry-run               Log what would be done without writing files
#   --help                  Show this help message
#
# Environment variables:
#   SOLR_URL                Solr HTTP base URL (default: http://localhost:8983)
#   SOLR_AUTH_USER          Solr Basic Auth username (optional)
#   SOLR_AUTH_PASS          Solr Basic Auth password (optional)
#   SOLR_ADMIN_USER         Fallback admin username if SOLR_AUTH_USER is unset
#   SOLR_ADMIN_PASS         Fallback admin password if SOLR_AUTH_PASS is unset
#   EXPORT_DEST             Base export directory (default: /source/exports)
#   SOLR_HEALTH_TIMEOUT     Seconds to wait for Solr health (default: 30)
#   PROJECT_ROOT            Repository root (default: /source/aithena)
#   LOG_FILE                Log file (default: /var/log/aithena-solr-export.log)
#   DRY_RUN                 Set to 1 to skip actual writes
#
# Output structure:
#   <dest>/<collection>-<timestamp>/
#     data.jsonl              — One JSON document per line
#     configset.zip           — Collection configset from ZooKeeper
#     manifest.json           — Export metadata (date, collection, doc count, etc.)
#     data.jsonl.sha256       — Checksum sidecar
#     configset.zip.sha256    — Checksum sidecar
#
# Exit codes:
#   0  Export succeeded
#   1  Fatal error
#   2  Partial failure (warnings only)
#
# See also:
#   scripts/backup-high.sh      — Tier 2 Solr index backup (Collections API BACKUP)
#   docs/prd/solr10-migration-prd.md — Solr 10 migration context
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SOLR_URL="${SOLR_URL:-http://localhost:8983}"
COLLECTION="${COLLECTION:-books}"
EXPORT_DEST="${EXPORT_DEST:-/source/exports}"
BATCH_SIZE="${BATCH_SIZE:-500}"
SINCE=""
DATA_ONLY=0
CONFIG_ONLY=0
DRY_RUN="${DRY_RUN:-0}"
SOLR_HEALTH_TIMEOUT="${SOLR_HEALTH_TIMEOUT:-30}"
PROJECT_ROOT="${PROJECT_ROOT:-/source/aithena}"

TIMESTAMP="$(date -u +%Y%m%d-%H%M%S)"
LOG_FILE="${LOG_FILE:-/var/log/aithena-solr-export.log}"
EXIT_CODE=0

# Restrictive umask — exports may contain sensitive data
umask 077

# --- Resolve Solr auth: prefer SOLR_AUTH_USER/PASS, fall back to SOLR_ADMIN ---
SOLR_USER="${SOLR_AUTH_USER:-${SOLR_ADMIN_USER:-}}"
SOLR_PASS="${SOLR_AUTH_PASS:-${SOLR_ADMIN_PASS:-}}"

# --- Ensure log file is writable; fall back to project-local if not ---
_init_log() {
    mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
    if ! touch "$LOG_FILE" 2>/dev/null; then
        LOG_FILE="${PROJECT_ROOT}/solr-export.log"
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
    msg="$(date -u '+%Y-%m-%dT%H:%M:%SZ') [${level}] [solr-export] $*"
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
            --collection)
                [[ $# -lt 2 ]] && { log_error "--collection requires a value"; exit 1; }
                COLLECTION="$2"; shift 2 ;;
            --dest)
                [[ $# -lt 2 ]] && { log_error "--dest requires a path"; exit 1; }
                EXPORT_DEST="$2"; shift 2 ;;
            --since)
                [[ $# -lt 2 ]] && { log_error "--since requires an ISO-8601 date"; exit 1; }
                SINCE="$2"; shift 2 ;;
            --batch-size)
                [[ $# -lt 2 ]] && { log_error "--batch-size requires a number"; exit 1; }
                BATCH_SIZE="$2"; shift 2 ;;
            --data-only)
                DATA_ONLY=1; shift ;;
            --config-only)
                CONFIG_ONLY=1; shift ;;
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

    # Validate mutually exclusive flags
    if [[ "$DATA_ONLY" -eq 1 && "$CONFIG_ONLY" -eq 1 ]]; then
        log_error "--data-only and --config-only are mutually exclusive"
        exit 1
    fi

    # Validate batch size
    if ! [[ "$BATCH_SIZE" =~ ^[0-9]+$ ]] || [[ "$BATCH_SIZE" -lt 1 ]]; then
        log_error "BATCH_SIZE must be a positive integer, got '${BATCH_SIZE}'"
        exit 1
    fi

    # Validate SINCE date format (basic check)
    if [[ -n "$SINCE" ]] && ! [[ "$SINCE" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2} ]]; then
        log_error "--since must be an ISO-8601 date (e.g. 2026-01-01T00:00:00Z), got '${SINCE}'"
        exit 1
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

# ---------------------------------------------------------------------------
# check_solr_health — verify Solr is up and collection exists
# ---------------------------------------------------------------------------
check_solr_health() {
    log_info "Checking Solr health (timeout: ${SOLR_HEALTH_TIMEOUT}s)..."

    local deadline=$((SECONDS + SOLR_HEALTH_TIMEOUT))

    while [[ $SECONDS -lt $deadline ]]; do
        local response=""
        if response=$(solr_curl "${SOLR_URL}/solr/admin/collections?action=CLUSTERSTATUS&wt=json" 2>/dev/null); then
            if echo "$response" | grep -q "\"${COLLECTION}\""; then
                log_info "Solr healthy, collection '${COLLECTION}' exists"
                return 0
            elif echo "$response" | grep -q '"live_nodes"'; then
                log_error "Solr is up but collection '${COLLECTION}' not found"
                return 1
            fi
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
# get_doc_count — retrieve total document count for the collection
# ---------------------------------------------------------------------------
get_doc_count() {
    local fq_param=""
    if [[ -n "$SINCE" ]]; then
        fq_param="&fq=date:[${SINCE}%20TO%20*]"
    fi

    local response=""
    response=$(solr_curl \
        "${SOLR_URL}/solr/${COLLECTION}/select?q=*:*&rows=0&wt=json${fq_param}" 2>&1) || {
        log_error "Failed to query document count: ${response}"
        return 1
    }

    # Extract numFound from JSON response
    local count
    count=$(echo "$response" | grep -o '"numFound":[0-9]*' | head -1 | cut -d: -f2)
    if [[ -z "$count" ]]; then
        log_error "Could not parse numFound from Solr response"
        return 1
    fi

    echo "$count"
}

# ---------------------------------------------------------------------------
# export_data — paginated export using cursorMark for large datasets
# ---------------------------------------------------------------------------
export_data() {
    local output_file="$1"

    log_info "Exporting collection data to ${output_file}..."

    if [[ "$DRY_RUN" == "1" ]]; then
        log_info "[DRY_RUN] Would export data from '${COLLECTION}' to ${output_file}"
        return 0
    fi

    local fq_param=""
    if [[ -n "$SINCE" ]]; then
        fq_param="&fq=date:[${SINCE}+TO+*]"
        log_info "Incremental export: documents with date >= ${SINCE}"
    fi

    local cursor_mark="*"
    local total_exported=0
    local page=0

    # Truncate output file
    : > "$output_file"

    while true; do
        page=$((page + 1))
        local encoded_cursor
        encoded_cursor=$(printf '%s' "$cursor_mark" | sed 's/\+/%2B/g; s/\//%2F/g; s/=/%3D/g')

        local response=""
        response=$(solr_curl \
            "${SOLR_URL}/solr/${COLLECTION}/select?q=*:*&rows=${BATCH_SIZE}&sort=id+asc&wt=json&cursorMark=${encoded_cursor}${fq_param}" 2>&1) || {
            log_error "Solr query failed on page ${page}: ${response}"
            return 1
        }

        # Extract nextCursorMark
        local next_cursor
        next_cursor=$(echo "$response" | grep -o '"nextCursorMark":"[^"]*"' | head -1 | sed 's/"nextCursorMark":"//;s/"$//')

        # Extract docs array and write each doc as a JSON line
        # Use python if available for reliable JSON parsing, fall back to jq
        local doc_count=0
        if command -v python3 &>/dev/null; then
            doc_count=$(python3 -c "
import json, sys
data = json.loads(sys.stdin.read())
docs = data.get('response', {}).get('docs', [])
with open(sys.argv[1], 'a') as f:
    for doc in docs:
        f.write(json.dumps(doc, ensure_ascii=False) + '\n')
print(len(docs))
" "$output_file" <<< "$response") || {
                log_error "Failed to parse Solr response on page ${page}"
                return 1
            }
        elif command -v jq &>/dev/null; then
            doc_count=$(echo "$response" | jq -c '.response.docs[]' >> "$output_file" 2>/dev/null && \
                echo "$response" | jq '.response.docs | length') || {
                log_error "Failed to parse Solr response on page ${page}"
                return 1
            }
        else
            log_error "Neither python3 nor jq found — cannot parse JSON response"
            return 1
        fi

        total_exported=$((total_exported + doc_count))

        if [[ $((page % 10)) -eq 0 ]]; then
            log_info "Progress: exported ${total_exported} documents (page ${page})..."
        fi

        # Stop when cursorMark doesn't change (end of results)
        if [[ -z "$next_cursor" || "$next_cursor" == "$cursor_mark" ]]; then
            break
        fi
        cursor_mark="$next_cursor"
    done

    log_info "Data export complete: ${total_exported} documents in ${page} page(s)"
    echo "$total_exported"
}

# ---------------------------------------------------------------------------
# export_configset — download collection configset via Solr Configsets API
# ---------------------------------------------------------------------------
export_configset() {
    local output_file="$1"

    log_info "Exporting configset for collection '${COLLECTION}'..."

    if [[ "$DRY_RUN" == "1" ]]; then
        log_info "[DRY_RUN] Would export configset for '${COLLECTION}' to ${output_file}"
        return 0
    fi

    # First, determine the configset name from collection status
    local cluster_response=""
    cluster_response=$(solr_curl \
        "${SOLR_URL}/solr/admin/collections?action=CLUSTERSTATUS&collection=${COLLECTION}&wt=json" 2>&1) || {
        log_error "Failed to get cluster status: ${cluster_response}"
        return 1
    }

    local configset_name
    configset_name=$(echo "$cluster_response" | grep -o '"configName":"[^"]*"' | head -1 | sed 's/"configName":"//;s/"$//')
    if [[ -z "$configset_name" ]]; then
        log_warn "Could not determine configset name; trying collection name '${COLLECTION}'"
        configset_name="$COLLECTION"
    fi
    log_info "Configset name: ${configset_name}"

    # Download configset as ZIP via the Configsets API
    local http_code
    local curl_args=(-s --max-time 120 -o "$output_file" -w "%{http_code}")
    if [[ -n "$SOLR_USER" && -n "$SOLR_PASS" ]]; then
        create_solr_netrc
        curl_args+=(--netrc-file "$_SOLR_NETRC")
    fi

    http_code=$(curl "${curl_args[@]}" \
        "${SOLR_URL}/api/cluster/configs/${configset_name}?omitHeader=true" 2>&1)
    local curl_rc=$?
    cleanup_solr_netrc

    if [[ $curl_rc -ne 0 ]]; then
        log_error "Failed to download configset ZIP"
        return 1
    fi

    if [[ "$http_code" != "200" ]]; then
        log_error "Configset download returned HTTP ${http_code}"
        rm -f "$output_file"
        return 1
    fi

    # Verify it's a valid ZIP (if 'file' command is available)
    if command -v file &>/dev/null; then
        if ! file "$output_file" | grep -qi 'zip'; then
            log_warn "Downloaded configset may not be a valid ZIP file"
            EXIT_CODE=2
        fi
    else
        log_warn "'file' command not found — skipping ZIP validation for configset"
    fi

    local zip_size
    zip_size=$(stat -c%s "$output_file" 2>/dev/null || stat -f%z "$output_file" 2>/dev/null || echo "unknown")
    log_info "Configset exported: ${output_file} (${zip_size} bytes)"
}

# ---------------------------------------------------------------------------
# write_manifest — create manifest.json with export metadata
# ---------------------------------------------------------------------------
write_manifest() {
    local manifest_file="$1"
    local doc_count="$2"
    local export_dir="$3"
    local has_data="$4"
    local has_config="$5"

    log_info "Writing export manifest..."

    if [[ "$DRY_RUN" == "1" ]]; then
        log_info "[DRY_RUN] Would write manifest to ${manifest_file}"
        return 0
    fi

    local data_sha=""
    local config_sha=""
    local data_size=""
    local config_size=""

    if [[ "$has_data" == "true" && -f "${export_dir}/data.jsonl" ]]; then
        data_sha=$(sha256sum "${export_dir}/data.jsonl" | cut -d' ' -f1)
        data_size=$(stat -c%s "${export_dir}/data.jsonl" 2>/dev/null || stat -f%z "${export_dir}/data.jsonl" 2>/dev/null || echo "0")
    fi

    if [[ "$has_config" == "true" && -f "${export_dir}/configset.zip" ]]; then
        config_sha=$(sha256sum "${export_dir}/configset.zip" | cut -d' ' -f1)
        config_size=$(stat -c%s "${export_dir}/configset.zip" 2>/dev/null || stat -f%z "${export_dir}/configset.zip" 2>/dev/null || echo "0")
    fi

    # Get schema version from Solr if possible
    local schema_version=""
    local schema_response=""
    if schema_response=$(solr_curl "${SOLR_URL}/solr/${COLLECTION}/schema?wt=json" 2>/dev/null); then
        schema_version=$(echo "$schema_response" | grep -o '"version":[0-9.]*' | head -1 | cut -d: -f2)
    fi

    if command -v python3 &>/dev/null; then
        python3 -c "
import json, sys
manifest = {
    'export_date': '$(date -u '+%Y-%m-%dT%H:%M:%SZ')',
    'export_timestamp': '${TIMESTAMP}',
    'solr_url': '${SOLR_URL}',
    'collection': '${COLLECTION}',
    'document_count': ${doc_count:-0},
    'batch_size': ${BATCH_SIZE},
    'incremental_since': '${SINCE}' if '${SINCE}' else None,
    'schema_version': '${schema_version}' if '${schema_version}' else None,
    'files': {}
}
if '${has_data}' == 'true':
    manifest['files']['data.jsonl'] = {
        'sha256': '${data_sha}',
        'size_bytes': int('${data_size}') if '${data_size}'.isdigit() else 0
    }
if '${has_config}' == 'true':
    manifest['files']['configset.zip'] = {
        'sha256': '${config_sha}',
        'size_bytes': int('${config_size}') if '${config_size}'.isdigit() else 0
    }
json.dump(manifest, open('${manifest_file}', 'w'), indent=2)
" || {
            log_error "Failed to write manifest with python3"
            return 1
        }
    else
        # Fallback: write JSON manually
        local since_field="null"
        [[ -n "$SINCE" ]] && since_field="\"${SINCE}\""
        local sv_field="null"
        [[ -n "$schema_version" ]] && sv_field="\"${schema_version}\""

        cat > "$manifest_file" <<EOF
{
  "export_date": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')",
  "export_timestamp": "${TIMESTAMP}",
  "solr_url": "${SOLR_URL}",
  "collection": "${COLLECTION}",
  "document_count": ${doc_count:-0},
  "batch_size": ${BATCH_SIZE},
  "incremental_since": ${since_field},
  "schema_version": ${sv_field},
  "files": {
EOF
        local comma=""
        if [[ "$has_data" == "true" ]]; then
            cat >> "$manifest_file" <<EOF
    "data.jsonl": {
      "sha256": "${data_sha}",
      "size_bytes": ${data_size:-0}
    }
EOF
            comma=","
        fi
        if [[ "$has_config" == "true" ]]; then
            [[ -n "$comma" ]] && echo "    ," >> "$manifest_file"
            cat >> "$manifest_file" <<EOF
    "configset.zip": {
      "sha256": "${config_sha}",
      "size_bytes": ${config_size:-0}
    }
EOF
        fi
        cat >> "$manifest_file" <<EOF
  }
}
EOF
    fi

    log_info "Manifest written: ${manifest_file}"
}

# ---------------------------------------------------------------------------
# write_checksum — write SHA-256 sidecar for a file
# ---------------------------------------------------------------------------
write_checksum() {
    local target="$1"
    if [[ -f "$target" ]]; then
        sha256sum "$target" > "${target}.sha256"
        log_info "Checksum: ${target}.sha256"
    fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    parse_args "$@"

    log_info "========== Aithena Solr Export START (${TIMESTAMP}) =========="
    log_info "SOLR_URL=${SOLR_URL}  COLLECTION=${COLLECTION}  DEST=${EXPORT_DEST}"
    log_info "BATCH_SIZE=${BATCH_SIZE}  SINCE=${SINCE:-<full export>}  DRY_RUN=${DRY_RUN}"
    if [[ -n "$SOLR_USER" ]]; then
        log_info "Auth: Basic Auth as ${SOLR_USER}"
    else
        log_info "Auth: none (set SOLR_AUTH_USER/SOLR_AUTH_PASS for authenticated access)"
    fi

    # --- Pre-flight checks ---
    require_cmd curl
    require_cmd sha256sum

    if ! command -v python3 &>/dev/null && ! command -v jq &>/dev/null; then
        log_error "Either python3 or jq is required to parse JSON. Install one and retry."
        exit 1
    fi

    # --- Create export directory ---
    local export_dir="${EXPORT_DEST}/${COLLECTION}-${TIMESTAMP}"

    if [[ "$DRY_RUN" == "1" ]]; then
        log_info "[DRY_RUN] Would create export directory: ${export_dir}"
    else
        mkdir -p "$export_dir"
    fi

    # --- Verify Solr is reachable ---
    check_solr_health || exit 1

    # --- Get document count ---
    local doc_count=0
    if [[ "$CONFIG_ONLY" -eq 0 ]]; then
        doc_count=$(get_doc_count) || exit 1
        log_info "Documents to export: ${doc_count}"
    fi

    # --- Export data ---
    local has_data="false"
    if [[ "$CONFIG_ONLY" -eq 0 ]]; then
        local data_file="${export_dir}/data.jsonl"
        local exported_count
        exported_count=$(export_data "$data_file") || exit 1
        if [[ "$DRY_RUN" != "1" ]]; then
            write_checksum "$data_file"
            has_data="true"
            doc_count="${exported_count:-$doc_count}"
        fi
    fi

    # --- Export configset ---
    local has_config="false"
    if [[ "$DATA_ONLY" -eq 0 ]]; then
        local config_file="${export_dir}/configset.zip"
        export_configset "$config_file" || {
            log_warn "Configset export failed — continuing with partial export"
            EXIT_CODE=2
        }
        if [[ "$DRY_RUN" != "1" && -f "$config_file" ]]; then
            write_checksum "$config_file"
            has_config="true"
        fi
    fi

    # --- Write manifest ---
    write_manifest "${export_dir}/manifest.json" "$doc_count" "$export_dir" "$has_data" "$has_config"

    log_info "========== Aithena Solr Export END (exit=${EXIT_CODE}) =========="
    if [[ "$DRY_RUN" != "1" ]]; then
        log_info "Export directory: ${export_dir}"
    fi

    return "$EXIT_CODE"
}

main "$@"

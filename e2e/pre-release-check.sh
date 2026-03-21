#!/bin/sh
# pre-release-check.sh — Analyze Docker Compose logs for pre-release findings
# Reads from stdin (piped) or from a file argument.
# Outputs a JSON array of findings to stdout.
# Exit codes: 0 = clean, 1 = errors found, 2 = warnings (no errors)
set -eu

usage() {
  cat <<'EOF'
Usage: docker compose logs --no-color | ./e2e/pre-release-check.sh [OPTIONS]
       ./e2e/pre-release-check.sh [OPTIONS] <logfile>

Scans Docker Compose logs for 9 categories of findings and outputs JSON.

Options:
  --version-file PATH   Path to VERSION file (default: ./VERSION)
  --startup-threshold N  Seconds to flag slow startups (default: 30)
  --ignore-startup-window N  Seconds after first log line to ignore connection
                             retries (default: 60)
  -h, --help            Show this help

Categories:
  1. crash        — exit codes != 0, FATAL, panic, segfault
  2. deprecation  — deprecated, will be removed, no longer supported
  3. version      — service version != VERSION file, unknown versions
  4. slow_startup — services taking > threshold to become healthy
  5. connection   — retrying, connection refused, reconnect (after startup)
  6. security     — insecure, TLS errors, certificate, auth failures
  7. memory       — OOM, memory pressure, heap, GC pressure
  8. config       — missing env, default value, not configured
  9. dependency   — pip/npm warnings, outdated packages
EOF
}

VERSION_FILE="./VERSION"
STARTUP_THRESHOLD=30
STARTUP_WINDOW=60

while [ $# -gt 0 ]; do
  case "$1" in
    --version-file)  VERSION_FILE="$2"; shift 2 ;;
    --startup-threshold) STARTUP_THRESHOLD="$2"; shift 2 ;;
    --ignore-startup-window) STARTUP_WINDOW="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    -*) echo "Unknown option: $1" >&2; usage >&2; exit 1 ;;
    *)  break ;;
  esac
done

# Read logs from file argument or stdin
if [ $# -ge 1 ] && [ -f "$1" ]; then
  LOG_FILE="$1"
else
  LOG_FILE="$(mktemp)"
  cat > "$LOG_FILE"
  CLEANUP_TMP=1
fi

cleanup() {
  if [ "${CLEANUP_TMP:-0}" = "1" ] && [ -f "$LOG_FILE" ]; then
    rm -f "$LOG_FILE"
  fi
}
trap cleanup EXIT

# Load expected version
EXPECTED_VERSION=""
if [ -f "$VERSION_FILE" ]; then
  EXPECTED_VERSION="$(cat "$VERSION_FILE" | tr -d '[:space:]')"
fi

# JSON escaping helper — escapes backslash, double quotes, and control chars
json_escape() {
  printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' -e 's/	/\\t/g' | tr -d '\000-\011\013-\037' | tr '\n' ' '
}

# Extract service name from a Docker Compose log line (format: "service-name  | ...")
extract_service() {
  printf '%s' "$1" | sed -n 's/^\([a-zA-Z0-9_-]*\)[[:space:]]*|.*/\1/p'
}

# Finding accumulator
FINDINGS=""
FINDING_COUNT=0
ERROR_COUNT=0
WARNING_COUNT=0

add_finding() {
  _cat="$1"
  _sev="$2"
  _svc="$3"
  _msg="$(json_escape "$4")"
  _line="$5"

  if [ "$FINDING_COUNT" -gt 0 ]; then
    FINDINGS="${FINDINGS},"
  fi

  FINDINGS="${FINDINGS}{\"category\":\"${_cat}\",\"severity\":\"${_sev}\",\"service\":\"${_svc}\",\"message\":\"${_msg}\",\"line\":${_line}}"
  FINDING_COUNT=$((FINDING_COUNT + 1))

  case "$_sev" in
    error) ERROR_COUNT=$((ERROR_COUNT + 1)) ;;
    warning) WARNING_COUNT=$((WARNING_COUNT + 1)) ;;
  esac
}

# --- Category 1: Crash/fatal errors ---
scan_crashes() {
  LINE_NUM=0
  while IFS= read -r line; do
    LINE_NUM=$((LINE_NUM + 1))
    svc="$(extract_service "$line")"
    case "$line" in
      *FATAL*|*fatal*|*panic*|*PANIC*|*segfault*|*SEGFAULT*|*Segmentation\ fault*)
        add_finding "crash" "error" "${svc:-unknown}" "$line" "$LINE_NUM"
        ;;
      *"exit code"*|*"exited with code"*)
        # Only flag non-zero exit codes
        case "$line" in
          *"exit code 0"*|*"exited with code 0"*) ;;
          *) add_finding "crash" "error" "${svc:-unknown}" "$line" "$LINE_NUM" ;;
        esac
        ;;
      *"killed"*|*"KILLED"*|*"OOMKilled"*)
        add_finding "crash" "error" "${svc:-unknown}" "$line" "$LINE_NUM"
        ;;
    esac
  done < "$LOG_FILE"
}

# --- Category 2: Deprecation warnings ---
scan_deprecations() {
  LINE_NUM=0
  while IFS= read -r line; do
    LINE_NUM=$((LINE_NUM + 1))
    svc="$(extract_service "$line")"
    lc_line="$(printf '%s' "$line" | tr '[:upper:]' '[:lower:]')"
    case "$lc_line" in
      *"deprecated"*|*"will be removed"*|*"no longer supported"*|*"end of life"*|*"end-of-life"*)
        add_finding "deprecation" "warning" "${svc:-unknown}" "$line" "$LINE_NUM"
        ;;
    esac
  done < "$LOG_FILE"
}

# --- Category 3: Version mismatches ---
scan_versions() {
  if [ -z "$EXPECTED_VERSION" ]; then
    return
  fi
  LINE_NUM=0
  while IFS= read -r line; do
    LINE_NUM=$((LINE_NUM + 1))
    svc="$(extract_service "$line")"
    lc_line="$(printf '%s' "$line" | tr '[:upper:]' '[:lower:]')"
    case "$lc_line" in
      *"version"*"unknown"*|*"unknown"*"version"*)
        add_finding "version" "warning" "${svc:-unknown}" "$line" "$LINE_NUM"
        ;;
      *"version:"*|*"version="*)
        # Check if expected version is mentioned; if a version line exists
        # but doesn't contain the expected version, flag it
        case "$line" in
          *"$EXPECTED_VERSION"*) ;;
          *) add_finding "version" "info" "${svc:-unknown}" "$line" "$LINE_NUM" ;;
        esac
        ;;
    esac
  done < "$LOG_FILE"
}

# --- Category 4: Slow startups ---
scan_slow_startups() {
  LINE_NUM=0
  while IFS= read -r line; do
    LINE_NUM=$((LINE_NUM + 1))
    svc="$(extract_service "$line")"
    lc_line="$(printf '%s' "$line" | tr '[:upper:]' '[:lower:]')"
    case "$lc_line" in
      *"health"*"unhealthy"*|*"not yet healthy"*|*"health check"*"fail"*)
        add_finding "slow_startup" "warning" "${svc:-unknown}" "$line" "$LINE_NUM"
        ;;
      *"started"*|*"ready"*|*"listening"*)
        # Look for startup time indicators exceeding threshold
        _seconds=""
        _seconds="$(printf '%s' "$line" | sed -n 's/.*[^0-9]\([0-9][0-9]*\)[[:space:]]*s\(ec\(ond\)\{0,1\}\)\{0,1\}[^a-zA-Z].*/\1/p' | head -1)"
        if [ -n "$_seconds" ] && [ "$_seconds" -gt "$STARTUP_THRESHOLD" ] 2>/dev/null; then
          add_finding "slow_startup" "warning" "${svc:-unknown}" "Startup took ${_seconds}s (threshold: ${STARTUP_THRESHOLD}s): $line" "$LINE_NUM"
        fi
        ;;
    esac
  done < "$LOG_FILE"
}

# --- Category 5: Connection retries (after startup window) ---
scan_connection_retries() {
  TOTAL_LINES="$(wc -l < "$LOG_FILE")"
  if [ "$TOTAL_LINES" -eq 0 ]; then
    return
  fi
  # Skip the first N lines as startup window (heuristic: first STARTUP_WINDOW lines ≈ startup)
  SKIP_LINES=$STARTUP_WINDOW
  LINE_NUM=0
  while IFS= read -r line; do
    LINE_NUM=$((LINE_NUM + 1))
    if [ "$LINE_NUM" -le "$SKIP_LINES" ]; then
      continue
    fi
    svc="$(extract_service "$line")"
    lc_line="$(printf '%s' "$line" | tr '[:upper:]' '[:lower:]')"
    case "$lc_line" in
      *"retrying"*|*"connection refused"*|*"reconnect"*|*"retry"*"attempt"*|*"connection reset"*|*"connection timed out"*)
        add_finding "connection" "warning" "${svc:-unknown}" "$line" "$LINE_NUM"
        ;;
    esac
  done < "$LOG_FILE"
}

# --- Category 6: Security warnings ---
scan_security() {
  LINE_NUM=0
  while IFS= read -r line; do
    LINE_NUM=$((LINE_NUM + 1))
    svc="$(extract_service "$line")"
    lc_line="$(printf '%s' "$line" | tr '[:upper:]' '[:lower:]')"
    case "$lc_line" in
      *"insecure"*|*"certificate"*"error"*|*"certificate"*"expired"*|*"certificate"*"invalid"*|*"tls"*"error"*|*"tls"*"fail"*|*"ssl"*"error"*|*"auth"*"fail"*|*"authentication failed"*|*"unauthorized"*|*"permission denied"*)
        add_finding "security" "error" "${svc:-unknown}" "$line" "$LINE_NUM"
        ;;
      *"self-signed"*|*"insecure mode"*|*"without tls"*|*"no ssl"*)
        add_finding "security" "warning" "${svc:-unknown}" "$line" "$LINE_NUM"
        ;;
    esac
  done < "$LOG_FILE"
}

# --- Category 7: Memory pressure ---
scan_memory() {
  LINE_NUM=0
  while IFS= read -r line; do
    LINE_NUM=$((LINE_NUM + 1))
    svc="$(extract_service "$line")"
    lc_line="$(printf '%s' "$line" | tr '[:upper:]' '[:lower:]')"
    case "$lc_line" in
      *"oom"*|*"out of memory"*|*"cannot allocate memory"*|*"memory allocation failed"*)
        add_finding "memory" "error" "${svc:-unknown}" "$line" "$LINE_NUM"
        ;;
      *"memory pressure"*|*"heap"*"overflow"*|*"gc pressure"*|*"gc overhead"*|*"low memory"*|*"memory warning"*)
        add_finding "memory" "warning" "${svc:-unknown}" "$line" "$LINE_NUM"
        ;;
    esac
  done < "$LOG_FILE"
}

# --- Category 8: Configuration issues ---
scan_config() {
  LINE_NUM=0
  while IFS= read -r line; do
    LINE_NUM=$((LINE_NUM + 1))
    svc="$(extract_service "$line")"
    lc_line="$(printf '%s' "$line" | tr '[:upper:]' '[:lower:]')"
    case "$lc_line" in
      *"missing env"*|*"missing environment"*|*"not configured"*|*"not set"*|*"using default"*|*"default value"*|*"fallback"*"config"*)
        add_finding "config" "warning" "${svc:-unknown}" "$line" "$LINE_NUM"
        ;;
      *"required"*"variable"*"not"*|*"env var"*"missing"*|*"environment variable"*"required"*)
        add_finding "config" "error" "${svc:-unknown}" "$line" "$LINE_NUM"
        ;;
    esac
  done < "$LOG_FILE"
}

# --- Category 9: Dependency issues ---
scan_dependencies() {
  LINE_NUM=0
  while IFS= read -r line; do
    LINE_NUM=$((LINE_NUM + 1))
    svc="$(extract_service "$line")"
    lc_line="$(printf '%s' "$line" | tr '[:upper:]' '[:lower:]')"
    case "$lc_line" in
      *"pip"*"warn"*|*"npm warn"*|*"npm"*"deprecated"*|*"outdated"*"package"*|*"vulnerability"*"found"*)
        add_finding "dependency" "warning" "${svc:-unknown}" "$line" "$LINE_NUM"
        ;;
      *"could not find"*"package"*|*"module not found"*|*"no matching distribution"*|*"package"*"not found"*)
        add_finding "dependency" "error" "${svc:-unknown}" "$line" "$LINE_NUM"
        ;;
    esac
  done < "$LOG_FILE"
}

# Run all scanners
scan_crashes
scan_deprecations
scan_versions
scan_slow_startups
scan_connection_retries
scan_security
scan_memory
scan_config
scan_dependencies

# Output JSON
printf '[%s]\n' "$FINDINGS"

# Summary to stderr
echo "--- Pre-release check summary ---" >&2
echo "Total findings: $FINDING_COUNT (errors: $ERROR_COUNT, warnings: $WARNING_COUNT)" >&2

# Exit code
if [ "$ERROR_COUNT" -gt 0 ]; then
  exit 1
elif [ "$WARNING_COUNT" -gt 0 ]; then
  exit 2
else
  exit 0
fi

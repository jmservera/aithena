#!/usr/bin/env bash
# Validate shared Python-image health checks without starting the full stack.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
  echo "SKIP: docker is not available"
  exit 0
fi

ARTIFACT_DIR="$ROOT/.test-artifacts/compose-health-checks"
SUMMARY_FILE="$ARTIFACT_DIR/summary.txt"
mkdir -p "$ARTIFACT_DIR"

containers=()

cleanup() {
  local status=$?
  if [ "${#containers[@]}" -gt 0 ]; then
    docker rm -f "${containers[@]}" >/dev/null 2>&1 || true
  fi

  if [ "$status" -eq 0 ]; then
    rm -rf "$ARTIFACT_DIR"
  else
    echo "Retained artifacts: $ARTIFACT_DIR"
  fi

  exit "$status"
}
trap cleanup EXIT

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

require_image() {
  local image="$1"
  docker image inspect "$image" >/dev/null 2>&1 ||
    fail "missing image $image; build it first"
}

wait_for_health() {
  local service="$1"
  local container="$2"
  local start_ts="$3"
  local deadline status health_output

  deadline=$((start_ts + 60))

  while :; do
    status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container")"

    case "$status" in
      healthy)
        local elapsed
        elapsed=$(( $(date +%s) - start_ts ))
        printf '%s\t%s\t%ss\n' "$service" "$status" "$elapsed" >> "$SUMMARY_FILE"
        echo "OK: $service became healthy in ${elapsed}s"
        return 0
        ;;
      unhealthy)
        health_output="$(docker inspect --format '{{range .State.Health.Log}}{{println .Output}}{{end}}' "$container")"
        fail "$service became unhealthy: ${health_output:-no health output}"
        ;;
      *)
        if ! docker inspect --format '{{.State.Running}}' "$container" | grep -qx true; then
          docker logs "$container" > "$ARTIFACT_DIR/$service.log" 2>&1 || true
          fail "$service exited before becoming healthy"
        fi
        ;;
    esac

    if [ "$(date +%s)" -ge "$deadline" ]; then
      health_output="$(docker inspect --format '{{range .State.Health.Log}}{{println .Output}}{{end}}' "$container")"
      fail "$service did not become healthy within 60s: ${health_output:-no health output}"
    fi

    sleep 2
  done
}

check_clean_logs() {
  local service="$1"
  local container="$2"
  local log_file="$ARTIFACT_DIR/$service.log"

  docker logs "$container" >"$log_file" 2>&1 || true

  if grep -Eiq 'traceback|exception|critical|error|failed' "$log_file"; then
    fail "$service emitted startup errors; see $log_file"
  fi
}

start_process_service() {
  local service="$1"
  local image="$2"
  local marker="$3"
  local container="healthcheck-${service}-$$"

  docker run -d \
    --name "$container" \
    "$image" \
    python -c 'import time; time.sleep(120)' "$marker" >/dev/null

  containers+=("$container")
  printf '%s\t%s\t%s\n' "$service" "$container" "$(date +%s)"
}

start_http_service() {
  local service="$1"
  local image="$2"
  local container="healthcheck-${service}-$$"

  docker run -d \
    --name "$container" \
    -e HEALTHCHECK_URL=http://localhost:8080/ \
    "$image" \
    python -m http.server 8080 >/dev/null

  containers+=("$container")
  printf '%s\t%s\t%s\n' "$service" "$container" "$(date +%s)"
}

require_image aithena-document-indexer:latest
require_image aithena-document-lister:latest
require_image aithena-solr-search:latest

: > "$SUMMARY_FILE"
echo "service	status	elapsed" >> "$SUMMARY_FILE"

while IFS=$'\t' read -r service container start_ts; do
  wait_for_health "$service" "$container" "$start_ts"
  check_clean_logs "$service" "$container"
done < <(
  start_process_service document-indexer aithena-document-indexer:latest document_indexer
  start_process_service document-lister aithena-document-lister:latest document_lister
  start_http_service solr-search aithena-solr-search:latest
)

echo ""
cat "$SUMMARY_FILE"

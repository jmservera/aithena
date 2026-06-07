#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load .env if it exists
if [[ -f .env ]]; then
  set +a
  source .env
  set -a
fi

VERSION_FILE="$SCRIPT_DIR/VERSION"

if git_tag="$(git describe --tags --exact-match 2>/dev/null)"; then
  VERSION="${git_tag#v}"
elif [[ -f "$VERSION_FILE" ]]; then
  VERSION="$(tr -d '[:space:]' < "$VERSION_FILE")"
else
  VERSION="dev"
fi

if [[ -z "$VERSION" ]]; then
  VERSION="dev"
fi

GIT_COMMIT="$(git rev-parse HEAD 2>/dev/null || printf 'unknown')"
BUILD_DATE="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

export VERSION GIT_COMMIT BUILD_DATE

echo "Building version ${VERSION}"
echo "Git commit: ${GIT_COMMIT}"
echo "Build date: ${BUILD_DATE}"

ARTIFACT_DIR="${BUILDALL_ARTIFACT_DIR:-${SCRIPT_DIR}/.test-artifacts}"
BUILDALL_LOG_TIMESTAMP="${BUILDALL_LOG_TIMESTAMP:-$(date -u +"%Y%m%dT%H%M%SZ")}"
FAILURES=()

safe_log_name() {
  local name="$1"
  printf '%s' "$name" | tr -c '[:alnum:]_.-' '_'
}

record_failure() {
  local label="$1"
  local status="$2"
  local log_file="$3"
  FAILURES+=("${label}|${status}|${log_file}")
}

print_failure_summary() {
  echo ""
  echo "Build failed with ${#FAILURES[@]} failure(s):" >&2
  local failure label status log_file
  for failure in "${FAILURES[@]}"; do
    IFS='|' read -r label status log_file <<< "$failure"
    echo "  - ${label} exited with status ${status}" >&2
    echo "    log: ${log_file}" >&2
  done
}

run_logged() {
  local label="$1"
  local log_slug="$2"
  local workdir="$3"
  shift 3

  mkdir -p "$ARTIFACT_DIR"
  local log_file="${ARTIFACT_DIR}/buildall-$(safe_log_name "$log_slug")-${BUILDALL_LOG_TIMESTAMP}.log"

  echo "Running ${label}"
  echo "  log: ${log_file}"
  if (
    cd "$workdir"
    "$@"
  ) > "$log_file" 2>&1; then
    echo "  ✅ ${label} succeeded"
    return 0
  else
    local status=$?
    echo "  ❌ ${label} failed (exit ${status})"
    record_failure "$label" "$status" "$log_file"
    return 1
  fi
}

discover_python_service_dirs() {
  find src -mindepth 2 -maxdepth 2 -type f -name pyproject.toml -print \
    | while IFS= read -r pyproject_file; do
      service_dir="$(dirname "$pyproject_file")"
      if [[ -f "${service_dir}/Dockerfile" ]]; then
        printf '%s\n' "$service_dir"
      fi
    done \
    | LC_ALL=C sort
}

mapfile -t python_service_dirs < <(discover_python_service_dirs)

for service_dir in "${python_service_dirs[@]}"; do
  if [[ ! -f "${service_dir}/pyproject.toml" ]]; then
    echo "Skipping ${service_dir}: no pyproject.toml"
    continue
  fi

  service_name="$(basename "$service_dir")"
  run_logged "uv sync in ${service_dir}" "$service_name" "${SCRIPT_DIR}/${service_dir}" uv sync || true
done

if [[ ${#FAILURES[@]} -gt 0 ]]; then
  echo "Skipping Docker Compose because service preparation failed." >&2
  print_failure_summary
  exit 1
fi

run_logged "docker compose up --build -d" "compose" "$SCRIPT_DIR" docker compose up --build -d || true

if [[ ${#FAILURES[@]} -gt 0 ]]; then
  print_failure_summary
  exit 1
fi

echo "Build completed successfully."

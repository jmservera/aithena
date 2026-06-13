#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

source "$SCRIPT_DIR/scripts/lib/build-services.sh"

aithena_load_dotenv "$SCRIPT_DIR"
aithena_export_build_metadata "$SCRIPT_DIR"

echo "Building version ${VERSION}"
echo "Git commit: ${GIT_COMMIT}"
echo "Build date: ${BUILD_DATE}"

ARTIFACT_DIR="${BUILDALL_ARTIFACT_DIR:-${SCRIPT_DIR}/.test-artifacts}"
BUILDALL_LOG_TIMESTAMP="${BUILDALL_LOG_TIMESTAMP:-$(date -u +"%Y%m%dT%H%M%SZ")}"
FAILURES=()

mapfile -t python_service_dirs < <(aithena_discover_python_service_dirs "$SCRIPT_DIR")
aithena_prepare_python_services "$SCRIPT_DIR" "$ARTIFACT_DIR" "$BUILDALL_LOG_TIMESTAMP" FAILURES "${python_service_dirs[@]}"

if [[ ${#FAILURES[@]} -gt 0 ]]; then
  echo "Skipping Docker Compose because service preparation failed." >&2
  aithena_print_failure_summary FAILURES
  exit 1
fi

aithena_run_logged "$ARTIFACT_DIR" "$BUILDALL_LOG_TIMESTAMP" FAILURES \
  "docker build aithena:base" "python-base" "$SCRIPT_DIR" \
  docker build -f Dockerfile.base -t aithena:base . || true

if [[ ${#FAILURES[@]} -gt 0 ]]; then
  echo "Skipping Docker Compose because the shared Python base image failed to build." >&2
  aithena_print_failure_summary FAILURES
  exit 1
fi

aithena_run_logged "$ARTIFACT_DIR" "$BUILDALL_LOG_TIMESTAMP" FAILURES \
  "docker compose up --build -d" "compose" "$SCRIPT_DIR" docker compose up --build -d || true

if [[ ${#FAILURES[@]} -gt 0 ]]; then
  aithena_print_failure_summary FAILURES
  exit 1
fi

echo "Build completed successfully."

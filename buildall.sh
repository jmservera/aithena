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

discover_python_service_dirs() {
  find src -mindepth 2 -maxdepth 2 -name pyproject.toml -print \
    | while IFS= read -r pyproject_file; do
      service_dir="$(dirname "$pyproject_file")"
      if [[ -f "${service_dir}/Dockerfile" ]]; then
        printf '%s\n' "$service_dir"
      fi
    done \
    | sort
}

mapfile -t python_service_dirs < <(discover_python_service_dirs)

for service_dir in "${python_service_dirs[@]}"; do
  if [[ ! -f "${service_dir}/pyproject.toml" ]]; then
    echo "Skipping ${service_dir}: no pyproject.toml"
    continue
  fi

  echo "Running uv sync in ${service_dir}"
  (
    cd "${service_dir}"
    uv sync
  )
done

docker compose up --build -d

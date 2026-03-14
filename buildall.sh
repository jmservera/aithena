#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

python_service_dirs=(
  "admin"
  "document-indexer"
  "document-lister"
  "embeddings-server"
  "solr-search"
)

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

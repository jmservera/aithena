#!/usr/bin/env bash
# Validate Compose network exposure and Solr auth wiring.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  echo "SKIP: docker compose is not available"
  exit 0
fi

ARTIFACT_DIR="$ROOT/.test-artifacts/compose-security"
mkdir -p "$ARTIFACT_DIR/e2e-library"

export E2E_LIBRARY_PATH="$ARTIFACT_DIR/e2e-library"
export SOLR_ADMIN_USER="${SOLR_ADMIN_USER:-solr_admin}"
export SOLR_ADMIN_PASS="${SOLR_ADMIN_PASS:-SolrAdmin_test_2026!}"
export SOLR_READONLY_USER="${SOLR_READONLY_USER:-solr_read}"
export SOLR_READONLY_PASS="${SOLR_READONLY_PASS:-SolrRead_test_2026!}"
export RABBITMQ_ADMIN_USER="${RABBITMQ_ADMIN_USER:-admin}"
export RABBITMQ_ADMIN_PASS="${RABBITMQ_ADMIN_PASS:-admin_test_pass}"
export RABBITMQ_LISTER_PASS="${RABBITMQ_LISTER_PASS:-lister_test_pass}"
export RABBITMQ_INDEXER_PASS="${RABBITMQ_INDEXER_PASS:-indexer_test_pass}"
export RABBITMQ_SEARCH_PASS="${RABBITMQ_SEARCH_PASS:-search_test_pass}"
export ADMIN_API_KEY="${ADMIN_API_KEY:-admin-test-key}"
export AUTH_JWT_SECRET="${AUTH_JWT_SECRET:-compose-security-test-secret}"
export AUTH_DB_DIR="${AUTH_DB_DIR:-$ARTIFACT_DIR/auth}"
mkdir -p "$AUTH_DB_DIR"

check_compose() {
  label="$1"
  shift
  docker compose "$@" --profile production config --format json |
    python3 -c '
import json
import sys

label = sys.argv[1]
data = json.load(sys.stdin)
services = data.get("services", {})
failures = []

for service_name in ("zoo1", "zoo2", "zoo3"):
    ports = services.get(service_name, {}).get("ports") or []
    if ports:
        failures.append(f"{label}: {service_name} publishes ports: {ports}")

for service_name in ("solr", "solr2", "solr3", "solr-init"):
    service = services.get(service_name)
    if service is None:
        continue
    if "distributed-only" in (service.get("profiles") or []):
        continue
    env = service.get("environment") or {}
    if isinstance(env, list):
        env_keys = {item.split("=", 1)[0] for item in env}
    else:
        env_keys = set(env)
    for key in ("SOLR_AUTH_USER", "SOLR_AUTH_PASS"):
        if key not in env_keys:
            failures.append(f"{label}: {service_name} missing {key}")

if failures:
    print("\n".join(failures), file=sys.stderr)
    sys.exit(1)

print(f"OK: {label}")
' "$label"
}

check_compose "default CI topology" \
  -f docker-compose.yml \
  -f docker/compose.ci-ports.yml \
  -f docker/compose.e2e.yml

check_compose "single-node CI topology" \
  -f docker-compose.yml \
  -f docker/compose.single-node.yml \
  -f docker/compose.ci-ports.yml \
  -f docker/compose.e2e.yml

check_compose "production topology" \
  -f docker/compose.prod.yml

rm -rf "$ARTIFACT_DIR"

#!/usr/bin/env bash
# Runtime validation for production SolrCloud with Solr 10 Overseer disabled.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  echo "SKIP: docker compose is not available"
  exit 0
fi

COMPOSE_ARGS=()
if [[ -n "${COMPOSE_FILES:-}" ]]; then
  # shellcheck disable=SC2206
  COMPOSE_ARGS=(${COMPOSE_FILES})
else
  COMPOSE_ARGS=(-f docker/compose.prod.yml)
fi

SOLR_URL="${SOLR_URL:-http://solr:8983}"
COLLECTION="${SOLR_OVERSEER_SMOKE_COLLECTION:-overseer_disabled_smoke}"
AUTH=()
if [[ -n "${SOLR_ADMIN_USER:-}" && -n "${SOLR_ADMIN_PASS:-}" ]]; then
  AUTH=(-u "${SOLR_ADMIN_USER}:${SOLR_ADMIN_PASS}")
fi
SOLR2_STOPPED=0

compose() {
  docker compose "${COMPOSE_ARGS[@]}" "$@"
}

solr_curl() {
  compose exec -T solr curl -fsS "${AUTH[@]}" "$@"
}

json_assert() {
  local code="$1"
  shift
  python3 -c "$code" "$@"
}

cleanup_collection() {
  if [[ "$SOLR2_STOPPED" == "1" ]]; then
    compose start solr2 >/dev/null 2>&1 || true
    SOLR2_STOPPED=0
  fi
  solr_curl "${SOLR_URL}/solr/admin/collections?action=DELETE&name=${COLLECTION}&wt=json" >/dev/null 2>&1 || true
}

trap cleanup_collection EXIT

echo "[overseer-validation] Checking Solr 10 Overseer-disabled system property..."
solr_curl "${SOLR_URL}/solr/admin/info/properties?wt=json" | json_assert '
import json
import sys

data = json.load(sys.stdin)
props = data.get("system.properties") or data.get("systemProperties") or {}
value = props.get("solr.cloud.overseer.enabled")
if str(value).lower() != "false":
    raise SystemExit(f"Expected solr.cloud.overseer.enabled=false, got {value!r}")
print("OK: solr.cloud.overseer.enabled=false")
'

echo "[overseer-validation] Checking 3 live Solr nodes..."
solr_curl "${SOLR_URL}/solr/admin/collections?action=CLUSTERSTATUS&liveNodes=true&wt=json" | json_assert '
import json
import sys

data = json.load(sys.stdin)
live_nodes = data.get("cluster", {}).get("live_nodes", [])
if len(live_nodes) != 3:
    raise SystemExit(f"Expected exactly 3 live nodes, got {len(live_nodes)}: {live_nodes}")
print("OK: 3 live nodes")
'

echo "[overseer-validation] Creating and deleting a replicated smoke collection..."
cleanup_collection
solr_curl \
  "${SOLR_URL}/solr/admin/collections?action=CREATE&name=${COLLECTION}&collection.configName=books&numShards=1&replicationFactor=3&maxShardsPerNode=1&waitForFinalState=true&wt=json" \
  >/dev/null
solr_curl "${SOLR_URL}/solr/admin/collections?action=CLUSTERSTATUS&collection=${COLLECTION}&wt=json" | json_assert '
import json
import sys

collection = sys.argv[1]
data = json.load(sys.stdin)
details = data.get("cluster", {}).get("collections", {}).get(collection)
if not details:
    raise SystemExit(f"Missing collection status for {collection}")
replicas = [
    replica
    for shard in details.get("shards", {}).values()
    for replica in shard.get("replicas", {}).values()
]
active = [replica for replica in replicas if replica.get("state") == "active"]
if len(active) != 3:
    raise SystemExit(f"Expected 3 active replicas, got {len(active)} of {len(replicas)}")
print("OK: replicated collection create succeeded")
' "$COLLECTION"

if [[ "${RUN_FAILOVER:-0}" == "1" ]]; then
  echo "[overseer-validation] Exercising single-node Solr failover (solr2 stop/start)..."
  compose stop solr2 >/dev/null
  SOLR2_STOPPED=1
  saw_two_live_nodes=0
  for _ in {1..60}; do
    if solr_curl "${SOLR_URL}/solr/admin/collections?action=CLUSTERSTATUS&liveNodes=true&wt=json" |
      json_assert '
import json
import sys

data = json.load(sys.stdin)
if len(data.get("cluster", {}).get("live_nodes", [])) < 2:
    raise SystemExit(1)
' >/dev/null 2>&1
    then
      saw_two_live_nodes=1
      break
    fi
    sleep 2
  done
  if [[ "$saw_two_live_nodes" != "1" ]]; then
    raise_message="Timed out waiting for at least 2 live Solr nodes after stopping solr2"
    echo "ERROR: $raise_message" >&2
    exit 1
  fi
  solr_curl "${SOLR_URL}/solr/admin/collections?action=CLUSTERSTATUS&collection=${COLLECTION}&wt=json" | json_assert '
import json
import sys

collection = sys.argv[1]
data = json.load(sys.stdin)
details = data.get("cluster", {}).get("collections", {}).get(collection, {})
shards = details.get("shards", {})
if not shards:
    raise SystemExit(f"Missing shards for {collection}")
for shard_name, shard in shards.items():
    replicas = shard.get("replicas", {}).values()
    if not any(replica.get("state") == "active" and replica.get("leader") == "true" for replica in replicas):
        raise SystemExit(f"Shard {shard_name} has no active leader during solr2 outage")
print("OK: collection retained an active leader with solr2 stopped")
' "$COLLECTION"
  compose start solr2 >/dev/null
  SOLR2_STOPPED=0
  saw_three_live_nodes=0
  for _ in {1..60}; do
    if solr_curl "${SOLR_URL}/solr/admin/collections?action=CLUSTERSTATUS&liveNodes=true&wt=json" |
      json_assert '
import json
import sys

data = json.load(sys.stdin)
if len(data.get("cluster", {}).get("live_nodes", [])) != 3:
    raise SystemExit(1)
' >/dev/null 2>&1
    then
      saw_three_live_nodes=1
      break
    fi
    sleep 2
  done
  if [[ "$saw_three_live_nodes" != "1" ]]; then
    echo "ERROR: Timed out waiting for solr2 to return to the 3-node cluster" >&2
    exit 1
  fi
  echo "OK: solr2 returned to the 3-node cluster"
else
  echo "SKIP: set RUN_FAILOVER=1 to stop/start solr2 and validate single-node failover"
fi

cleanup_collection
trap - EXIT
echo "[overseer-validation] Complete"

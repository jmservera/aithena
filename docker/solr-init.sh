#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# solr-init.sh — Bootstrap Solr security, configsets, and collections
#
# Shared by the full 3-node cluster (docker-compose.yml) and the single-node
# dev/CI overlay (docker/compose.single-node.yml).  All behaviour differences
# are driven by environment variables so there is only one copy of the logic.
#
# Required env vars:
#   ZK_HOST                 ZooKeeper connection string (e.g. zoo1:2181)
#   SOLR_URL                Solr base URL (e.g. http://solr:8983)
#   SOLR_ADMIN_USER         Admin username for BasicAuth bootstrap
#   SOLR_ADMIN_PASS         Admin password
#   SOLR_AUTH_USER           User for collection admin ops (usually = admin)
#   SOLR_AUTH_PASS           Password for collection admin ops
#   SOLR_READONLY_USER      Read-only user to create
#   SOLR_READONLY_PASS      Read-only password
#   SOLR_NUM_SHARDS         Number of shards (default: 1)
#   SOLR_REPLICATION_FACTOR Replication factor (default: 1)
#   SOLR_EXPECTED_NODES     Minimum live nodes before proceeding (default: 1)
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail

: "${ZK_HOST:?ZK_HOST is required}"
: "${SOLR_URL:?SOLR_URL is required}"
: "${SOLR_ADMIN_USER:?SOLR_ADMIN_USER is required}"
: "${SOLR_ADMIN_PASS:?SOLR_ADMIN_PASS is required}"
: "${SOLR_AUTH_USER:?SOLR_AUTH_USER is required}"
: "${SOLR_AUTH_PASS:?SOLR_AUTH_PASS is required}"
: "${SOLR_READONLY_USER:?SOLR_READONLY_USER is required}"
: "${SOLR_READONLY_PASS:?SOLR_READONLY_PASS is required}"

NUM_SHARDS="${SOLR_NUM_SHARDS:-1}"
REPLICATION_FACTOR="${SOLR_REPLICATION_FACTOR:-1}"
EXPECTED_NODES="${SOLR_EXPECTED_NODES:-1}"

# ── Wait for Solr to be reachable (with or without auth) ─────────────────────
echo "Waiting for Solr at ${SOLR_URL}..."
until curl -fsS -u "${SOLR_ADMIN_USER}:${SOLR_ADMIN_PASS}" \
        "${SOLR_URL}/solr/admin/info/system" >/dev/null 2>&1 \
   || curl -fsS "${SOLR_URL}/solr/admin/info/system" >/dev/null 2>&1; do
  sleep 2
done
echo "Solr is reachable."

# ── Wait for expected number of live nodes ────────────────────────────────────
echo "Waiting for ${EXPECTED_NODES} live Solr node(s)..."
until [ "$(curl -fsS -u "${SOLR_ADMIN_USER}:${SOLR_ADMIN_PASS}" \
        "${SOLR_URL}/solr/admin/collections?action=CLUSTERSTATUS&wt=json" 2>/dev/null \
        | grep -o '"[^"]*:8983_solr"' | sort -u | wc -l | tr -d '[:space:]')" -ge "${EXPECTED_NODES}" ] 2>/dev/null \
   || [ "$(curl -fsS \
        "${SOLR_URL}/solr/admin/collections?action=CLUSTERSTATUS&wt=json" 2>/dev/null \
        | grep -o '"[^"]*:8983_solr"' | sort -u | wc -l | tr -d '[:space:]')" -ge "${EXPECTED_NODES}" ] 2>/dev/null; do
  sleep 2
done
echo "Cluster has ${EXPECTED_NODES}+ live node(s)."

# ── Security: Bootstrap BasicAuth + RBAC ──────────────────────────────────────
# Solr 9.7 BasicAuthPlugin requires >=1 user with hashed password
# at load time, so we use "solr auth enable" which handles hashing.
AUTH_RESP=$(curl -sS "${SOLR_URL}/solr/admin/authentication" 2>/dev/null || true)
if echo "${AUTH_RESP}" | grep -qi 'No authentication'; then
  echo "Bootstrapping Solr security..."
  # Seed an empty security.json so "solr auth enable" can update it
  echo '{}' > /opt/solr/empty-security.json
  solr zk cp file:/opt/solr/empty-security.json zk:/security.json -z "${ZK_HOST}"
  sleep 2

  # Create admin user with hashed password (also creates default RBAC rules)
  solr auth enable --type basicAuth \
    -u "${SOLR_ADMIN_USER}:${SOLR_ADMIN_PASS}" \
    --block-unknown false \
    --solr-include-file /dev/null \
    -z "${ZK_HOST}"

  echo "Waiting for Solr to load security config..."
  sleep 5

  # NOTE: solr auth enable (Solr 9.7) already assigns the admin user
  # all built-in roles: ["superadmin", "admin", "search", "index"].
  # Do NOT overwrite with set-user-role — that strips superadmin/search.

  # Add readonly user
  echo "Adding readonly user..."
  curl -fsS -u "${SOLR_ADMIN_USER}:${SOLR_ADMIN_PASS}" \
    "${SOLR_URL}/solr/admin/authentication" \
    -H 'Content-Type: application/json' \
    -d '{"set-user": {"'"${SOLR_READONLY_USER}"'": "'"${SOLR_READONLY_PASS}"'"}}'

  # Assign search role (Solr 9.7 built-in role for read + collection-admin-read)
  curl -fsS -u "${SOLR_ADMIN_USER}:${SOLR_ADMIN_PASS}" \
    "${SOLR_URL}/solr/admin/authorization" \
    -H 'Content-Type: application/json' \
    -d '{"set-user-role": {"'"${SOLR_READONLY_USER}"'": ["search"]}}'

  echo "Security bootstrap complete."
else
  echo "Security already configured, skipping bootstrap."
fi

# ── Validate SOLR_NUM_SHARDS and SOLR_REPLICATION_FACTOR ──────────────────────
if ! echo "${NUM_SHARDS}" | grep -qE '^[1-9][0-9]*$'; then
  echo "ERROR: Invalid SOLR_NUM_SHARDS: '${NUM_SHARDS}'. Expected a positive integer." >&2
  exit 1
fi

if ! echo "${REPLICATION_FACTOR}" | grep -qE '^[1-9][0-9]*$'; then
  echo "ERROR: Invalid SOLR_REPLICATION_FACTOR: '${REPLICATION_FACTOR}'. Expected a positive integer." >&2
  exit 1
fi

if [ "${REPLICATION_FACTOR}" -gt "${EXPECTED_NODES}" ]; then
  echo "WARNING: SOLR_REPLICATION_FACTOR=${REPLICATION_FACTOR} exceeds available nodes (${EXPECTED_NODES}). Forcing replicationFactor=${EXPECTED_NODES}." >&2
  REPLICATION_FACTOR="${EXPECTED_NODES}"
fi

# ── books collection (multilingual-e5-base, 768D) ────────────────────────────
if ! solr zk ls /configs -z "${ZK_HOST}" | grep -qx 'books'; then
  solr zk upconfig -z "${ZK_HOST}" -n books -d /configsets/books
fi

if ! curl -fsS -u "${SOLR_AUTH_USER}:${SOLR_AUTH_PASS}" \
      "${SOLR_URL}/solr/admin/collections?action=LIST&wt=json" | grep -q '"books"'; then
  curl -fsS -u "${SOLR_AUTH_USER}:${SOLR_AUTH_PASS}" \
    "${SOLR_URL}/solr/admin/collections?action=CREATE&name=books&collection.configName=books&numShards=${NUM_SHARDS}&replicationFactor=${REPLICATION_FACTOR}&waitForFinalState=true&wt=json"
fi

SOLR_BASE_URL="${SOLR_URL}" SOLR_COLLECTION="books" \
  SOLR_AUTH_USER="${SOLR_AUTH_USER}" SOLR_AUTH_PASS="${SOLR_AUTH_PASS}" \
  sh /scripts/add-conf-overlay.sh

echo "Solr init complete (${EXPECTED_NODES}-node mode)"

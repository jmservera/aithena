#!/usr/bin/env bash
# Create all required Docker volume directories for Aithena.
#
# Usage:
#   ./scripts/init-volumes.sh              # Uses default /source/volumes
#   VOLUMES_ROOT=/mnt/d/aithena ./scripts/init-volumes.sh  # Custom root
#
# The script is idempotent — safe to run repeatedly.

set -euo pipefail

VOLUMES_ROOT="${VOLUMES_ROOT:-/source/volumes}"

echo "Creating Aithena volume directories under ${VOLUMES_ROOT} ..."

# Service data directories
dirs=(
    "${VOLUMES_ROOT}/collections-db"
    "${VOLUMES_ROOT}/rabbitmq-data"
    "${VOLUMES_ROOT}/redis"
    "${VOLUMES_ROOT}/solr-data"
    "${VOLUMES_ROOT}/solr-data2"
    "${VOLUMES_ROOT}/solr-data3"
    "${VOLUMES_ROOT}/zoo-backup"
    "${VOLUMES_ROOT}/zoo-data1/data"
    "${VOLUMES_ROOT}/zoo-data1/datalog"
    "${VOLUMES_ROOT}/zoo-data1/logs"
    "${VOLUMES_ROOT}/zoo-data2/data"
    "${VOLUMES_ROOT}/zoo-data2/datalog"
    "${VOLUMES_ROOT}/zoo-data2/logs"
    "${VOLUMES_ROOT}/zoo-data3/data"
    "${VOLUMES_ROOT}/zoo-data3/datalog"
    "${VOLUMES_ROOT}/zoo-data3/logs"
)

for d in "${dirs[@]}"; do
    mkdir -p "$d"
done

# Solr runs as UID 8983 inside the container.
# Use -R only on the top-level directory; ignore errors on files already
# owned by the target UID (common on re-runs).
for d in "${VOLUMES_ROOT}/solr-data" "${VOLUMES_ROOT}/solr-data2" "${VOLUMES_ROOT}/solr-data3"; do
    chown -R 8983:8983 "$d" 2>/dev/null || chown 8983:8983 "$d" 2>/dev/null || true
done

# ZooKeeper runs as UID 1000 inside the container.
for d in "${VOLUMES_ROOT}/zoo-data1" "${VOLUMES_ROOT}/zoo-data2" "${VOLUMES_ROOT}/zoo-data3" "${VOLUMES_ROOT}/zoo-backup"; do
    chown -R 1000:1000 "$d" 2>/dev/null || chown 1000:1000 "$d" 2>/dev/null || true
done

echo "Done. All volume directories created under ${VOLUMES_ROOT}."
echo ""
echo "If using a custom path, export VOLUMES_ROOT before running docker compose:"
echo "  export VOLUMES_ROOT=${VOLUMES_ROOT}"

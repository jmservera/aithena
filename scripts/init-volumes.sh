#!/usr/bin/env bash
# Create required Docker volume directories for Aithena.
# Covers docker-compose.yml and docker-compose.prod.yml.
# For SSL (docker-compose.ssl.yml), also create certbot dirs manually.
#
# Usage:
#   sudo ./scripts/init-volumes.sh              # Uses default /source/volumes
#   sudo VOLUMES_ROOT=/mnt/data/volumes ./scripts/init-volumes.sh  # Custom root
#
# When using a custom VOLUMES_ROOT, you must symlink it so Docker Compose
# can find the volumes at the expected path:
#   ln -s /mnt/data/volumes /source/volumes
#
# The script is idempotent — safe to run repeatedly.

set -euo pipefail

VOLUMES_ROOT="${VOLUMES_ROOT:-/source/volumes}"
WARN=0

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
for d in "${VOLUMES_ROOT}/solr-data" "${VOLUMES_ROOT}/solr-data2" "${VOLUMES_ROOT}/solr-data3"; do
    if ! chown -R 8983:8983 "$d" 2>/dev/null; then
        echo "⚠  Could not chown $d to 8983:8983 — run with sudo" >&2
        WARN=1
    fi
done

# ZooKeeper runs as UID 1000 inside the container.
for d in "${VOLUMES_ROOT}/zoo-data1" "${VOLUMES_ROOT}/zoo-data2" "${VOLUMES_ROOT}/zoo-data3" "${VOLUMES_ROOT}/zoo-backup"; do
    if ! chown -R 1000:1000 "$d" 2>/dev/null; then
        echo "⚠  Could not chown $d to 1000:1000 — run with sudo" >&2
        WARN=1
    fi
done

echo ""
if [ "$WARN" -eq 1 ]; then
    echo "Done with warnings. Some directories may have incorrect ownership."
    echo "Re-run with sudo to fix: sudo $0"
else
    echo "Done. All volume directories created under ${VOLUMES_ROOT}."
fi

if [ "${VOLUMES_ROOT}" != "/source/volumes" ]; then
    echo ""
    echo "Docker Compose expects volumes at /source/volumes."
    echo "Create a symlink so Compose can find them:"
    echo "  sudo ln -s ${VOLUMES_ROOT} /source/volumes"
fi

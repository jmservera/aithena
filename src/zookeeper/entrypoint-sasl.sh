#!/bin/bash
set -euo pipefail

# ──────────────────────────────────────────────────────────────────────────────
# ZooKeeper SASL entrypoint wrapper
#
# Generates the JAAS configuration file from the template by substituting
# environment variables, then exec's the official ZooKeeper Docker entrypoint.
#
# Required env vars:
#   ZK_SASL_USER  — SASL username (e.g. "solr")
#   ZK_SASL_PASS  — SASL password
# ──────────────────────────────────────────────────────────────────────────────

: "${ZK_SASL_USER:?ZK_SASL_USER is required}"
: "${ZK_SASL_PASS:?ZK_SASL_PASS is required}"

JAAS_TEMPLATE="/conf/jaas-template.conf"
JAAS_OUTPUT="/conf/jaas.conf"

sed \
  -e "s|\${ZK_SASL_USER}|${ZK_SASL_USER}|g" \
  -e "s|\${ZK_SASL_PASS}|${ZK_SASL_PASS}|g" \
  "$JAAS_TEMPLATE" > "$JAAS_OUTPUT"

echo "ZooKeeper SASL JAAS config generated at ${JAAS_OUTPUT}"

exec /docker-entrypoint.sh "$@"

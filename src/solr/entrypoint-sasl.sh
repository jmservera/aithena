#!/bin/bash
set -euo pipefail

# ──────────────────────────────────────────────────────────────────────────────
# Solr SASL entrypoint wrapper
#
# Generates the JAAS configuration file from the template by substituting
# environment variables, then exec's the official Solr Docker entrypoint.
#
# Required env vars:
#   ZK_SASL_USER  — SASL username (must match ZooKeeper's Server section)
#   ZK_SASL_PASS  — SASL password
# ──────────────────────────────────────────────────────────────────────────────

: "${ZK_SASL_USER:?ZK_SASL_USER is required}"
: "${ZK_SASL_PASS:?ZK_SASL_PASS is required}"

JAAS_TEMPLATE="/opt/solr/server/etc/solr-jaas-template.conf"
JAAS_OUTPUT="/opt/solr/server/etc/solr-jaas.conf"

sed \
  -e "s|\${ZK_SASL_USER}|${ZK_SASL_USER}|g" \
  -e "s|\${ZK_SASL_PASS}|${ZK_SASL_PASS}|g" \
  "$JAAS_TEMPLATE" > "$JAAS_OUTPUT"

echo "Solr SASL JAAS config generated at ${JAAS_OUTPUT}"

exec docker-entrypoint.sh "$@"

#!/bin/bash
set -euo pipefail

# ZooKeeper SASL entrypoint wrapper
# Generates JAAS config from template, then exec's the ZK entrypoint.

: "${ZK_SASL_USER:?ZK_SASL_USER is required}"
: "${ZK_SASL_PASS:?ZK_SASL_PASS is required}"

JAAS_TEMPLATE="/conf/jaas-template.conf"
JAAS_OUTPUT="/conf/jaas.conf"

sed \
  -e "s|\${ZK_SASL_USER}|${ZK_SASL_USER}|g" \
  -e "s|\${ZK_SASL_PASS}|${ZK_SASL_PASS}|g" \
  "$JAAS_TEMPLATE" > "$JAAS_OUTPUT"

exec /docker-entrypoint.sh "$@"

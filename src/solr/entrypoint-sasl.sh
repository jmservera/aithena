#!/bin/bash
set -euo pipefail

# Solr SASL entrypoint wrapper
# Generates JAAS config at runtime using printf (no template file needed).

: "${ZK_SASL_USER:?ZK_SASL_USER is required}"
: "${ZK_SASL_PASS:?ZK_SASL_PASS is required}"

printf 'Client {\n    org.apache.zookeeper.server.auth.DigestLoginModule required\n    username="%s"\n    password="%s";\n};\n' \
  "$ZK_SASL_USER" "$ZK_SASL_PASS" \
  > /opt/solr/server/etc/solr-jaas.conf
chmod 600 /opt/solr/server/etc/solr-jaas.conf

exec docker-entrypoint.sh "$@"

#!/bin/bash
set -euo pipefail

# Solr SASL entrypoint wrapper
# Generates JAAS config at runtime using printf (no template file needed).
# When running as root, fixes bind-mount ownership then drops to solr (8983).

: "${ZK_SASL_USER:?ZK_SASL_USER is required}"
: "${ZK_SASL_PASS:?ZK_SASL_PASS is required}"

# Fix bind-mount ownership when running as root, then drop privileges
if [ "$(id -u)" = "0" ]; then
  chown -R 8983:8983 /var/solr
  printf 'Client {\n    org.apache.zookeeper.server.auth.DigestLoginModule required\n    username="%s"\n    password="%s";\n};\n' \
    "$ZK_SASL_USER" "$ZK_SASL_PASS" \
    > /var/solr/solr-jaas.conf
  chown 8983:8983 /var/solr/solr-jaas.conf
  chmod 600 /var/solr/solr-jaas.conf
  exec gosu solr docker-entrypoint.sh "$@"
else
  printf 'Client {\n    org.apache.zookeeper.server.auth.DigestLoginModule required\n    username="%s"\n    password="%s";\n};\n' \
    "$ZK_SASL_USER" "$ZK_SASL_PASS" \
    > /var/solr/solr-jaas.conf
  chmod 600 /var/solr/solr-jaas.conf
  exec docker-entrypoint.sh "$@"
fi

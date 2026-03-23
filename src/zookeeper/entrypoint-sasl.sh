#!/bin/bash
set -euo pipefail

# ZooKeeper SASL entrypoint wrapper
# Generates JAAS config at runtime using printf (no template file needed).

: "${ZK_SASL_USER:?ZK_SASL_USER is required}"
: "${ZK_SASL_PASS:?ZK_SASL_PASS is required}"

printf 'QuorumServer {\n    org.apache.zookeeper.server.auth.DigestLoginModule required\n    user_%s="%s";\n};\nQuorumLearner {\n    org.apache.zookeeper.server.auth.DigestLoginModule required\n    username="%s"\n    password="%s";\n};\nServer {\n    org.apache.zookeeper.server.auth.DigestLoginModule required\n    user_%s="%s";\n};\n' \
  "$ZK_SASL_USER" "$ZK_SASL_PASS" \
  "$ZK_SASL_USER" "$ZK_SASL_PASS" \
  "$ZK_SASL_USER" "$ZK_SASL_PASS" \
  > /conf/jaas.conf
chown zookeeper:zookeeper /conf/jaas.conf
chmod 600 /conf/jaas.conf

exec /docker-entrypoint.sh "$@"

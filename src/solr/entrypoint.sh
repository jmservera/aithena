#!/bin/bash
set -euo pipefail

# Solr entrypoint wrapper
# Fixes bind-mount ownership when running as root, then drops to solr (8983).

if [ "$(id -u)" = "0" ]; then
  if [ -d /var/solr/data ]; then
    find -P /var/solr/data -user root -exec chown 8983:8983 {} +
  fi
  exec gosu solr docker-entrypoint.sh "$@"
else
  exec docker-entrypoint.sh "$@"
fi

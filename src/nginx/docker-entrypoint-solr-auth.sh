#!/bin/sh
# docker-entrypoint-solr-auth.sh — pre-compute Solr Basic Auth credentials.
#
# Runs before the standard nginx entrypoint so that ${SOLR_BASIC_AUTH} is
# available as an environment variable when the nginx image's built-in
# envsubst template processing step substitutes it into the config.
#
# Required env vars (set in docker-compose):
#   SOLR_ADMIN_USER  — Solr admin username
#   SOLR_ADMIN_PASS  — Solr admin password
#
# Produces:
#   SOLR_BASIC_AUTH  — base64(user:pass), ready for an HTTP Basic Auth header

set -eu

if [ -n "${SOLR_ADMIN_USER:-}" ] && [ -n "${SOLR_ADMIN_PASS:-}" ]; then
    SOLR_BASIC_AUTH=$(printf '%s:%s' "$SOLR_ADMIN_USER" "$SOLR_ADMIN_PASS" | base64 | tr -d '\n')
    export SOLR_BASIC_AUTH
else
    echo "WARNING: SOLR_ADMIN_USER or SOLR_ADMIN_PASS not set; Solr proxy will not inject Basic Auth" >&2
fi

# Delegate to the standard nginx Docker entrypoint (handles envsubst, etc.)
exec /docker-entrypoint.sh "$@"

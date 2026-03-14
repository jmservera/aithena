#!/bin/sh
set -eu

SOLR_BASE_URL="${SOLR_BASE_URL:-http://localhost:8983}"
SOLR_COLLECTION="${SOLR_COLLECTION:-books}"

collection_endpoint="${SOLR_BASE_URL%/}/api/collections/${SOLR_COLLECTION}/config"
backup_endpoint="${SOLR_BASE_URL%/}/api/cluster/backup-repositories"

retry_curl() {
  output=""
  until output="$(curl -fsS "$@" 2>/dev/null)"; do
    sleep 2
  done
  printf '%s' "$output"
}

post_json() {
  endpoint="$1"
  payload="$2"
  retry_curl -X POST -H 'Content-type:application/json' -d "$payload" "$endpoint" >/dev/null
}

optional_post_json() {
  endpoint="$1"
  payload="$2"
  if ! curl -fsS -X POST -H 'Content-type:application/json' -d "$payload" "$endpoint"; then
    echo "Warning: optional Solr config request failed for $endpoint; continuing" >&2
  fi
}

collection_config="$(retry_curl "$collection_endpoint")"

if ! printf '%s' "$collection_config" | grep -q '"/update/extract"'; then
  post_json "$collection_endpoint" '{
    "add-requesthandler": {
      "/update/extract": {
        "name": "/update/extract",
        "class": "solr.extraction.ExtractingRequestHandler",
        "defaults": {
          "lowernames": "true",
          "fmap.content": "_text_",
          "captureAttr": "true",
          "update.chain": "langid"
        }
      }
    }
  }'
fi

collection_config="$(retry_curl "$collection_endpoint")"

if ! printf '%s' "$collection_config" | grep -q '"my-init"'; then
  post_json "$collection_endpoint" '{
    "add-initparams": {
      "my-init": {
        "path": "/select,/browse",
        "defaults": {
          "df": "content"
        }
      }
    }
  }'
fi

backup_config="$(curl -fsS "$backup_endpoint" 2>/dev/null || true)"

if [ -n "$backup_config" ] && ! printf '%s' "$backup_config" | grep -q '"local_repo"'; then
  optional_post_json "$backup_endpoint" '{
    "create-repository": {
      "name": "local_repo",
      "type": "local",
      "settings": {
        "location": "/backup"
      }
    }
  }'
fi
#!/usr/bin/env bash
set -euo pipefail

# Full failover coverage expects docker-compose.yml only. The e2e override disables
# nginx and certbot, so keep COMPOSE_FILES at its default unless you intentionally
# want a reduced-scope drill.

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

read -r -a COMPOSE_FILES <<<"${COMPOSE_FILES:-docker-compose.yml}"
COMPOSE_ARGS=()
for compose_file in "${COMPOSE_FILES[@]}"; do
  COMPOSE_ARGS+=( -f "$compose_file" )
done

compose() {
  docker compose "${COMPOSE_ARGS[@]}" "$@"
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

log() {
  printf '\n[%s] %s\n' "$(date -u +%H:%M:%S)" "$*"
}

json_matches() {
  local payload="$1"
  local expr="$2"
  JSON_PAYLOAD="$payload" JSON_EXPR="$expr" python3 - <<'PY'
import json
import os
import sys

data = json.loads(os.environ["JSON_PAYLOAD"])
expr = os.environ["JSON_EXPR"]
if not eval(expr, {"__builtins__": {}}, {"data": data}):
    sys.exit(1)
PY
}

assert_json() {
  local payload="$1"
  local expr="$2"
  local message="$3"
  if ! json_matches "$payload" "$expr"; then
    echo "Assertion failed: $message" >&2
    printf '%s\n' "$payload" >&2
    exit 1
  fi
}

container_id() {
  compose ps -q "$1"
}

container_state() {
  local cid
  cid="$(container_id "$1")"
  [[ -n "$cid" ]] || return 1
  docker inspect -f '{{.State.Status}}' "$cid"
}

container_exit_code() {
  local cid
  cid="$(container_id "$1")"
  [[ -n "$cid" ]] || return 1
  docker inspect -f '{{.State.ExitCode}}' "$cid"
}

container_health() {
  local cid
  cid="$(container_id "$1")"
  [[ -n "$cid" ]] || return 1
  docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$cid"
}

wait_for_state() {
  local service="$1"
  local target="$2"
  local timeout="${3:-300}"
  local started_at=$SECONDS

  while (( SECONDS - started_at < timeout )); do
    local state=""
    case "$target" in
      healthy)
        state="$(container_health "$service" 2>/dev/null || true)"
        [[ "$state" == "healthy" ]] && return 0
        ;;
      running)
        state="$(container_state "$service" 2>/dev/null || true)"
        [[ "$state" == "running" ]] && return 0
        ;;
      exited)
        state="$(container_state "$service" 2>/dev/null || true)"
        [[ "$state" == "exited" ]] && return 0
        ;;
      exited0)
        state="$(container_state "$service" 2>/dev/null || true)"
        if [[ "$state" == "exited" ]] && [[ "$(container_exit_code "$service" 2>/dev/null || true)" == "0" ]]; then
          return 0
        fi
        ;;
      *)
        echo "Unsupported wait target: $target" >&2
        exit 1
        ;;
    esac
    sleep 2
  done

  compose ps >&2 || true
  echo "Timed out waiting for $service to reach state '$target'" >&2
  return 1
}

status_json() {
  compose exec -T solr-search wget -qO- http://localhost:8080/v1/status/
}

wait_for_status() {
  local expr="$1"
  local timeout="${2:-180}"
  local started_at=$SECONDS
  local payload=""

  while (( SECONDS - started_at < timeout )); do
    if payload="$(status_json 2>/dev/null)" && json_matches "$payload" "$expr"; then
      printf '%s\n' "$payload"
      return 0
    fi
    sleep 2
  done

  [[ -n "$payload" ]] && printf '%s\n' "$payload" >&2
  echo "Timed out waiting for status condition: $expr" >&2
  return 1
}

api_login() {
  [[ -n "${DRILL_USERNAME:-}" ]] || {
    echo "Set DRILL_USERNAME to run authenticated search probes." >&2
    exit 1
  }
  [[ -n "${DRILL_PASSWORD:-}" ]] || {
    echo "Set DRILL_PASSWORD to run authenticated search probes." >&2
    exit 1
  }

  local login_body response
  login_body="$(python3 -c 'import json, os; print(json.dumps({"username": os.environ["DRILL_USERNAME"], "password": os.environ["DRILL_PASSWORD"]}))')"
  response="$(curl -fsS \
    -H 'Content-Type: application/json' \
    -d "$login_body" \
    http://localhost/v1/auth/login)"

  TOKEN="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])' <<<"$response")"
  export TOKEN
}

api_get_json() {
  local url="$1"
  curl -fsS -H "Authorization: Bearer ${TOKEN}" "$url"
}

api_get_status() {
  local url="$1"
  local body_file="$TMP_DIR/response-body.json"
  HTTP_STATUS="$(curl -sS -o "$body_file" -w '%{http_code}' -H "Authorization: Bearer ${TOKEN}" "$url")"
  HTTP_BODY="$(cat "$body_file")"
  export HTTP_STATUS HTTP_BODY
}

assert_keyword_search_ok() {
  local payload
  payload="$(api_get_json 'http://localhost/v1/search?q=history&mode=keyword&page_size=1')"
  assert_json "$payload" "data['mode'] == 'keyword' and data['degraded'] is False" "keyword search should succeed"
}

assert_semantic_degraded() {
  local payload
  payload="$(api_get_json 'http://localhost/v1/search?q=history&mode=semantic&page_size=1')"
  assert_json "$payload" "data['mode'] == 'keyword'" "semantic fallback should return keyword mode"
  assert_json "$payload" "data['degraded'] is True" "semantic fallback should mark degraded=true"
  assert_json "$payload" "data['requested_mode'] == 'semantic'" "semantic fallback should preserve requested_mode"
}

assert_semantic_recovered() {
  local payload
  payload="$(api_get_json 'http://localhost/v1/search?q=history&mode=semantic&page_size=1')"
  assert_json "$payload" "data['mode'] == 'semantic' and data['degraded'] is False" "semantic search should recover after embeddings restart"
}

assert_search_fails() {
  api_get_status 'http://localhost/v1/search?q=history&mode=keyword&page_size=1'
  if [[ "$HTTP_STATUS" == "200" ]]; then
    echo "Expected search failure, but got HTTP 200" >&2
    printf '%s\n' "$HTTP_BODY" >&2
    exit 1
  fi
}

check_nginx_health() {
  curl -fsS http://localhost/health >/dev/null
}

require_cmd docker
require_cmd python3
require_cmd curl

TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

log "Validating Docker Compose configuration"
compose config >/dev/null

log "Starting the full stack"
compose up -d --build

for service in redis rabbitmq zoo1 zoo2 zoo3 solr solr2 solr3 embeddings-server document-lister document-indexer solr-search streamlit-admin redis-commander aithena-ui nginx; do
  wait_for_state "$service" healthy 360
done
wait_for_state solr-init exited0 180

log "Checking healthy baseline via /v1/status/"
BASELINE_STATUS="$(wait_for_status "data['services']['solr'] == 'up' and data['services']['redis'] == 'up' and data['services']['rabbitmq'] == 'up' and data['services']['embeddings'] == 'up' and data['embeddings_available'] is True and data['solr']['status'] == 'ok' and data['solr']['nodes'] >= 3" 180)"
assert_json "$BASELINE_STATUS" "data['indexing']['total_discovered'] >= 0" "status endpoint should expose indexing counts"
check_nginx_health
api_login
assert_keyword_search_ok
assert_semantic_recovered

log "Scenario: primary solr service down"
compose stop solr
wait_for_status "data['services']['solr'] == 'down' and data['solr']['status'] == 'error'" 120 >/dev/null
assert_search_fails
compose start solr
wait_for_state solr healthy 240
compose restart solr-search nginx document-indexer
wait_for_state solr-search healthy 180
wait_for_state nginx healthy 180
wait_for_state document-indexer healthy 180
wait_for_status "data['services']['solr'] == 'up' and data['solr']['status'] == 'ok' and data['solr']['nodes'] >= 3" 240 >/dev/null
assert_keyword_search_ok

log "Scenario: redis down"
compose stop redis
REDIS_DOWN_STATUS="$(wait_for_status "data['services']['redis'] == 'down'" 90)"
assert_json "$REDIS_DOWN_STATUS" "data['indexing'] == {'total_discovered': 0, 'indexed': 0, 'failed': 0, 'pending': 0}" "Redis outage should zero indexing counters"
assert_keyword_search_ok
compose start redis
wait_for_state redis healthy 120
compose restart document-lister document-indexer streamlit-admin redis-commander
wait_for_state document-lister healthy 180
wait_for_state document-indexer healthy 180
wait_for_state streamlit-admin healthy 180
wait_for_state redis-commander healthy 180
wait_for_status "data['services']['redis'] == 'up'" 120 >/dev/null
assert_keyword_search_ok

log "Scenario: rabbitmq down"
compose stop rabbitmq
wait_for_status "data['services']['rabbitmq'] == 'down'" 120 >/dev/null
assert_keyword_search_ok
compose start rabbitmq
wait_for_state rabbitmq healthy 180
compose restart document-lister document-indexer streamlit-admin
wait_for_state document-lister healthy 180
wait_for_state document-indexer healthy 180
wait_for_state streamlit-admin healthy 180
wait_for_status "data['services']['rabbitmq'] == 'up'" 120 >/dev/null
assert_keyword_search_ok

log "Scenario: embeddings-server down"
compose stop embeddings-server
EMBEDDINGS_DOWN_STATUS="$(wait_for_status "data['services']['embeddings'] == 'down' and data['embeddings_available'] is False" 120)"
assert_json "$EMBEDDINGS_DOWN_STATUS" "data['services']['solr'] == 'up'" "Embeddings outage should not take Solr down"
assert_keyword_search_ok
assert_semantic_degraded
compose start embeddings-server
wait_for_state embeddings-server healthy 240
compose restart document-indexer
wait_for_state document-indexer healthy 180
wait_for_status "data['services']['embeddings'] == 'up' and data['embeddings_available'] is True" 180 >/dev/null
assert_semantic_recovered

log "Scenario: nginx down"
compose stop nginx
wait_for_state nginx exited 60
if curl -fsS http://localhost/health >/dev/null 2>&1; then
  echo "Expected nginx health check to fail while nginx is stopped" >&2
  exit 1
fi
NGINX_INTERNAL_STATUS="$(status_json)"
assert_json "$NGINX_INTERNAL_STATUS" "data['services']['solr'] == 'up' and data['services']['redis'] == 'up' and data['services']['rabbitmq'] == 'up' and data['services']['embeddings'] == 'up'" "Core services should stay available internally when nginx is stopped"
compose start nginx
wait_for_state nginx healthy 180
check_nginx_health
assert_keyword_search_ok

log "Final recovery validation"
FINAL_STATUS="$(wait_for_status "data['services']['solr'] == 'up' and data['services']['redis'] == 'up' and data['services']['rabbitmq'] == 'up' and data['services']['embeddings'] == 'up' and data['embeddings_available'] is True and data['solr']['status'] == 'ok' and data['solr']['nodes'] >= 3" 240)"
assert_json "$FINAL_STATUS" "data['solr']['docs_indexed'] >= 0" "Solr status should include an indexed document count after recovery"
check_nginx_health
assert_keyword_search_ok
assert_semantic_recovered

log "Failover drill completed successfully"
compose ps

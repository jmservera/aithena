#!/usr/bin/env bash
# smoke-openvino-permissions.sh — OpenVINO embeddings container smoke test
#
# Validates that the OpenVINO embeddings-server container:
#   1. Has correct model directory permissions (readable by app user)
#   2. Has OPENVINO_CACHE_DIR set and writable (regression from rc.3→rc.23)
#   3. Loads the embedding model with BACKEND=openvino successfully
#   4. Produces embeddings via the /v1/embeddings/ endpoint
#
# Usage:
#   ./e2e/smoke-openvino-permissions.sh <image-ref>
#   ./e2e/smoke-openvino-permissions.sh ghcr.io/jmservera/aithena-embeddings-server:1.19.0-rc.1-openvino
#
# Exit codes:
#   0 = all checks passed
#   1 = one or more checks failed
#
# Environment variables:
#   SMOKE_PORT           — host port to bind (default: 18080)
#   SMOKE_TIMEOUT        — seconds to wait for model loading (default: 180)
#   SMOKE_REPORT_FILE    — write machine-readable results here (optional)

set -euo pipefail

IMAGE="${1:?Usage: $0 <image-ref>}"
CONTAINER_NAME="smoke-openvino-$$"
PORT="${SMOKE_PORT:-18080}"
STARTUP_TIMEOUT="${SMOKE_TIMEOUT:-180}"
REPORT_FILE="${SMOKE_REPORT_FILE:-}"

MODEL_DIR="/models/sentence_transformers/intfloat_multilingual-e5-base"
OV_SUBDIR="$MODEL_DIR/openvino"

# ── Helpers ──────────────────────────────────────────────────────────────

cleanup() {
  docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
}
trap cleanup EXIT

FAILED=0
RESULTS=""

pass() {
  echo "  ✅ $1"
  RESULTS="${RESULTS}PASS: $1\n"
}

fail() {
  echo "  ❌ $1"
  RESULTS="${RESULTS}FAIL: $1\n"
  FAILED=1
}

section() {
  echo ""
  echo "--- $1 ---"
}

# ── Banner ───────────────────────────────────────────────────────────────

echo "============================================="
echo " OpenVINO Permissions Smoke Test"
echo "============================================="
echo "Image:   $IMAGE"
echo "Port:    $PORT"
echo "Timeout: ${STARTUP_TIMEOUT}s"
echo ""

# ── Test 1: Model directory exists and is readable ───────────────────────

section "Test 1: Model directory structure"

if docker run --rm --entrypoint "" "$IMAGE" \
    sh -c "test -d '${MODEL_DIR}'" 2>/dev/null; then
  pass "Model directory exists: $MODEL_DIR"
else
  fail "Model directory missing: $MODEL_DIR"
fi

# ── Test 2: OpenVINO cache writability (the actual regression test) ──────

section "Test 2: OPENVINO_CACHE_DIR writability (permission check)"

# The fix for the rc.3→rc.23 regression redirects OpenVINO's compiled-model
# cache from /models/.../model_cache (read-only) to a writable directory via
# the OPENVINO_CACHE_DIR env var. Verify this is set and writable.
WRITE_OUTPUT=$(docker run --rm --entrypoint "" "$IMAGE" \
  sh -c '
    echo "OV_CACHE_DIR=${OPENVINO_CACHE_DIR:-unset}"
    if [ -z "${OPENVINO_CACHE_DIR:-}" ]; then
      echo "ENV_MISSING"
    elif [ -d "$OPENVINO_CACHE_DIR" ]; then
      echo "DIR_EXISTS"
      touch "$OPENVINO_CACHE_DIR/test_write" 2>&1 && echo "WRITE_OK" || echo "WRITE_FAIL"
    else
      mkdir -p "$OPENVINO_CACHE_DIR" 2>&1 && echo "DIR_CREATED" || echo "DIR_FAIL"
      touch "$OPENVINO_CACHE_DIR/test_write" 2>&1 && echo "WRITE_OK" || echo "WRITE_FAIL"
    fi
  ' 2>&1) || true

if echo "$WRITE_OUTPUT" | grep -q "ENV_MISSING"; then
  fail "OPENVINO_CACHE_DIR env var is not set"
  echo "    OpenVINO will try to write inside /models/ (read-only) and fail"
elif echo "$WRITE_OUTPUT" | grep -qE "DIR_EXISTS|DIR_CREATED"; then
  pass "OPENVINO_CACHE_DIR is set and directory exists"
else
  fail "OPENVINO_CACHE_DIR directory cannot be created"
  echo "    Output: $WRITE_OUTPUT"
fi

if echo "$WRITE_OUTPUT" | grep -q "WRITE_OK"; then
  pass "Can write files inside OPENVINO_CACHE_DIR"
else
  fail "Cannot write files inside OPENVINO_CACHE_DIR"
fi

# ── Test 3: Ownership and UID audit ──────────────────────────────────────

section "Test 3: Container user and permissions audit"

AUDIT_OUTPUT=$(docker run --rm --entrypoint "" "$IMAGE" \
  sh -c "
    echo 'USER:'; id
    echo 'MODEL_DIR:'; ls -ld '${MODEL_DIR}' 2>&1
    echo 'OV_DIR:'; ls -ld '${OV_SUBDIR}' 2>&1 || echo '(not present)'
    echo 'PARENT_PERMS:'; stat -c '%a %U:%G' '${MODEL_DIR}' 2>&1 || true
  " 2>&1) || true

echo "$AUDIT_OUTPUT"

if echo "$AUDIT_OUTPUT" | grep -qE "uid=(999|1000)"; then
  pass "Container runs as non-root user"
else
  fail "Container does not run as expected non-root user"
fi

# ── Test 4: Full model load via health endpoint ──────────────────────────

section "Test 4: OpenVINO model loading (BACKEND=openvino DEVICE=cpu)"

docker run -d --name "$CONTAINER_NAME" \
  -p "${PORT}:8080" \
  -e BACKEND=openvino \
  -e DEVICE=cpu \
  "$IMAGE"

elapsed=0
healthy=false
while [ "$elapsed" -lt "$STARTUP_TIMEOUT" ]; do
  if curl -sf "http://localhost:${PORT}/health" >/dev/null 2>&1; then
    healthy=true
    break
  fi
  # Fail fast if the container exited
  if ! docker inspect --format='{{.State.Running}}' "$CONTAINER_NAME" 2>/dev/null | grep -q true; then
    echo "  ⚠️  Container exited before becoming healthy"
    break
  fi
  sleep 3
  elapsed=$((elapsed + 3))
done

if $healthy; then
  pass "Health endpoint responded after ${elapsed}s"

  HEALTH_BODY=$(curl -sf "http://localhost:${PORT}/health" || true)
  if echo "$HEALTH_BODY" | grep -q '"backend".*"openvino"'; then
    pass "Health response confirms backend=openvino"
  else
    fail "Health response missing backend=openvino: $HEALTH_BODY"
  fi
else
  fail "Model failed to load within ${STARTUP_TIMEOUT}s"
  echo ""
  echo "  === Container logs (last 80 lines) ==="
  docker logs "$CONTAINER_NAME" 2>&1 | tail -80 || true
  echo "  === End logs ==="
fi

# ── Test 5: Embedding inference end-to-end ───────────────────────────────

section "Test 5: Embedding inference"

if $healthy; then
  EMBED_RESPONSE=$(curl -sf -X POST "http://localhost:${PORT}/v1/embeddings/" \
    -H "Content-Type: application/json" \
    -d '{"input": "smoke test for openvino permissions"}' 2>&1) || true

  if echo "$EMBED_RESPONSE" | grep -q '"embedding"'; then
    pass "Embedding inference succeeded (got embedding vector)"

    # Validate embedding dimension (e5-base = 768)
    DIM=$(echo "$EMBED_RESPONSE" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(len(data['data'][0]['embedding']))
" 2>/dev/null) || true
    if [ "$DIM" = "768" ]; then
      pass "Embedding dimension is 768 (correct for e5-base)"
    else
      fail "Unexpected embedding dimension: ${DIM:-parse-error} (expected 768)"
    fi
  else
    fail "Embedding inference failed: ${EMBED_RESPONSE:-no response}"
  fi
else
  fail "Skipped embedding inference (model not loaded)"
fi

# ── Summary ──────────────────────────────────────────────────────────────

echo ""
echo "============================================="
echo " Results"
echo "============================================="
printf "%b" "$RESULTS"
echo ""

# Write machine-readable report if requested
if [ -n "$REPORT_FILE" ]; then
  printf "%b" "$RESULTS" > "$REPORT_FILE"
  echo "Report written to: $REPORT_FILE"
fi

if [ "$FAILED" -ne 0 ]; then
  echo "❌ SMOKE TEST FAILED — one or more checks did not pass"
  exit 1
else
  echo "✅ ALL CHECKS PASSED"
  exit 0
fi

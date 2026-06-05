#!/usr/bin/env bash
# Verifies OpenVINO smoke diagnostics do not mask failures when piped through tee.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ARTIFACT_DIR="$ROOT/.test-artifacts/openvino-pipefail"
mkdir -p "$ARTIFACT_DIR"
trap 'rm -rf "$ARTIFACT_DIR"' EXIT

PASS=0
FAIL=0

assert_pipefail_in_block() {
  local file="$1"
  local label="$2"
  if python3 - "$ROOT/$file" <<'PY'
from pathlib import Path
import sys

text = Path(sys.argv[1]).read_text()
needle = "OpenVINO"
if needle not in text:
    raise SystemExit(1)

lines = text.splitlines()
for index, line in enumerate(lines):
    if "2>&1 | tee openvino-smoke-output.txt" not in line:
        continue
    start = max(0, index - 8)
    block = "\n".join(lines[start:index])
    if "set -o pipefail" in block or "set -euo pipefail" in block or "bash -o pipefail" in block:
        raise SystemExit(0)
raise SystemExit(1)
PY
  then
    PASS=$((PASS + 1))
    echo "  ✅ $label"
  else
    FAIL=$((FAIL + 1))
    echo "  ❌ $label"
  fi
}

assert_pipeline_fails() {
  local output="$ARTIFACT_DIR/pipeline-output.txt"
  if bash -c 'set -o pipefail; false 2>&1 | tee "$1"' bash "$output"; then
    FAIL=$((FAIL + 1))
    echo "  ❌ pipefail propagates smoke command failure"
  else
    PASS=$((PASS + 1))
    echo "  ✅ pipefail propagates smoke command failure"
  fi
}

echo "Checking OpenVINO smoke tee pipelines"
assert_pipefail_in_block ".github/workflows/openvino-release-gate.yml" "release gate has pipefail before tee"
assert_pipefail_in_block ".github/workflows/pre-release.yml" "pre-release job has pipefail before tee"
assert_pipefail_in_block "e2e/smoke-openvino-permissions.ci.yml" "CI job snippet has pipefail before tee"
assert_pipeline_fails

echo ""
echo "Passed: $PASS"
echo "Failed: $FAIL"

if [ "$FAIL" -ne 0 ]; then
  exit 1
fi

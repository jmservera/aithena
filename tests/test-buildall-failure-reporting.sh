#!/usr/bin/env bash
# Verifies buildall.sh reports the failing service and retains per-step logs.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SANDBOX="$ROOT/.test-artifacts/buildall-failure-test.$$"

cleanup() {
  local status=$?
  if [ "$status" -eq 0 ]; then
    rm -rf "$SANDBOX"
  else
    echo "Retained artifacts: $SANDBOX"
  fi
  exit "$status"
}
trap cleanup EXIT

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

mkdir -p "$SANDBOX/repo/src/service-a" "$SANDBOX/repo/src/service-b" "$SANDBOX/bin"
cp "$ROOT/buildall.sh" "$SANDBOX/repo/buildall.sh"
mkdir -p "$SANDBOX/repo/scripts/lib"
cp "$ROOT/scripts/lib/build-services.sh" "$SANDBOX/repo/scripts/lib/build-services.sh"
printf 'test-version\n' > "$SANDBOX/repo/VERSION"
touch "$SANDBOX/repo/Dockerfile.base"

for service in service-a service-b; do
  touch "$SANDBOX/repo/src/$service/pyproject.toml"
  touch "$SANDBOX/repo/src/$service/Dockerfile"
done

cat > "$SANDBOX/bin/uv" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
case "$PWD" in
  */service-b)
    echo "simulated uv failure for service-b" >&2
    exit 42
    ;;
  *)
    echo "simulated uv success for ${PWD##*/}"
    ;;
esac
SH
chmod +x "$SANDBOX/bin/uv"

cat > "$SANDBOX/bin/docker" <<'SH'
#!/usr/bin/env bash
if [ "$1" = "build" ]; then
  echo "simulated base image build success"
  exit 0
fi
echo "docker should not run after a service preparation failure" >&2
exit 99
SH
chmod +x "$SANDBOX/bin/docker"

OUTPUT="$SANDBOX/output.txt"
if PATH="$SANDBOX/bin:$PATH" BUILDALL_LOG_TIMESTAMP="20260102T030405Z" \
  bash "$SANDBOX/repo/buildall.sh" > "$OUTPUT" 2>&1; then
  fail "buildall.sh should fail when an individual service sync fails"
fi

grep -Fq "uv sync in src/service-b failed (exit 42)" "$OUTPUT" ||
  fail "output should name the failing service and exit status"

grep -Fq "Skipping Docker Compose because service preparation failed." "$OUTPUT" ||
  fail "output should explain Docker Compose was skipped"

LOG="$SANDBOX/repo/.test-artifacts/buildall-service-b-20260102T030405Z.log"
[ -f "$LOG" ] || fail "expected service-b log at $LOG"

grep -Fq "simulated uv failure for service-b" "$LOG" ||
  fail "service log should contain the command failure output"

if grep -Fq "docker should not run" "$OUTPUT"; then
  fail "docker compose should not run after a service preparation failure"
fi

cat > "$SANDBOX/bin/uv" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
echo "simulated uv success for ${PWD##*/}"
SH
chmod +x "$SANDBOX/bin/uv"

cat > "$SANDBOX/bin/docker" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
if [ "$1" = "build" ]; then
  echo "simulated base image build success"
  exit 0
fi
if [ "$1 $2 $3 $4" != "compose up --build -d" ]; then
  echo "unexpected docker arguments: $*" >&2
  exit 2
fi
echo "simulated compose failure" >&2
exit 77
SH
chmod +x "$SANDBOX/bin/docker"

COMPOSE_OUTPUT="$SANDBOX/compose-output.txt"
if PATH="$SANDBOX/bin:$PATH" BUILDALL_LOG_TIMESTAMP="20260102T030406Z" \
  bash "$SANDBOX/repo/buildall.sh" > "$COMPOSE_OUTPUT" 2>&1; then
  fail "buildall.sh should fail when Docker Compose fails"
fi

grep -Fq "docker compose up --build -d failed (exit 77)" "$COMPOSE_OUTPUT" ||
  fail "output should report Docker Compose failure and exit status"

COMPOSE_LOG="$SANDBOX/repo/.test-artifacts/buildall-compose-20260102T030406Z.log"
[ -f "$COMPOSE_LOG" ] || fail "expected Compose log at $COMPOSE_LOG"

grep -Fq "simulated compose failure" "$COMPOSE_LOG" ||
  fail "Compose log should contain command failure output"

echo "OK: buildall.sh reports failed steps and saves per-step logs"

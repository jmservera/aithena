#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# This smoke test is intended to run from `make test`; until #1747 merges, invoke it directly.
FIXTURE_DIR="$ROOT/tests/fixtures/manage-cli"
ARTIFACT_DIR="$ROOT/.test-artifacts/manage-cli"
PROJECT_NAME="manage-cli-$RANDOM-$$"

mkdir -p "$ARTIFACT_DIR"

cleanup() {
  local status=$?
  NO_COLOR=1 \
    AITHENA_COMPOSE_FILES="$FIXTURE_DIR/docker-compose.yml" \
    COMPOSE_PROJECT_NAME="$PROJECT_NAME" \
    "$ROOT/manage.sh" down >/dev/null 2>&1 || true

  if [[ "$status" -eq 0 ]]; then
    rm -rf "$ARTIFACT_DIR"
  else
    echo "Retained artifacts: $ARTIFACT_DIR"
  fi

  exit "$status"
}
trap cleanup EXIT

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  echo "SKIP: docker compose is not available"
  exit 0
fi

run_manage() {
  NO_COLOR=1 \
    AITHENA_COMPOSE_FILES="$FIXTURE_DIR/docker-compose.yml" \
    COMPOSE_PROJECT_NAME="$PROJECT_NAME" \
    "$ROOT/manage.sh" "$@"
}

bash -n "$ROOT/manage.sh"
[[ -x "$ROOT/manage.sh" ]] || fail "manage.sh should be executable"

run_manage --help >"$ARTIFACT_DIR/help.txt"
grep -Fq "Core commands:" "$ARTIFACT_DIR/help.txt" || fail "main help should list commands"

for command in up down build logs health test status shell reset; do
  run_manage "$command" --help >"$ARTIFACT_DIR/help-$command.txt"
done

if run_manage shell >"$ARTIFACT_DIR/shell-missing.txt" 2>&1; then
  fail "shell without a service should fail"
fi
grep -Fq "A service name is required" "$ARTIFACT_DIR/shell-missing.txt" ||
  fail "shell without service should explain the error"

if run_manage not-a-command >"$ARTIFACT_DIR/bad-command.txt" 2>&1; then
  fail "unknown commands should fail"
fi
grep -Fq "Unknown command" "$ARTIFACT_DIR/bad-command.txt" ||
  fail "unknown command output should explain the failure"

run_manage build app >"$ARTIFACT_DIR/build.txt"
run_manage up >"$ARTIFACT_DIR/up.txt"

healthy=0
for _ in {1..15}; do
  if run_manage health >"$ARTIFACT_DIR/health.txt" 2>&1; then
    healthy=1
    break
  fi
  sleep 2
done
[[ "$healthy" -eq 1 ]] || fail "health never reported success"

grep -Fq "app: healthy" "$ARTIFACT_DIR/health.txt" ||
  fail "health output should report the fixture service as healthy"

run_manage status >"$ARTIFACT_DIR/status.txt"
grep -Fq "app" "$ARTIFACT_DIR/status.txt" || fail "status should include the fixture service"

run_manage logs --no-follow app >"$ARTIFACT_DIR/logs.txt"
grep -Fq "fixture app started" "$ARTIFACT_DIR/logs.txt" ||
  fail "logs should include the fixture service output"

run_manage shell app sh -lc 'printf "shell-ok\n"' >"$ARTIFACT_DIR/shell.txt"
grep -Fq "shell-ok" "$ARTIFACT_DIR/shell.txt" ||
  fail "shell command should execute inside the fixture container"

AITHENA_TEST_COMMAND='printf "test-ok\n"' run_manage test >"$ARTIFACT_DIR/test.txt"
grep -Fq "test-ok" "$ARTIFACT_DIR/test.txt" ||
  fail "test command should execute the override"

run_manage reset >"$ARTIFACT_DIR/reset.txt"
if docker compose -f "$FIXTURE_DIR/docker-compose.yml" -p "$PROJECT_NAME" ps --services --status running | grep -q .; then
  fail "reset should leave the fixture stack stopped"
fi

run_manage up >"$ARTIFACT_DIR/up-after-reset.txt"
run_manage down >"$ARTIFACT_DIR/down.txt"

if docker compose -f "$FIXTURE_DIR/docker-compose.yml" -p "$PROJECT_NAME" ps --services --status running | grep -q .; then
  fail "down should stop all running services"
fi

echo "OK: manage.sh subcommands work against the fixture compose stack"

#!/usr/bin/env bash
# Verifies buildall.sh and manage.sh share dynamic Dockerfile discovery.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SANDBOX="$ROOT/.test-artifacts/build-service-discovery.$$"

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

mkdir -p \
  "$SANDBOX/repo/src/service-a" \
  "$SANDBOX/repo/src/newservice" \
  "$SANDBOX/repo/src/aithena-ui" \
  "$SANDBOX/repo/src/solr" \
  "$SANDBOX/repo/scripts/lib" \
  "$SANDBOX/bin" \
  "$SANDBOX/logs"

cp "$ROOT/buildall.sh" "$SANDBOX/repo/buildall.sh"
cp "$ROOT/manage.sh" "$SANDBOX/repo/manage.sh"
cp "$ROOT/scripts/lib/build-services.sh" "$SANDBOX/repo/scripts/lib/build-services.sh"
chmod +x "$SANDBOX/repo/buildall.sh" "$SANDBOX/repo/manage.sh"
printf 'test-version\n' > "$SANDBOX/repo/VERSION"

for service in service-a newservice; do
  touch "$SANDBOX/repo/src/$service/pyproject.toml"
  touch "$SANDBOX/repo/src/$service/Dockerfile"
done
touch "$SANDBOX/repo/src/aithena-ui/Dockerfile"
touch "$SANDBOX/repo/src/solr/Dockerfile"

cat > "$SANDBOX/bin/uv" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
printf 'uv:%s\n' "${PWD##*/}"
SH
chmod +x "$SANDBOX/bin/uv"

cat > "$SANDBOX/bin/docker" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
printf 'docker:%s\n' "$*" >> "${DOCKER_LOG:?}"
if [[ "$1" == "compose" && "$2" == "version" ]]; then
  printf 'Docker Compose version v2.0.0\n'
  exit 0
fi
if [[ "$1" == "compose" && "$2" == "up" && "$3" == "--build" && "$4" == "-d" ]]; then
  printf 'compose-up-ok\n'
  exit 0
fi
if [[ "$1" == "compose" && "$2" == "-f" && "$4" == "build" ]]; then
  printf 'compose-build-ok\n'
  exit 0
fi
if [[ "$1" == "compose" && "$2" == "build" ]]; then
  printf 'compose-build-ok\n'
  exit 0
fi
echo "unexpected docker arguments: $*" >&2
exit 2
SH
chmod +x "$SANDBOX/bin/docker"

BUILDALL_OUTPUT="$SANDBOX/buildall-output.txt"
BUILDALL_LOG_DIR="$SANDBOX/custom-artifacts"
DOCKER_LOG="$SANDBOX/logs/buildall-docker.log" PATH="$SANDBOX/bin:$PATH" \
  BUILDALL_ARTIFACT_DIR="$BUILDALL_LOG_DIR" BUILDALL_LOG_TIMESTAMP="20260102T030407Z" \
  bash "$SANDBOX/repo/buildall.sh" > "$BUILDALL_OUTPUT" 2>&1 || fail "buildall.sh should succeed"

grep -Fq "uv sync in src/service-a" "$BUILDALL_OUTPUT" ||
  fail "buildall should prepare service-a discovered from Dockerfile"
grep -Fq "uv sync in src/newservice" "$BUILDALL_OUTPUT" ||
  fail "buildall should prepare newservice discovered from Dockerfile"
if grep -Fq "uv sync in src/aithena-ui" "$BUILDALL_OUTPUT"; then
  fail "buildall should not run uv sync for Dockerfile-only services without pyproject.toml"
fi
if grep -Fq "uv sync in src/solr" "$BUILDALL_OUTPUT"; then
  fail "buildall should not run uv sync for infra images without pyproject.toml"
fi

grep -Fq "docker:compose up --build -d" "$SANDBOX/logs/buildall-docker.log" ||
  fail "buildall should still run docker compose up --build -d"
[ -f "$BUILDALL_LOG_DIR/buildall-service-a-20260102T030407Z.log" ] ||
  fail "BUILDALL_ARTIFACT_DIR should control log output path"
[ -f "$BUILDALL_LOG_DIR/buildall-newservice-20260102T030407Z.log" ] ||
  fail "newservice log should use BUILDALL_LOG_TIMESTAMP"

MANAGE_OUTPUT="$SANDBOX/manage-output.txt"
DOCKER_LOG="$SANDBOX/logs/manage-docker.log" PATH="$SANDBOX/bin:$PATH" NO_COLOR=1 \
  BUILDALL_LOG_TIMESTAMP="20260102T030408Z" \
  bash "$SANDBOX/repo/manage.sh" build newservice aithena-ui solr > "$MANAGE_OUTPUT" 2>&1 ||
  fail "manage.sh build should succeed"

grep -Fq "uv sync in src/newservice" "$MANAGE_OUTPUT" ||
  fail "manage build should prepare requested Python services discovered from Dockerfiles"
if grep -Fq "uv sync in src/aithena-ui" "$MANAGE_OUTPUT"; then
  fail "manage build should skip non-Python Dockerfile services"
fi
if grep -Fq "uv sync in src/solr" "$MANAGE_OUTPUT"; then
  fail "manage build should skip infra-only Dockerfile services"
fi
grep -Fq "docker:compose -f docker-compose.yml build newservice aithena-ui solr" "$SANDBOX/logs/manage-docker.log" ||
  fail "manage build should pass the requested services to docker compose build"

echo "OK: buildall.sh and manage.sh share dynamic Dockerfile discovery"

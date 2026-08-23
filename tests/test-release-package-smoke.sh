#!/usr/bin/env bash
# tests/test-release-package-smoke.sh — end-to-end smoke test for the packaged
# production release.
#
# Usage:
#   tests/test-release-package-smoke.sh [--archive PATH]
#
#   --archive PATH   Validate this already-built archive instead of building
#                     a fresh one. Used by .github/workflows/release.yml to
#                     smoke-test the EXACT archive it just built, before
#                     upload. Without --archive (e.g. plain CI runs), the
#                     test builds its own throwaway archive via
#                     scripts/build-release-package.sh.
#
# This test:
#   1. Stages/builds the actual release archive via
#      scripts/build-release-package.sh (the same script CI/release.yml
#      uses), or validates a caller-supplied archive built by that script.
#   2. Extracts it into a clean, script-owned temporary directory.
#   3. Runs the documented entry point (installer/run.sh) non-interactively,
#      from both the extracted package and the source checkout.
#   4. Validates the artifacts the installer generates (.env, start.sh, auth DB).
#   5. Validates every Compose file combination the installer's generated
#      start.sh can produce (prod environment — the only one shipped in the
#      release package) via `docker compose config`, WITHOUT starting any
#      services. Falls back to a YAML-syntax check when Docker is unavailable.
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
ARTIFACT_DIR="$ROOT/.test-artifacts/release-package-smoke"

PREBUILT_ARCHIVE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --archive)
      PREBUILT_ARCHIVE="${2:?--archive requires a value}"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

# All extraction/build work happens in a script-owned mktemp directory — never
# a caller-controlled path — so unconditional cleanup here is always safe.
WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/aithena-release-smoke.XXXXXX")"

cleanup() {
  local status=$?
  rm -rf -- "$WORK_DIR"
  if [[ "$status" -eq 0 ]]; then
    rm -rf -- "$ARTIFACT_DIR"
  else
    echo "Retained diagnostics: $ARTIFACT_DIR" >&2
  fi
  exit "$status"
}
trap cleanup EXIT

mkdir -p "$ARTIFACT_DIR"

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0

pass() {
  PASS_COUNT=$((PASS_COUNT + 1))
  echo "PASS: $*"
}

fail() {
  FAIL_COUNT=$((FAIL_COUNT + 1))
  echo "FAIL: $*" >&2
}

skip() {
  SKIP_COUNT=$((SKIP_COUNT + 1))
  echo "SKIP: $*"
}

EXTRACT_DIR="$WORK_DIR/extracted"

if [[ -n "$PREBUILT_ARCHIVE" ]]; then
  echo "== Using pre-built release archive =="
  [[ -f "$PREBUILT_ARCHIVE" ]] || { fail "--archive path does not exist: $PREBUILT_ARCHIVE"; exit 1; }
  ARCHIVE_PATH="$PREBUILT_ARCHIVE"
  pass "using caller-supplied archive: $ARCHIVE_PATH"
  VERSION="$(tar -xzO -f "$ARCHIVE_PATH" aithena-release/VERSION 2>/dev/null || true)"
else
  VERSION="0.0.0-smoketest"
  ARCHIVE_PATH="$WORK_DIR/build/aithena-v${VERSION}-release.tar.gz"

  # ── 1. Build the actual release archive ───────────────────────────────────
  echo "== Building release archive =="
  bash "$ROOT/scripts/build-release-package.sh" \
    --version "$VERSION" \
    --archive "$ARCHIVE_PATH" \
    --checksum \
    >"$ARTIFACT_DIR/build.log" 2>&1 || {
      cat "$ARTIFACT_DIR/build.log" >&2
      fail "scripts/build-release-package.sh exited non-zero"
      exit 1
    }
  if [[ -f "$ARCHIVE_PATH" ]]; then
    pass "release archive was built"
  else
    fail "release archive missing after build"
  fi
fi

if [[ -f "$ARCHIVE_PATH.sha256" ]]; then
  pass "checksum file was written"
else
  fail "checksum file missing after build"
fi

if [[ -f "$ARCHIVE_PATH.sha256" ]]; then
  if (cd "$(dirname -- "$ARCHIVE_PATH")" && sha256sum -c "$(basename -- "$ARCHIVE_PATH").sha256" >/dev/null 2>&1); then
    pass "checksum verifies against the built archive"
  else
    fail "checksum does not verify against the built archive"
  fi
fi

# ── 2. Extract into a clean directory ────────────────────────────────────────
echo "== Extracting archive =="
mkdir -p "$EXTRACT_DIR"
tar -xzf "$ARCHIVE_PATH" -C "$EXTRACT_DIR"
PACKAGE_ROOT="$EXTRACT_DIR/aithena-release"
[[ -d "$PACKAGE_ROOT" ]] || { fail "extracted archive did not produce aithena-release/"; exit 1; }

# ── 3. Required paths ────────────────────────────────────────────────────────
echo "== Verifying required paths =="
REQUIRED_PATHS=(
  "docker-compose.yml"
  "docker/compose.prod.yml"
  "docker/compose.dev-ports.yml"
  "docker/compose.gpu-nvidia.yml"
  "docker/compose.gpu-intel.yml"
  "docker/compose.ssl.yml"
  "docker/compose.single-node.yml"
  "installer/run.sh"
  "installer/setup.py"
  "installer/__main__.py"
  "installer/pyproject.toml"
  "installer/uv.lock"
  "src/aithena-common/pyproject.toml"
  "src/aithena-common/aithena_common/__init__.py"
  "src/aithena-common/aithena_common/auth_db.py"
  "src/aithena-common/aithena_common/passwords.py"
  "src/nginx/default.conf.template"
  "src/nginx/ssl.conf.template"
  "src/nginx/docker-entrypoint-solr-auth.sh"
  "src/nginx/html"
  "src/solr/books"
  "src/solr/add-conf-overlay.sh"
  "src/solr/entrypoint.sh"
  "src/solr/log4j2.xml"
  "src/redis/redis.conf"
  "src/rabbitmq/rabbitmq.conf"
  "src/rabbitmq/init-definitions.sh"
  ".env.example"
  "README.md"
  "LICENSE"
  "VERSION"
  "docs/quickstart.md"
  "docs/admin-manual.md"
)
for path in "${REQUIRED_PATHS[@]}"; do
  if [[ -e "$PACKAGE_ROOT/$path" ]]; then
    pass "required path present: $path"
  else
    fail "required path MISSING from release archive: $path"
  fi
done

if [[ "$(cat "$PACKAGE_ROOT/VERSION")" == "$VERSION" ]]; then
  pass "packaged VERSION matches the requested --version ($VERSION)"
else
  fail "packaged VERSION does not match the requested --version"
fi

# ── 3b. Every ./src/... bind-mount source referenced by any shipped compose
# file must actually exist in the package. This is derived directly from the
# compose files themselves (not a hand-maintained list) so a newly added bind
# mount that isn't packaged fails loudly instead of only failing at
# `docker compose up` time on an end user's machine.
echo "== Verifying every compose bind-mount source is packaged =="
missing_bind_mounts=0
while IFS= read -r bind_source; do
  [[ -n "$bind_source" ]] || continue
  if [[ -e "$PACKAGE_ROOT/$bind_source" ]]; then
    pass "compose bind-mount source present: $bind_source"
  else
    fail "compose bind-mount source MISSING from release archive: $bind_source"
    missing_bind_mounts=$((missing_bind_mounts + 1))
  fi
done < <(grep -hoE '^\s*-\s*\./src/[A-Za-z0-9._/-]+' "$PACKAGE_ROOT"/docker-compose.yml "$PACKAGE_ROOT"/docker/compose.*.yml \
  | sed -E 's#^\s*-\s*\./##' | sort -u)
if [[ "$missing_bind_mounts" -eq 0 ]]; then
  pass "all compose bind-mount sources referenced by shipped compose files are packaged"
fi

# ── 4. Documented compose commands must list docker-compose.yml first ──────
# Compose resolves relative bind-mount paths (./src/...) against the directory
# of the FIRST -f file. Any documented command that starts with an overlay
# (docker/compose.*.yml) instead of the root docker-compose.yml breaks in the
# extracted package because ./src/... would be looked up under docker/src/...
echo "== Checking documented compose command ordering =="
check_doc_compose_ordering() {
  local doc="$1"
  [[ -f "$PACKAGE_ROOT/$doc" ]] || return 0
  local bad
  bad="$(grep -nE 'docker compose( -f [^ ]+)*( up| pull| ps| logs| exec| stop| start| down| config)' "$PACKAGE_ROOT/$doc" \
    | grep -E ' -f docker/compose\.' \
    | grep -vE ' -f docker-compose\.yml .*-f docker/compose\.' \
    || true)"
  if [[ -n "$bad" ]]; then
    fail "$doc documents a compose overlay command without docker-compose.yml first:"$'\n'"$bad"
  else
    pass "$doc compose commands consistently list docker-compose.yml before overlays"
  fi

  # The prod-mode overlays (gpu-*, ssl, single-node) only make sense combined
  # with docker/compose.prod.yml (they're additive to the prod branch of
  # installer/setup.py's generate_start_script()). A documented command that
  # jumps straight from docker-compose.yml to a gpu/ssl/single-node overlay
  # without docker/compose.prod.yml in between would fail against that
  # overlay's stricter required env vars (e.g. SOLR_ADMIN_USER).
  local bad_prod
  bad_prod="$(grep -nE 'docker compose( -f [^ ]+)*( up| pull| ps| logs| exec| stop| start| down| config)' "$PACKAGE_ROOT/$doc" \
    | grep -E ' -f docker/compose\.(gpu-nvidia|gpu-intel|ssl|single-node)\.yml' \
    | grep -vE ' -f docker/compose\.prod\.yml ' \
    || true)"
  if [[ -n "$bad_prod" ]]; then
    fail "$doc documents a GPU/SSL/single-node overlay command without docker/compose.prod.yml:"$'\n'"$bad_prod"
  else
    pass "$doc GPU/SSL/single-node overlay commands consistently include docker/compose.prod.yml"
  fi
}
check_doc_compose_ordering "docs/quickstart.md"
check_doc_compose_ordering "docs/admin-manual.md"
check_doc_compose_ordering "README.md"

# ── 4b. No packaged doc should tell users to run the broken `python3 -m
# installer` module invocation (regression guard for requirement 5's
# entry-point consistency: the one documented command is ./installer/run.sh).
echo "== Checking packaged docs for stale installer invocations =="
stale_invocations=0
for doc in docs/quickstart.md docs/admin-manual.md docs/user-manual.md docs/config/README.md README.md .env.example; do
  [[ -f "$PACKAGE_ROOT/$doc" ]] || continue
  if grep -qE 'python3? +-m +installer\b' "$PACKAGE_ROOT/$doc"; then
    fail "$doc still documents the broken 'python3 -m installer' invocation"
    stale_invocations=$((stale_invocations + 1))
  fi
done
if [[ "$stale_invocations" -eq 0 ]]; then
  pass "no packaged doc documents the broken 'python3 -m installer' invocation"
fi

# ── 5. Run the documented entry point (safely, non-interactively) ──────────
echo "== Running installer/run.sh --help (packaged) =="
if (cd "$PACKAGE_ROOT" && ./installer/run.sh --help </dev/null >"$ARTIFACT_DIR/help-package.txt" 2>&1); then
  pass "./installer/run.sh --help succeeds from the extracted package"
else
  cat "$ARTIFACT_DIR/help-package.txt" >&2
  fail "./installer/run.sh --help failed from the extracted package"
fi

echo "== Running installer/run.sh --help (source checkout) =="
if (cd "$ROOT" && ./installer/run.sh --help </dev/null >"$ARTIFACT_DIR/help-source.txt" 2>&1); then
  pass "./installer/run.sh --help succeeds from the source checkout"
else
  cat "$ARTIFACT_DIR/help-source.txt" >&2
  fail "./installer/run.sh --help failed from the source checkout"
fi

# Strip uv's one-time "Building/Built/Installed" noise (absolute paths differ
# between the source checkout and the extracted package by construction) and
# compare only the actual --help output the two entry points produce.
if diff -q \
  <(grep -vE '^[[:space:]]*(Building|Built|Installed)\b' "$ARTIFACT_DIR/help-package.txt") \
  <(grep -vE '^[[:space:]]*(Building|Built|Installed)\b' "$ARTIFACT_DIR/help-source.txt") \
  >/dev/null 2>&1; then
  pass "installer/run.sh --help output is identical from source and package"
else
  fail "installer/run.sh --help output differs between source and package"
fi

# ── 6. Full non-interactive install into the extracted package ─────────────
echo "== Running a full non-interactive install (prod, no GPU, no SSL) =="
LIBRARY_PATH="$WORK_DIR/library"
AUTH_DB_PATH="$WORK_DIR/auth/users.db"
mkdir -p "$LIBRARY_PATH"

if (cd "$PACKAGE_ROOT" && ./installer/run.sh \
  --library-path "$LIBRARY_PATH" \
  --admin-user smoketest-admin \
  --admin-password 'Sm0ke-Test-Passw0rd!' \
  --origin http://localhost \
  --auth-db-path "$AUTH_DB_PATH" \
  --environment prod \
  --gpu none \
  --no-ssl \
  --topology single-node \
  </dev/null >"$ARTIFACT_DIR/install.log" 2>&1); then
  pass "non-interactive installer run succeeded"
else
  cat "$ARTIFACT_DIR/install.log" >&2
  fail "non-interactive installer run failed"
fi

if [[ -f "$PACKAGE_ROOT/.env" ]]; then
  pass "installer generated .env"
  if grep -q '^AUTH_JWT_SECRET=generate-with-installer$' "$PACKAGE_ROOT/.env"; then
    fail ".env still contains the insecure placeholder AUTH_JWT_SECRET"
  else
    pass ".env contains a generated AUTH_JWT_SECRET"
  fi
else
  fail "installer did not generate .env"
fi

if [[ -f "$AUTH_DB_PATH" ]]; then
  pass "installer generated the auth database"
else
  fail "installer did not generate the auth database at $AUTH_DB_PATH"
fi

if [[ -x "$PACKAGE_ROOT/start.sh" ]]; then
  pass "installer generated an executable start.sh"
  if grep -q -- '-f docker-compose.yml -f docker/compose.prod.yml' "$PACKAGE_ROOT/start.sh"; then
    pass "start.sh compose chain starts with docker-compose.yml then docker/compose.prod.yml"
  else
    fail "start.sh compose chain does not start with docker-compose.yml then docker/compose.prod.yml"
  fi
else
  fail "installer did not generate an executable start.sh"
fi

# ── 7. Validate every Compose combination the installer can generate ───────
# (prod environment only — the release package does not ship dev build
# contexts for docker-compose.yml's app services, so --environment dev is
# intentionally out of scope for the packaged installer.)
echo "== Validating packaged Compose file combinations =="

HAVE_DOCKER=0
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  HAVE_DOCKER=1
fi

HAVE_PYYAML=0
if python3 -c 'import yaml' >/dev/null 2>&1; then
  HAVE_PYYAML=1
fi

validate_compose_files() {
  # Validates the exact compose file list with `docker compose config`, or
  # falls back to a per-file YAML syntax check (Docker's custom !override /
  # !reset merge tags are registered so PyYAML doesn't choke on them).
  local label="$1"
  shift
  local -a compose_args=("$@")

  if [[ "$HAVE_DOCKER" -eq 1 ]]; then
    if (
      cd "$PACKAGE_ROOT" && \
      AUTH_JWT_SECRET=smoketest-secret \
      AUTH_DB_DIR="$WORK_DIR/auth" \
      SOLR_ADMIN_USER=smoketest-admin \
      SOLR_ADMIN_PASS=smoketest-admin-pass \
      SOLR_READONLY_USER=smoketest-read \
      SOLR_READONLY_PASS=smoketest-read-pass \
      NGINX_HOST=smoketest.example.invalid \
      docker compose "${compose_args[@]}" config >/dev/null 2>"$ARTIFACT_DIR/compose-$label.err"
    ); then
      pass "docker compose config succeeds: $label"
    else
      cat "$ARTIFACT_DIR/compose-$label.err" >&2
      fail "docker compose config failed: $label"
    fi
    return
  fi

  if [[ "$HAVE_PYYAML" -eq 0 ]]; then
    skip "compose syntax check for $label (PyYAML not available in this environment)"
    return
  fi

  local file
  local -a files=()
  local i=0
  while [[ $i -lt ${#compose_args[@]} ]]; do
    if [[ "${compose_args[$i]}" == "-f" ]]; then
      files+=("${compose_args[$((i + 1))]}")
      i=$((i + 2))
    else
      i=$((i + 1))
    fi
  done

  local ok=1
  for file in "${files[@]}"; do
    if ! PACKAGE_ROOT="$PACKAGE_ROOT" COMPOSE_FILE="$file" python3 - <<'PYEOF'
import os
import sys

import yaml


class _ComposeTagLoader(yaml.SafeLoader):
    pass


def _passthrough(loader, node):
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_scalar(node)


for tag in ("!override", "!reset"):
    _ComposeTagLoader.add_constructor(tag, _passthrough)

path = os.path.join(os.environ["PACKAGE_ROOT"], os.environ["COMPOSE_FILE"])
with open(path, encoding="utf-8") as handle:
    yaml.load(handle, Loader=_ComposeTagLoader)
PYEOF
    then
      ok=0
    fi
  done

  if [[ "$ok" -eq 1 ]]; then
    pass "YAML syntax check succeeds (no Docker): $label"
  else
    fail "YAML syntax check failed (no Docker): $label"
  fi
}

# Mirrors installer/setup.py's generate_start_script() ordering for the
# prod branch: docker-compose.yml, docker/compose.prod.yml, then optional GPU,
# SSL, and topology overlays in that fixed order.
for gpu in none nvidia intel; do
  for ssl in false true; do
    for topology in single-node distributed; do
      label="gpu=$gpu,ssl=$ssl,topology=$topology"
      args=(-f docker-compose.yml -f docker/compose.prod.yml)
      case "$gpu" in
        nvidia) args+=(-f docker/compose.gpu-nvidia.yml) ;;
        intel) args+=(-f docker/compose.gpu-intel.yml) ;;
      esac
      if [[ "$ssl" == "true" ]]; then
        args+=(-f docker/compose.ssl.yml)
      fi
      if [[ "$topology" == "single-node" ]]; then
        args+=(-f docker/compose.single-node.yml)
      fi
      validate_compose_files "$label" "${args[@]}"
    done
  done
done

# Cross-check: actually drive the installer for a representative sample of
# combinations and confirm the *generated start.sh* matches the compose file
# list this test independently computed above (catches drift between this
# test's matrix and the installer's real behavior).
echo "== Cross-checking installer-generated start.sh against the test matrix =="
check_generated_chain() {
  local gpu="$1" ssl="$2" topology="$3"
  shift 3
  local -a expected_args=("$@")
  local expected_chain="${expected_args[*]}"

  local -a ssl_flags=(--no-ssl)
  if [[ "$ssl" == "true" ]]; then
    ssl_flags=(--ssl --domain smoketest.example.invalid)
  fi

  if (cd "$PACKAGE_ROOT" && ./installer/run.sh \
    --library-path "$LIBRARY_PATH" \
    --admin-user smoketest-admin \
    --admin-password 'Sm0ke-Test-Passw0rd!' \
    --origin http://localhost \
    --auth-db-path "$AUTH_DB_PATH" \
    --environment prod \
    --gpu "$gpu" \
    "${ssl_flags[@]}" \
    --topology "$topology" \
    </dev/null >"$ARTIFACT_DIR/install-$gpu-$ssl-$topology.log" 2>&1); then
    if grep -qF -- "docker compose $expected_chain up" "$PACKAGE_ROOT/start.sh"; then
      pass "generated start.sh matches expected compose chain: gpu=$gpu,ssl=$ssl,topology=$topology"
    else
      fail "generated start.sh does NOT match expected compose chain: gpu=$gpu,ssl=$ssl,topology=$topology"
      cat "$PACKAGE_ROOT/start.sh" >&2
    fi
  else
    cat "$ARTIFACT_DIR/install-$gpu-$ssl-$topology.log" >&2
    fail "installer run failed while cross-checking gpu=$gpu,ssl=$ssl,topology=$topology"
  fi
}

check_generated_chain none false distributed \
  -f docker-compose.yml -f docker/compose.prod.yml
check_generated_chain nvidia true single-node \
  -f docker-compose.yml -f docker/compose.prod.yml -f docker/compose.gpu-nvidia.yml -f docker/compose.ssl.yml -f docker/compose.single-node.yml
check_generated_chain intel false single-node \
  -f docker-compose.yml -f docker/compose.prod.yml -f docker/compose.gpu-intel.yml -f docker/compose.single-node.yml

# ── 8. Run the literal documented production command from the package ─────
echo "== Validating the literal documented quickstart command ==" 
if [[ "$HAVE_DOCKER" -eq 1 ]]; then
  if (
    cd "$PACKAGE_ROOT" && \
    AUTH_JWT_SECRET=smoketest-secret \
    AUTH_DB_DIR="$WORK_DIR/auth" \
    SOLR_ADMIN_USER=smoketest-admin \
    SOLR_ADMIN_PASS=smoketest-admin-pass \
    SOLR_READONLY_USER=smoketest-read \
    SOLR_READONLY_PASS=smoketest-read-pass \
    docker compose -f docker-compose.yml -f docker/compose.prod.yml config >/dev/null 2>"$ARTIFACT_DIR/quickstart-cmd.err"
  ); then
    pass "literal quickstart command validates: docker compose -f docker-compose.yml -f docker/compose.prod.yml config"
  else
    cat "$ARTIFACT_DIR/quickstart-cmd.err" >&2
    fail "literal quickstart command failed to validate"
  fi
else
  skip "literal quickstart command validation (Docker not available)"
fi

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo "== Summary =="
echo "Passed: $PASS_COUNT, Failed: $FAIL_COUNT, Skipped: $SKIP_COUNT"

if [[ "$FAIL_COUNT" -gt 0 ]]; then
  exit 1
fi
exit 0

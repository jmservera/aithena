#!/usr/bin/env bash
# Validate that Solr 10 image support stays wired into CI without forcing the
# runtime cutover before solr-init compatibility has landed.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

grep -Eq '^ARG SOLR_BASE_IMAGE=solr:9\.7$' src/solr/Dockerfile ||
  fail "src/solr/Dockerfile must keep Solr 9.7 as the default base until the Solr 10 cutover"

grep -Eq '^FROM \$\{SOLR_BASE_IMAGE\}$' src/solr/Dockerfile ||
  fail "src/solr/Dockerfile must build from SOLR_BASE_IMAGE"

grep -q 'tag_suffix: "-solr10"' .github/workflows/build-containers.yml ||
  fail "build-containers.yml must publish a Solr 10 suffixed image"

grep -q 'SOLR_BASE_IMAGE=solr:10' .github/workflows/build-containers.yml ||
  fail "build-containers.yml must build the Solr image with SOLR_BASE_IMAGE=solr:10"

grep -q 'docker/compose.solr10.yml' .github/workflows/solr-image-validation.yml ||
  fail "solr-image-validation.yml must validate the opt-in Solr 10 Compose overlay"

grep -Eq '^[[:space:]]*SOLR_BASE_IMAGE:[[:space:]]*solr:10$' docker/compose.solr10.yml ||
  fail "docker/compose.solr10.yml must opt Solr builds into solr:10"

grep -Eq '^[[:space:]]*SOLR_VERSION:[[:space:]]*"10"$' docker/compose.solr10.yml ||
  fail "docker/compose.solr10.yml must opt Solr runtime into SOLR_VERSION=10"

if grep -Eq '^[[:space:]]*image:[[:space:]]*ghcr\.io/jmservera/aithena-solr:' docker-compose.yml docker/*.yml; then
  fail "compose must not consume the experimental Solr 10 image before issue #1337 lands"
fi

if grep -Eq '^[[:space:]]*SOLR_VERSION:[[:space:]]*"10"$' docker-compose.yml docker/compose.prod.yml; then
  fail "default runtime compose files must not force SOLR_VERSION=10 before cutover"
fi

echo "OK: Solr 10 image references are wired for CI and isolated behind the opt-in Compose overlay"

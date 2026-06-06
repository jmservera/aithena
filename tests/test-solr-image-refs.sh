#!/usr/bin/env bash
# Validate that Solr 10 is the default runtime while a Solr 9.7 rollback path
# remains explicit.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

grep -Eq '^ARG SOLR_BASE_IMAGE=solr:10$' src/solr/Dockerfile ||
  fail "src/solr/Dockerfile must default to the Solr 10 base image"

grep -Eq '^FROM \$\{SOLR_BASE_IMAGE\}$' src/solr/Dockerfile ||
  fail "src/solr/Dockerfile must build from SOLR_BASE_IMAGE"

grep -q 'tag_suffix: "-solr9"' .github/workflows/build-containers.yml ||
  fail "build-containers.yml must publish a Solr 9 rollback image"

grep -q 'SOLR_BASE_IMAGE=solr:9.7' .github/workflows/build-containers.yml ||
  fail "build-containers.yml must build the rollback Solr image with SOLR_BASE_IMAGE=solr:9.7"

grep -q 'docker/compose.solr9.yml' .github/workflows/solr-image-validation.yml ||
  fail "solr-image-validation.yml must validate the Solr 9 rollback Compose overlay"

grep -Eq '^[[:space:]]*SOLR_BASE_IMAGE:[[:space:]]*\$\{SOLR_BASE_IMAGE:-solr:10\}$' docker-compose.yml docker/compose.prod.yml ||
  fail "default compose files must build Solr from solr:10 unless explicitly overridden"

grep -Eq '^[[:space:]]*SOLR_VERSION:[[:space:]]*\$\{SOLR_VERSION:-10\}$' docker-compose.yml docker/compose.prod.yml ||
  fail "default compose files must set SOLR_VERSION=10 unless explicitly overridden"

grep -Fq -- '- SOLR_VERSION=${SOLR_VERSION:-10}' docker-compose.yml ||
  fail "docker-compose.yml must set solr-search SOLR_VERSION=10 unless explicitly overridden"

grep -Fq -- '- SOLR_VERSION=${SOLR_VERSION:-10}' docker/compose.prod.yml ||
  fail "docker/compose.prod.yml must set solr-search SOLR_VERSION=10 unless explicitly overridden"

grep -Eq '^[[:space:]]*SOLR_BASE_IMAGE:[[:space:]]*solr:10$' docker/compose.solr10.yml ||
  fail "docker/compose.solr10.yml must opt Solr builds into solr:10"

grep -Eq '^[[:space:]]*SOLR_VERSION:[[:space:]]*"10"$' docker/compose.solr10.yml ||
  fail "docker/compose.solr10.yml must opt Solr runtime into SOLR_VERSION=10"

grep -Eq '^[[:space:]]*-[[:space:]]*SOLR_VERSION=10$' docker/compose.solr10.yml ||
  fail "docker/compose.solr10.yml must opt solr-search into SOLR_VERSION=10"

grep -Eq '^[[:space:]]*SOLR_BASE_IMAGE:[[:space:]]*solr:9\.7$' docker/compose.solr9.yml ||
  fail "docker/compose.solr9.yml must provide a Solr 9.7 rollback base image"

grep -Eq '^[[:space:]]*SOLR_VERSION:[[:space:]]*"9"$' docker/compose.solr9.yml ||
  fail "docker/compose.solr9.yml must provide a Solr 9 runtime rollback"

grep -Eq '^[[:space:]]*-[[:space:]]*SOLR_VERSION=9$' docker/compose.solr9.yml ||
  fail "docker/compose.solr9.yml must opt solr-search into SOLR_VERSION=9"

echo "OK: Solr 10 is the default runtime and Solr 9 rollback references are wired"

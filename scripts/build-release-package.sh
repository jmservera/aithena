#!/usr/bin/env bash
# =============================================================================
# Aithena — Release Package Builder
# =============================================================================
# Stages (and optionally archives) the production release package: the same
# layout that ships in the GitHub release tarball. This is the single source
# of truth for release packaging, used by:
#   - .github/workflows/release.yml (package-release job)
#   - tests/test-release-package-smoke.sh (CI + local smoke test)
#
# The staged layout mirrors the paths documented in README.md / docs/*.md, so
# operators can run the documented commands (docker compose -f
# docker-compose.yml -f docker/compose.prod.yml ..., ./installer/run.sh, ...)
# directly from an extracted release archive with no path translation.
#
# Usage:
#   scripts/build-release-package.sh [OPTIONS]
#
# Options:
#   --version VERSION     Version to stamp (default: contents of VERSION file)
#   --output-dir DIR       Staging directory (default: release-package)
#   --archive PATH         Also create a .tar.gz at PATH
#   --checksum             Write a .sha256 checksum next to --archive
#   --help, -h             Show this help text
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

OUTPUT_DIR="release-package"
ARCHIVE_PATH=""
WRITE_CHECKSUM=0
VERSION=""

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { printf "${GREEN}[INFO]${NC}  %s\n" "$*"; }
step()  { printf "${BLUE}[STEP]${NC}  %s\n" "$*"; }
error() { printf "${RED}[ERROR]${NC} %s\n" "$*" >&2; }

usage() {
  cat <<'USAGE'
Usage: scripts/build-release-package.sh [OPTIONS]

Stage (and optionally archive) the Aithena production release package.

Options:
  --version VERSION   Version to stamp (default: contents of VERSION file)
  --output-dir DIR     Staging directory (default: release-package)
  --archive PATH        Also create a .tar.gz at PATH from the staged directory
  --checksum            Write PATH.sha256 (requires --archive)
  --help, -h            Show this help text
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version) VERSION="${2:-}"; shift 2 ;;
    --output-dir) OUTPUT_DIR="${2:-}"; shift 2 ;;
    --archive) ARCHIVE_PATH="${2:-}"; shift 2 ;;
    --checksum) WRITE_CHECKSUM=1; shift ;;
    --help|-h) usage; exit 0 ;;
    *) error "Unknown option: $1"; usage; exit 1 ;;
  esac
done

if [[ -z "$VERSION" ]]; then
  if [[ ! -f VERSION ]]; then
    error "VERSION file not found and --version not supplied"
    exit 1
  fi
  VERSION="$(tr -d '[:space:]' < VERSION)"
fi

# Bind-mount config paths required by docker-compose.yml / docker/compose.prod.yml.
# Kept in sync with scripts/package-offline-installer.sh's PACKAGE_CONFIG_BIND_PATHS.
CONFIG_BIND_PATHS=(
  "src/redis/redis.conf"
  "src/rabbitmq/rabbitmq.conf"
  "src/rabbitmq/init-definitions.sh"
  "src/nginx/docker-entrypoint-solr-auth.sh"
  "src/nginx/default.conf.template"
  "src/nginx/html"
  "src/solr/Dockerfile"
  "src/solr/entrypoint.sh"
  "src/solr/log4j2.xml"
  "src/solr/books"
  "src/solr/add-conf-overlay.sh"
)

# Compose files the packaged installer's generated start.sh (and the
# packaged docs) can reference. installer/setup.py selects among these based
# on the operator's --environment/--gpu/--ssl/--topology choices, so they all
# need to ship together with docker-compose.yml + docker/compose.prod.yml.
COMPOSE_OVERLAY_FILES=(
  "docker/compose.prod.yml"
  "docker/compose.dev-ports.yml"
  "docker/compose.gpu-nvidia.yml"
  "docker/compose.gpu-intel.yml"
  "docker/compose.ssl.yml"
  "docker/compose.single-node.yml"
)

step "Staging release package v${VERSION} → ${OUTPUT_DIR}"

rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR/installer" "$OUTPUT_DIR/docker" "$OUTPUT_DIR/docs"

# Core production files — paths match README.md / docs/*.md exactly:
#   docker-compose.yml (base, always included)
#   docker/compose.*.yml (overlays selectable by the installer / documented commands)
cp docker-compose.yml "$OUTPUT_DIR/"
for overlay in "${COMPOSE_OVERLAY_FILES[@]}"; do
  cp "$overlay" "$OUTPUT_DIR/docker/"
done
cp .env.example "$OUTPUT_DIR/"
cp README.md "$OUTPUT_DIR/"
cp LICENSE "$OUTPUT_DIR/"
cp VERSION "$OUTPUT_DIR/"

# Installer: first-run CLI plus its aithena-common dependency, staged at the
# same relative path (../src/aithena-common) that installer/setup.py and
# installer/pyproject.toml expect, so `uv run installer/setup.py` and
# `installer/run.sh` work unmodified from the extracted archive.
cp -r installer/* "$OUTPUT_DIR/installer/"
find "$OUTPUT_DIR/installer" -type d -name '__pycache__' -exec rm -rf {} +
mkdir -p "$OUTPUT_DIR/src/aithena-common"
cp -r src/aithena-common/aithena_common "$OUTPUT_DIR/src/aithena-common/"
cp src/aithena-common/pyproject.toml "$OUTPUT_DIR/src/aithena-common/"
if [[ -f src/aithena-common/uv.lock ]]; then
  cp src/aithena-common/uv.lock "$OUTPUT_DIR/src/aithena-common/"
fi

# Documentation
cp docs/quickstart.md docs/user-manual.md docs/admin-manual.md "$OUTPUT_DIR/docs/"

# Config files bind-mounted by docker-compose.yml / docker/compose.prod.yml
for rel_path in "${CONFIG_BIND_PATHS[@]}"; do
  dest_dir="$OUTPUT_DIR/$(dirname "$rel_path")"
  mkdir -p "$dest_dir"
  cp -r "$rel_path" "$dest_dir/"
done

info "Release package staged at: ${OUTPUT_DIR}"

if [[ -n "$ARCHIVE_PATH" ]]; then
  step "Creating archive: ${ARCHIVE_PATH}"
  mkdir -p "$(dirname "$ARCHIVE_PATH")"
  tar -czf "$ARCHIVE_PATH" -C "$OUTPUT_DIR" .
  info "Archive created: ${ARCHIVE_PATH}"

  if [[ "$WRITE_CHECKSUM" -eq 1 ]]; then
    sha256sum "$ARCHIVE_PATH" > "${ARCHIVE_PATH}.sha256"
    info "Checksum written: ${ARCHIVE_PATH}.sha256"
  fi
fi

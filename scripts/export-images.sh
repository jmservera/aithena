#!/usr/bin/env bash
# =============================================================================
# Aithena — Build & Export All Docker Images for Air-Gapped Deployment
# =============================================================================
# Runs on an INTERNET-CONNECTED machine. Builds all custom images, pulls all
# official base images, exports everything as compressed tarballs, and bundles
# into a self-contained archive for transfer to a disconnected target.
#
# Usage:
#   ./scripts/export-images.sh                  # full build + export
#   ./scripts/export-images.sh --dry-run        # show what would be done
#   ./scripts/export-images.sh --skip-build     # export existing images only
#   ./scripts/export-images.sh --help           # show this help
#
# Output:
#   staging/aithena-offline-v{VERSION}.tar.gz   — self-contained package
#
# Prerequisites:
#   - Docker Engine (with compose v2 plugin)
#   - gzip, tar, git
#   - Sufficient disk space (~15 GB free recommended)
#
# See also: docs/deployment/offline-deployment.md
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
umask 077

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

VERSION_FILE="$REPO_ROOT/VERSION"
DRY_RUN=0
SKIP_BUILD=0

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
info()    { printf "${GREEN}[INFO]${NC}  %s\n" "$*"; }
warn()    { printf "${YELLOW}[WARN]${NC}  %s\n" "$*"; }
error()   { printf "${RED}[ERROR]${NC} %s\n" "$*" >&2; }
step()    { printf "${BLUE}[STEP]${NC}  %s\n" "$*"; }

usage() {
  cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Build and export all Aithena Docker images for air-gapped deployment.

Options:
  --dry-run       Show what would be done without executing
  --skip-build    Skip building; export already-present images only
  --help          Show this help message

Output:
  staging/aithena-offline-v{VERSION}.tar.gz
EOF
}

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)    DRY_RUN=1;    shift ;;
    --skip-build) SKIP_BUILD=1; shift ;;
    --help|-h)    usage; exit 0 ;;
    *)            error "Unknown option: $1"; usage; exit 1 ;;
  esac
done

# ---------------------------------------------------------------------------
# Resolve version (same pattern as buildall.sh)
# ---------------------------------------------------------------------------
cd "$REPO_ROOT"

if git_tag="$(git describe --tags --exact-match 2>/dev/null)"; then
  VERSION="${git_tag#v}"
elif [[ -f "$VERSION_FILE" ]]; then
  VERSION="$(tr -d '[:space:]' < "$VERSION_FILE")"
else
  VERSION="dev"
fi

if [[ -z "$VERSION" ]]; then
  VERSION="dev"
fi

GIT_COMMIT="$(git rev-parse HEAD 2>/dev/null || printf 'unknown')"
BUILD_DATE="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

export VERSION GIT_COMMIT BUILD_DATE

info "Version:    ${VERSION}"
info "Git commit: ${GIT_COMMIT}"
info "Build date: ${BUILD_DATE}"

# ---------------------------------------------------------------------------
# Prerequisites check
# ---------------------------------------------------------------------------
for cmd in docker gzip tar git; do
  if ! command -v "$cmd" &>/dev/null; then
    error "Required command not found: $cmd"
    exit 1
  fi
done

if ! docker compose version &>/dev/null; then
  error "Docker Compose v2 plugin not found. Install docker-compose-plugin."
  exit 1
fi

# ---------------------------------------------------------------------------
# Image inventory
# ---------------------------------------------------------------------------
# Custom images (built by compose)
CUSTOM_IMAGES=(
  "ghcr.io/jmservera/aithena-embeddings-server:${VERSION}"
  "ghcr.io/jmservera/aithena-document-lister:${VERSION}"
  "ghcr.io/jmservera/aithena-document-indexer:${VERSION}"
  "ghcr.io/jmservera/aithena-solr-search:${VERSION}"
  "ghcr.io/jmservera/aithena-aithena-ui:${VERSION}"
)

# Official base images (pulled, not built) — one entry per unique image
OFFICIAL_IMAGES=(
  "redis:latest"
  "rabbitmq:4.0-management"
  "rediscommander/redis-commander:latest"
  "nginx:1.27-alpine"
  "zookeeper:3.9"
  "solr:9.7"
)

ALL_IMAGES=("${CUSTOM_IMAGES[@]}" "${OFFICIAL_IMAGES[@]}")

# ---------------------------------------------------------------------------
# Staging area
# ---------------------------------------------------------------------------
STAGING_DIR="$REPO_ROOT/staging"
PACKAGE_NAME="aithena-offline-v${VERSION}"
PACKAGE_DIR="${STAGING_DIR}/${PACKAGE_NAME}"

step "Preparing staging area: ${PACKAGE_DIR}"
if [[ "$DRY_RUN" -eq 1 ]]; then
  info "[DRY RUN] Would create ${PACKAGE_DIR}/{images,compose,config}"
else
  rm -rf "${PACKAGE_DIR}"
  mkdir -p "${PACKAGE_DIR}/images"
  mkdir -p "${PACKAGE_DIR}/compose"
  mkdir -p "${PACKAGE_DIR}/config/solr"
  mkdir -p "${PACKAGE_DIR}/config/nginx"
fi

# ---------------------------------------------------------------------------
# Step 1: Build custom images
# ---------------------------------------------------------------------------
if [[ "$SKIP_BUILD" -eq 1 ]]; then
  warn "Skipping build (--skip-build). Using existing local images."
elif [[ "$DRY_RUN" -eq 1 ]]; then
  info "[DRY RUN] Would run: docker compose build"
else
  step "Building custom images via docker compose..."
  docker compose build
  info "Build complete."
fi

# ---------------------------------------------------------------------------
# Step 2: Pull official base images
# ---------------------------------------------------------------------------
step "Pulling official base images..."
for img in "${OFFICIAL_IMAGES[@]}"; do
  if [[ "$DRY_RUN" -eq 1 ]]; then
    info "[DRY RUN] Would pull: ${img}"
  else
    info "Pulling ${img}..."
    docker pull "$img"
  fi
done

# ---------------------------------------------------------------------------
# Step 3: Export all images as compressed tarballs
# ---------------------------------------------------------------------------
step "Exporting Docker images..."

# Convert image reference to a safe filename
# e.g. ghcr.io/jmservera/aithena-solr-search:1.11.0 → aithena-solr-search_1.11.0
image_to_filename() {
  local img="$1"
  # Strip registry prefix
  local name="${img##*/}"
  # Replace : with _
  name="${name//:/_}"
  printf '%s' "$name"
}

TOTAL=${#ALL_IMAGES[@]}
CURRENT=0

for img in "${ALL_IMAGES[@]}"; do
  CURRENT=$((CURRENT + 1))
  filename="$(image_to_filename "$img")"
  tarball="${PACKAGE_DIR}/images/${filename}.tar.gz"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    info "[DRY RUN] [${CURRENT}/${TOTAL}] Would export: ${img} → images/${filename}.tar.gz"
  else
    info "[${CURRENT}/${TOTAL}] Exporting: ${img} → images/${filename}.tar.gz"
    docker save "$img" | gzip > "$tarball"
  fi
done

# ---------------------------------------------------------------------------
# Step 4: Copy compose files and configs
# ---------------------------------------------------------------------------
step "Copying compose files and configuration..."

if [[ "$DRY_RUN" -eq 1 ]]; then
  info "[DRY RUN] Would copy compose files, .env.example, configs"
else
  # Compose files for production
  cp "$REPO_ROOT/docker-compose.yml"      "${PACKAGE_DIR}/compose/"
  cp "$REPO_ROOT/docker/compose.prod.yml" "${PACKAGE_DIR}/compose/"
  cp "$REPO_ROOT/.env.example"            "${PACKAGE_DIR}/compose/.env.example"

  # Solr configsets
  if [[ -d "$REPO_ROOT/src/solr/books" ]]; then
    cp -r "$REPO_ROOT/src/solr/books" "${PACKAGE_DIR}/config/solr/"
  fi
  if [[ -f "$REPO_ROOT/src/solr/add-conf-overlay.sh" ]]; then
    cp "$REPO_ROOT/src/solr/add-conf-overlay.sh" "${PACKAGE_DIR}/config/solr/"
  fi

  # Nginx config
  if [[ -f "$REPO_ROOT/src/nginx/default.conf" ]]; then
    cp "$REPO_ROOT/src/nginx/default.conf" "${PACKAGE_DIR}/config/nginx/"
  fi
  if [[ -d "$REPO_ROOT/src/nginx/html" ]]; then
    cp -r "$REPO_ROOT/src/nginx/html" "${PACKAGE_DIR}/config/nginx/"
  fi

  # RabbitMQ config
  if [[ -f "$REPO_ROOT/src/rabbitmq/rabbitmq.conf" ]]; then
    mkdir -p "${PACKAGE_DIR}/config/rabbitmq"
    cp "$REPO_ROOT/src/rabbitmq/rabbitmq.conf" "${PACKAGE_DIR}/config/rabbitmq/"
  fi
fi

# ---------------------------------------------------------------------------
# Step 5: Copy installer scripts and metadata
# ---------------------------------------------------------------------------
step "Adding installer scripts and metadata..."

if [[ "$DRY_RUN" -eq 1 ]]; then
  info "[DRY RUN] Would copy install.sh, verify.sh, VERSION, README"
else
  cp "$REPO_ROOT/installer/install-offline.sh"  "${PACKAGE_DIR}/install.sh"
  cp "$REPO_ROOT/installer/verify.sh"           "${PACKAGE_DIR}/verify.sh"
  cp "$REPO_ROOT/VERSION"                       "${PACKAGE_DIR}/VERSION"
  chmod +x "${PACKAGE_DIR}/install.sh"
  chmod +x "${PACKAGE_DIR}/verify.sh"

  # Generate a minimal README inside the package
  cat > "${PACKAGE_DIR}/README.md" <<'PKGREADME'
# Aithena — Offline Deployment Package

This package contains everything needed to deploy Aithena on a machine
without internet access.

## Quick Start

```bash
# 1. Extract (if not already)
tar xzf aithena-offline-v*.tar.gz
cd aithena-offline-v*/

# 2. Install
sudo ./install.sh

# 3. Verify
./verify.sh
```

## Contents

| Directory   | Description                           |
|-------------|---------------------------------------|
| `images/`   | Docker images as compressed tarballs  |
| `compose/`  | Docker Compose files + env template   |
| `config/`   | Solr, nginx, and RabbitMQ configs     |
| `install.sh`| Offline installation script           |
| `verify.sh` | Post-install health check             |

## Full Documentation

See `docs/deployment/offline-deployment.md` in the source repository for
the complete deployment guide including prerequisites, transfer methods,
updating, and troubleshooting.
PKGREADME
fi

# ---------------------------------------------------------------------------
# Step 6: Create the final archive
# ---------------------------------------------------------------------------
ARCHIVE_PATH="${STAGING_DIR}/${PACKAGE_NAME}.tar.gz"

step "Creating archive: ${ARCHIVE_PATH}"

if [[ "$DRY_RUN" -eq 1 ]]; then
  info "[DRY RUN] Would create: ${ARCHIVE_PATH}"
  info "[DRY RUN] Contents:"
  info "  ${PACKAGE_NAME}/images/   (${TOTAL} image tarballs)"
  info "  ${PACKAGE_NAME}/compose/  (docker-compose.yml, docker/compose.prod.yml, .env.example)"
  info "  ${PACKAGE_NAME}/config/   (solr, nginx, rabbitmq configs)"
  info "  ${PACKAGE_NAME}/install.sh"
  info "  ${PACKAGE_NAME}/verify.sh"
  info "  ${PACKAGE_NAME}/VERSION"
  info "  ${PACKAGE_NAME}/README.md"
else
  (cd "$STAGING_DIR" && tar czf "${PACKAGE_NAME}.tar.gz" "${PACKAGE_NAME}")

  ARCHIVE_SIZE="$(du -sh "$ARCHIVE_PATH" | cut -f1)"
  info "Archive created: ${ARCHIVE_PATH} (${ARCHIVE_SIZE})"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
info "========================================="
info "  Offline package ready!"
info "========================================="
info "  Version:  ${VERSION}"
info "  Archive:  ${ARCHIVE_PATH}"
info "  Images:   ${TOTAL} (${#CUSTOM_IMAGES[@]} custom + ${#OFFICIAL_IMAGES[@]} official)"
echo ""
info "Transfer this file to the target machine, then run:"
info "  tar xzf ${PACKAGE_NAME}.tar.gz"
info "  cd ${PACKAGE_NAME}"
info "  sudo ./install.sh"
echo ""

#!/usr/bin/env bash
# =============================================================================
# Aithena — Air-Gapped Offline Installer
# =============================================================================
# Runs on a DISCONNECTED target machine. Loads pre-exported Docker images,
# sets up configuration, creates required volumes/directories, and starts
# all services.
#
# Usage:
#   sudo ./install.sh                    # full installation
#   sudo ./install.sh --dry-run          # show what would be done
#   sudo ./install.sh --skip-load        # skip image loading (already loaded)
#   sudo ./install.sh --install-dir DIR  # custom installation directory
#   sudo ./install.sh --help             # show this help
#
# Prerequisites:
#   - Docker Engine ≥ 24.0
#   - Docker Compose v2 plugin
#   - 20 GB free disk space (images + volumes)
#   - Root / sudo access
#
# See also: docs/deployment/offline-deployment.md
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
umask 077

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_DIR="$SCRIPT_DIR"

DRY_RUN=0
SKIP_LOAD=0
INSTALL_DIR="/opt/aithena"

MIN_DOCKER_VERSION="24.0"
MIN_DISK_GB=20

# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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

Install Aithena from an offline package on a disconnected machine.

Options:
  --dry-run           Show what would be done without executing
  --skip-load         Skip Docker image loading (if already loaded)
  --install-dir DIR   Installation directory (default: /opt/aithena)
  --help              Show this help message

Prerequisites:
  - Docker Engine >= ${MIN_DOCKER_VERSION}
  - Docker Compose v2 plugin
  - ${MIN_DISK_GB} GB free disk space
  - Root / sudo access
EOF
}

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)      DRY_RUN=1;         shift ;;
    --skip-load)    SKIP_LOAD=1;       shift ;;
    --install-dir)  INSTALL_DIR="$2";  shift 2 ;;
    --help|-h)      usage; exit 0 ;;
    *)              error "Unknown option: $1"; usage; exit 1 ;;
  esac
done

# ---------------------------------------------------------------------------
# Read version from package
# ---------------------------------------------------------------------------
if [[ -f "${PACKAGE_DIR}/VERSION" ]]; then
  VERSION="$(tr -d '[:space:]' < "${PACKAGE_DIR}/VERSION")"
else
  error "VERSION file not found in package. Is this a valid Aithena offline package?"
  exit 1
fi

info "Aithena Offline Installer v${VERSION}"
echo ""

# ---------------------------------------------------------------------------
# Step 1: Validate prerequisites
# ---------------------------------------------------------------------------
step "Validating prerequisites..."

# Must run as root
if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  error "This script must be run as root (use sudo)."
  exit 1
fi

# Docker Engine
if ! command -v docker &>/dev/null; then
  error "Docker Engine not found. Install Docker before running this script."
  error "See: https://docs.docker.com/engine/install/"
  exit 1
fi

DOCKER_VERSION="$(docker version --format '{{.Server.Version}}' 2>/dev/null || echo "0.0")"
info "Docker Engine: v${DOCKER_VERSION}"

# Simple major.minor version comparison
version_ge() {
  local IFS=.
  local i ver1=($1) ver2=($2)
  for ((i=0; i<${#ver2[@]}; i++)); do
    local v1="${ver1[i]:-0}"
    local v2="${ver2[i]:-0}"
    if ((v1 > v2)); then return 0; fi
    if ((v1 < v2)); then return 1; fi
  done
  return 0
}

if ! version_ge "$DOCKER_VERSION" "$MIN_DOCKER_VERSION"; then
  error "Docker Engine >= ${MIN_DOCKER_VERSION} required (found ${DOCKER_VERSION})."
  exit 1
fi

# Docker Compose v2
if ! docker compose version &>/dev/null; then
  error "Docker Compose v2 plugin not found."
  error "Install: sudo apt-get install docker-compose-plugin"
  exit 1
fi

COMPOSE_VERSION="$(docker compose version --short 2>/dev/null || echo "unknown")"
info "Docker Compose: v${COMPOSE_VERSION}"

# Disk space check
AVAILABLE_GB="$(df --output=avail -BG "${INSTALL_DIR%/*}" 2>/dev/null | tail -1 | tr -dc '0-9' || echo "0")"
if [[ "$AVAILABLE_GB" -lt "$MIN_DISK_GB" ]]; then
  warn "Low disk space: ${AVAILABLE_GB} GB available, ${MIN_DISK_GB} GB recommended."
  warn "Continuing anyway — installation may fail if space runs out."
else
  info "Disk space: ${AVAILABLE_GB} GB available (${MIN_DISK_GB} GB required)"
fi

# Verify package contents
if [[ ! -d "${PACKAGE_DIR}/images" ]]; then
  error "images/ directory not found. Is this a valid offline package?"
  exit 1
fi

IMAGE_COUNT="$(find "${PACKAGE_DIR}/images" -name '*.tar.gz' | wc -l)"
if [[ "$IMAGE_COUNT" -eq 0 ]]; then
  error "No image tarballs found in images/ directory."
  exit 1
fi

info "Package contains ${IMAGE_COUNT} image archives."
info "Prerequisites: OK"
echo ""

# ---------------------------------------------------------------------------
# Step 2: Load Docker images
# ---------------------------------------------------------------------------
if [[ "$SKIP_LOAD" -eq 1 ]]; then
  warn "Skipping image loading (--skip-load)."
else
  step "Loading Docker images (${IMAGE_COUNT} archives)..."

  LOADED=0
  FAILED=0

  for tarball in "${PACKAGE_DIR}"/images/*.tar.gz; do
    filename="$(basename "$tarball")"
    LOADED=$((LOADED + 1))

    if [[ "$DRY_RUN" -eq 1 ]]; then
      info "[DRY RUN] [${LOADED}/${IMAGE_COUNT}] Would load: ${filename}"
    else
      info "[${LOADED}/${IMAGE_COUNT}] Loading: ${filename}..."
      if gunzip -c "$tarball" | docker load 2>&1; then
        info "  ✓ Loaded successfully"
      else
        error "  ✗ Failed to load: ${filename}"
        FAILED=$((FAILED + 1))
      fi
    fi
  done

  if [[ "$FAILED" -gt 0 ]]; then
    error "${FAILED} image(s) failed to load."
    exit 1
  fi

  info "All images loaded successfully."
  echo ""
fi

# ---------------------------------------------------------------------------
# Step 3: Set up installation directory
# ---------------------------------------------------------------------------
step "Setting up installation directory: ${INSTALL_DIR}"

if [[ "$DRY_RUN" -eq 1 ]]; then
  info "[DRY RUN] Would create ${INSTALL_DIR} and copy files"
else
  mkdir -p "$INSTALL_DIR"

  # Copy compose files
  cp "${PACKAGE_DIR}/compose/docker-compose.yml"      "${INSTALL_DIR}/"
  cp "${PACKAGE_DIR}/compose/docker-compose.prod.yml" "${INSTALL_DIR}/"

  # Copy configs preserving directory structure
  mkdir -p "${INSTALL_DIR}/src/solr"
  mkdir -p "${INSTALL_DIR}/src/nginx"
  mkdir -p "${INSTALL_DIR}/src/rabbitmq"

  # Solr configsets
  if [[ -d "${PACKAGE_DIR}/config/solr/books" ]]; then
    cp -r "${PACKAGE_DIR}/config/solr/books" "${INSTALL_DIR}/src/solr/"
  fi
  if [[ -f "${PACKAGE_DIR}/config/solr/add-conf-overlay.sh" ]]; then
    cp "${PACKAGE_DIR}/config/solr/add-conf-overlay.sh" "${INSTALL_DIR}/src/solr/"
    chmod +x "${INSTALL_DIR}/src/solr/add-conf-overlay.sh"
  fi

  # Nginx config
  if [[ -f "${PACKAGE_DIR}/config/nginx/default.conf" ]]; then
    cp "${PACKAGE_DIR}/config/nginx/default.conf" "${INSTALL_DIR}/src/nginx/"
  fi
  if [[ -d "${PACKAGE_DIR}/config/nginx/html" ]]; then
    cp -r "${PACKAGE_DIR}/config/nginx/html" "${INSTALL_DIR}/src/nginx/"
  fi

  # RabbitMQ config
  if [[ -f "${PACKAGE_DIR}/config/rabbitmq/rabbitmq.conf" ]]; then
    cp "${PACKAGE_DIR}/config/rabbitmq/rabbitmq.conf" "${INSTALL_DIR}/src/rabbitmq/"
  fi

  # Copy VERSION for reference
  cp "${PACKAGE_DIR}/VERSION" "${INSTALL_DIR}/"

  info "Files installed to ${INSTALL_DIR}"
fi

# ---------------------------------------------------------------------------
# Step 4: Generate .env if not present
# ---------------------------------------------------------------------------
step "Configuring environment..."

ENV_FILE="${INSTALL_DIR}/.env"

if [[ -f "$ENV_FILE" ]]; then
  info "Existing .env found — preserving current configuration."
else
  if [[ "$DRY_RUN" -eq 1 ]]; then
    info "[DRY RUN] Would generate .env from template"
  else
    if [[ -f "${PACKAGE_DIR}/compose/.env.example" ]]; then
      cp "${PACKAGE_DIR}/compose/.env.example" "$ENV_FILE"

      # Generate secure random values for secrets
      JWT_SECRET="$(openssl rand -base64 48 2>/dev/null || head -c 48 /dev/urandom | base64)"
      ADMIN_API_KEY="$(openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | xxd -p | head -c 64)"
      RABBIT_PASS="$(openssl rand -base64 24 2>/dev/null || head -c 24 /dev/urandom | base64)"

      # Substitute placeholder values
      sed -i "s|AUTH_JWT_SECRET=generate-with-installer|AUTH_JWT_SECRET=${JWT_SECRET}|" "$ENV_FILE"
      sed -i "s|ADMIN_API_KEY=generate-with-installer|ADMIN_API_KEY=${ADMIN_API_KEY}|" "$ENV_FILE"
      sed -i "s|RABBITMQ_USER=generate-with-installer|RABBITMQ_USER=aithena|" "$ENV_FILE"
      sed -i "s|RABBITMQ_PASS=generate-with-installer|RABBITMQ_PASS=${RABBIT_PASS}|" "$ENV_FILE"

      # Set version
      sed -i "s|VERSION=.*|VERSION=${VERSION}|" "$ENV_FILE"

      # Set default paths for offline deployment
      sed -i "s|BOOKS_PATH=.*|BOOKS_PATH=/data/booklibrary|" "$ENV_FILE"
      sed -i "s|BOOK_LIBRARY_PATH=.*|BOOK_LIBRARY_PATH=/data/booklibrary|" "$ENV_FILE"
      sed -i "s|AUTH_DB_DIR=.*|AUTH_DB_DIR=/opt/aithena/data/auth|" "$ENV_FILE"

      chmod 600 "$ENV_FILE"
      info ".env generated with secure random secrets."
      warn "Review ${ENV_FILE} and adjust paths before starting services."
    else
      error ".env.example not found in package. Create .env manually."
    fi
  fi
fi

# ---------------------------------------------------------------------------
# Step 5: Create required directories and set permissions
# ---------------------------------------------------------------------------
step "Creating data directories..."

# Volume bind-mount directories (matching docker-compose.yml volume definitions)
VOLUME_DIRS=(
  "/source/volumes/rabbitmq-data"
  "/source/volumes/redis"
  "/source/volumes/solr-data"
  "/source/volumes/solr-data2"
  "/source/volumes/solr-data3"
  "/source/volumes/zoo-data1/logs"
  "/source/volumes/zoo-data1/data"
  "/source/volumes/zoo-data1/datalog"
  "/source/volumes/zoo-data2/logs"
  "/source/volumes/zoo-data2/data"
  "/source/volumes/zoo-data2/datalog"
  "/source/volumes/zoo-data3/logs"
  "/source/volumes/zoo-data3/data"
  "/source/volumes/zoo-data3/datalog"
  "/source/volumes/zoo-backup"
  "/source/volumes/collections-db"
  "/data/booklibrary"
  "/opt/aithena/data/auth"
)

# UID mappings for bind-mount ownership (must match container expectations)
# See Brett's history: bind-mount ownership is always the host's
declare -A DIR_UIDS=(
  ["/source/volumes/rabbitmq-data"]="100"
  ["/source/volumes/redis"]="999"
  ["/source/volumes/solr-data"]="8983"
  ["/source/volumes/solr-data2"]="8983"
  ["/source/volumes/solr-data3"]="8983"
  ["/source/volumes/zoo-data1/logs"]="1000"
  ["/source/volumes/zoo-data1/data"]="1000"
  ["/source/volumes/zoo-data1/datalog"]="1000"
  ["/source/volumes/zoo-data2/logs"]="1000"
  ["/source/volumes/zoo-data2/data"]="1000"
  ["/source/volumes/zoo-data2/datalog"]="1000"
  ["/source/volumes/zoo-data3/logs"]="1000"
  ["/source/volumes/zoo-data3/data"]="1000"
  ["/source/volumes/zoo-data3/datalog"]="1000"
  ["/source/volumes/zoo-backup"]="1000"
  ["/source/volumes/collections-db"]="1000"
  ["/opt/aithena/data/auth"]="1000"
)

for dir in "${VOLUME_DIRS[@]}"; do
  if [[ "$DRY_RUN" -eq 1 ]]; then
    info "[DRY RUN] Would create: ${dir}"
  else
    mkdir -p "$dir"
    uid="${DIR_UIDS[$dir]:-1000}"
    chown "$uid:$uid" "$dir"
    info "Created: ${dir} (uid:${uid})"
  fi
done

echo ""

# ---------------------------------------------------------------------------
# Step 6: Start services
# ---------------------------------------------------------------------------
step "Starting Aithena services..."

if [[ "$DRY_RUN" -eq 1 ]]; then
  info "[DRY RUN] Would run: docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d"
else
  cd "$INSTALL_DIR"
  docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

  info "Services started."
fi

# ---------------------------------------------------------------------------
# Step 7: Basic health check
# ---------------------------------------------------------------------------
step "Running initial health check (waiting for services to start)..."

if [[ "$DRY_RUN" -eq 1 ]]; then
  info "[DRY RUN] Would wait for services and check health"
else
  # Wait for services to initialize
  TIMEOUT=180
  ELAPSED=0
  INTERVAL=10

  info "Waiting up to ${TIMEOUT}s for services to become healthy..."

  while [[ "$ELAPSED" -lt "$TIMEOUT" ]]; do
    HEALTHY_COUNT="$(docker compose -f docker-compose.yml -f docker-compose.prod.yml ps --format json 2>/dev/null | grep -c '"healthy"' || true)"
    TOTAL_SERVICES="$(docker compose -f docker-compose.yml -f docker-compose.prod.yml ps --format json 2>/dev/null | wc -l || true)"

    if [[ "$HEALTHY_COUNT" -gt 0 ]]; then
      info "  ${HEALTHY_COUNT}/${TOTAL_SERVICES} services healthy (${ELAPSED}s elapsed)"
    fi

    # Check if nginx is responding (last service to come up)
    if curl -sf -o /dev/null "http://127.0.0.1:80/health" 2>/dev/null; then
      info "nginx health check passed — stack is ready."
      break
    fi

    sleep "$INTERVAL"
    ELAPSED=$((ELAPSED + INTERVAL))
  done

  if [[ "$ELAPSED" -ge "$TIMEOUT" ]]; then
    warn "Timed out waiting for all services. Some may still be starting."
    warn "Run './verify.sh' to check status, or wait and try again."
  fi
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
info "========================================="
info "  Aithena v${VERSION} — Installation Complete"
info "========================================="
info "  Install dir: ${INSTALL_DIR}"
info "  Config:      ${ENV_FILE}"
info ""
info "  Next steps:"
info "  1. Review/edit ${ENV_FILE} (especially BOOKS_PATH)"
info "  2. Copy your book library to the BOOKS_PATH directory"
info "  3. Run: ./verify.sh (or ${PACKAGE_DIR}/verify.sh)"
info "  4. Access Aithena at: http://<server-ip>/"
echo ""

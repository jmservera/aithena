#!/usr/bin/env bash
set -euo pipefail

# Prevent running the entire script as root (e.g., via sudo ./installer/setupdev.sh)
if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
  echo "ERROR: Do not run this script as root or with sudo." >&2
  echo "Run it as your regular user; the script will invoke sudo only for privileged operations." >&2
  exit 1
fi

# ============================================================
# Development Environment Setup Script for Aithena
# ============================================================
# This script installs essential development tools:
# - Docker Engine + plugins (container runtime for all services)
# - Node.js via nvm (for aithena-ui frontend and E2E tests)
# - GitHub CLI (for PR/issue management)
# - astral uv (Python package/project manager)
# - @github/copilot CLI (AI pair programming)
# ============================================================

# Cleanup temporary files on exit
cleanup() {
  if [[ -n "${TEMP_FILE:-}" && -f "$TEMP_FILE" ]]; then
    rm -f "$TEMP_FILE"
  fi
}
trap cleanup EXIT

# ============================================================
# Docker Engine + Plugins
# ============================================================
# Using official Docker APT repository for Ubuntu
# (avoids supply chain risk of curl | bash installer)

echo "==> Updating apt and installing prerequisites..."
sudo apt-get update
sudo apt-get install -y ca-certificates curl

echo "==> Creating /etc/apt/keyrings ..."
sudo install -m 0755 -d /etc/apt/keyrings

echo "==> Downloading Docker GPG key..."
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Determine Ubuntu codename safely
. /etc/os-release
CODENAME="${UBUNTU_CODENAME:-$VERSION_CODENAME}"

echo "==> Adding Docker apt repository for: ${CODENAME}"
sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: ${CODENAME}
Components: stable
Signed-By: /etc/apt/keyrings/docker.asc
EOF

echo "==> Updating apt and installing Docker packages..."
sudo apt-get update
sudo apt-get install -y \
  docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin \
  screen

echo "==> Done."
echo "    Test with: sudo docker run hello-world"

# Add the actual user (not root) to docker group
# Use SUDO_USER when script is run with sudo, fallback to USER
TARGET_USER="${SUDO_USER:-$USER}"
if ! sudo usermod -aG docker "$TARGET_USER"; then
  echo "WARNING: Failed to add $TARGET_USER to docker group" >&2
fi
echo "==> Added $TARGET_USER to the docker group."
echo "==> IMPORTANT: Log out/in (or reboot) for group changes to take effect."
echo "==> For this session, run Docker with: sudo docker ..."

# ============================================================
# Node.js (via nvm)
# ============================================================
# Node.js is required for aithena-ui (React frontend) and E2E tests
# Using nvm v0.40.4 (pinned) to install Node.js v24.x (latest 24 minor)

NVM_VERSION="v0.40.4"
NODE_MAJOR_VERSION="22"

echo "==> Installing nvm ${NVM_VERSION}..."
curl -o- "https://raw.githubusercontent.com/nvm-sh/nvm/${NVM_VERSION}/install.sh" | bash

# Source nvm in current shell
\. "$HOME/.nvm/nvm.sh"

echo "==> Installing Node.js ${NODE_MAJOR_VERSION}.x..."
nvm install "$NODE_MAJOR_VERSION"

# Verify installation
INSTALLED_NODE_VERSION=$(node -v)
echo "==> Node.js installed: $INSTALLED_NODE_VERSION"
echo "==> npm version: $(npm -v)"

# ============================================================
# astral uv (Python package/project manager)
# ============================================================
# Used for managing Python service dependencies and virtualenvs
# Pinned to installer script version for reproducibility

UV_INSTALLER_VERSION="0.5.21"
echo "==> Installing astral uv ${UV_INSTALLER_VERSION}..."
curl -LsSf "https://github.com/astral-sh/uv/releases/download/${UV_INSTALLER_VERSION}/install.sh" | sh

# Ensure uv is on PATH
export PATH="$HOME/.local/bin:$PATH"

# ============================================================
# @github/copilot CLI (AI pair programming)
# ============================================================
# Provides AI-powered terminal assistance for development

echo "==> Installing @github/copilot CLI..."
npm install -g @github/copilot

# ============================================================
# GitHub CLI (gh)
# ============================================================
# Used for PR/issue management and GitHub API operations

echo "==> Installing GitHub CLI prerequisites..."
if ! type -p wget >/dev/null; then
  sudo apt-get update
  sudo apt-get install -y wget
fi

echo "==> Downloading GitHub CLI GPG key..."
sudo mkdir -p -m 755 /etc/apt/keyrings
TEMP_FILE=$(mktemp)
wget -nv -O "$TEMP_FILE" https://cli.github.com/packages/githubcli-archive-keyring.gpg
sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg < "$TEMP_FILE" > /dev/null
sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg

echo "==> Adding GitHub CLI apt repository..."
sudo mkdir -p -m 755 /etc/apt/sources.list.d
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
  | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null

echo "==> Installing GitHub CLI..."
sudo apt-get update
sudo apt-get install -y gh

# ============================================================
# Project Dependencies
# ============================================================
# Install all project-specific dependencies for development

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# === System utilities ===
echo "==> Installing system utilities (jq, xdg-utils)..."
sudo apt-get install -y jq xdg-utils

# === Python dev tools ===
echo "==> Installing ruff (Python linter) via uv..."
uv tool install ruff

# === Project dependencies: Frontend ===
echo "==> Installing aithena-ui (frontend) npm dependencies..."
\. "$HOME/.nvm/nvm.sh"
(cd "$REPO_ROOT/src/aithena-ui" && npm install)

# === Project dependencies: Playwright E2E ===
echo "==> Installing Playwright E2E npm dependencies..."
(cd "$REPO_ROOT/e2e/playwright" && npm install)

# === Project dependencies: Python services ===
echo "==> Syncing Python service virtualenvs..."

for svc in solr-search document-indexer document-lister admin; do
  echo "    → $svc (uv sync --frozen)"
  (cd "$REPO_ROOT/src/$svc" && uv sync --frozen)
done

echo "    → embeddings-server (uv venv + pip install)"
(cd "$REPO_ROOT/src/embeddings-server" && uv venv && uv pip install -r requirements.txt)

# === Playwright browser install ===
echo "==> Installing Playwright Chromium browser + system deps..."
\. "$HOME/.nvm/nvm.sh"
(cd "$REPO_ROOT/e2e/playwright" && npx playwright install --with-deps chromium)

echo ""
echo "==> Dev environment setup complete!"
echo "    Verify: npx playwright --version"
echo "    Verify: cd src/aithena-ui && npx vitest run --reporter=dot"

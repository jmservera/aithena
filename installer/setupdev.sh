#!/usr/bin/env bash
set -euo pipefail

# This script installs Docker Engine + plugins on Ubuntu using Docker's official APT repo.

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

sudo usermod -aG docker "$USER" || true
echo "==> Added $USER to the docker group."
echo "==> IMPORTANT: Log out/in (or reboot) for group changes to take effect."
echo "==> For this session, run Docker with: sudo docker ..."

# Download and install nvm:
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.4/install.sh | bash

# in lieu of restarting the shell
\. "$HOME/.nvm/nvm.sh"

# Download and install Node.js:
nvm install 24

# Verify the Node.js version:
node -v # Should print "v24.14.0".

# Verify npm version:
npm -v # Should print "11.9.0".

curl -LsSf https://astral.sh/uv/install.sh | sh

npm install -g @github/copilot

(type -p wget >/dev/null || (sudo apt update && sudo apt install wget -y)) \
	&& sudo mkdir -p -m 755 /etc/apt/keyrings \
	&& out=$(mktemp) && wget -nv -O$out https://cli.github.com/packages/githubcli-archive-keyring.gpg \
	&& cat $out | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null \
	&& sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
	&& sudo mkdir -p -m 755 /etc/apt/sources.list.d \
	&& echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
	&& sudo apt update \
	&& sudo apt install gh -y

# ============================================================
# Development environment setup (tools + project dependencies)
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# === System utilities ===
echo "==> Installing system utilities (jq, xdg-utils)..."
sudo apt-get install -y jq xdg-utils

# === Python dev tools ===
echo "==> Installing ruff (Python linter) via uv..."
# Ensure uv is on PATH (installed above via astral.sh)
export PATH="$HOME/.local/bin:$PATH"
uv tool install ruff

# === Project dependencies: Frontend ===
echo "==> Installing aithena-ui (frontend) npm dependencies..."
# Ensure nvm/node are available
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

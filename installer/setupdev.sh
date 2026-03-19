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

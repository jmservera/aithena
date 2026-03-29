# WSL2 Installation Guide

This guide covers installing Aithena on Windows using WSL2 (Windows Subsystem for Linux). It documents both Docker Desktop and direct Docker CE approaches, along with options for storing data on a secondary disk.

## Prerequisites

- Windows 10 version 2004+ or Windows 11
- WSL2 enabled with an Ubuntu 24.04 distribution
- At least 16 GB RAM (32 GB recommended)
- SSD storage for Docker volumes (100 GB+ recommended)

## Option A: Docker Desktop (Recommended for most users)

Docker Desktop manages the WSL2 integration automatically and provides a GUI for container management.

### Installation

1. Download and install [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/).
2. During setup, ensure **Use WSL 2 based engine** is checked.
3. In Docker Desktop → Settings → Resources → WSL Integration, enable your Ubuntu distro.
4. Open your Ubuntu terminal and verify:

   ```bash
   docker --version
   docker compose version
   ```

### Volume storage location

Docker Desktop stores all container data inside a managed WSL2 virtual disk at:

```
%LOCALAPPDATA%\Docker\wsl\data\ext4.vhdx
```

To move this to a secondary disk, see [Moving Docker Desktop data](#moving-docker-desktop-data-to-a-secondary-disk) below.

## Option B: Docker CE directly in WSL2

Install Docker Engine directly inside the WSL2 Ubuntu distribution, without Docker Desktop. This gives full control but requires manual setup.

### Installation

```bash
# Remove any old packages
sudo apt-get remove docker docker-engine docker.io containerd runc 2>/dev/null

# Add Docker's official GPG key and repository
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Add your user to the docker group (log out and back in to take effect)
sudo groupadd docker 2>/dev/null || true
sudo usermod -aG docker "$USER"
newgrp docker

# Start Docker (WSL2 doesn't use systemd by default)
sudo service docker start

# Verify
docker run --rm hello-world
```

> **Tip:** To start Docker automatically when WSL opens, add `sudo service docker start` to your `~/.bashrc`, or enable systemd in `/etc/wsl.conf`:
>
> ```ini
> [boot]
> systemd=true
> ```

### Volume storage location

With Docker CE inside WSL2, container data lives in the WSL2 ext4 filesystem at `/var/lib/docker/`. To use a secondary disk, see [Secondary disk options](#secondary-disk-options) below.

## Setting up Aithena volumes

Aithena uses bind-mounted named volumes that require host directories to exist before starting. Run the provided init script:

```bash
# Default: creates directories under /source/volumes
sudo ./scripts/init-volumes.sh

# Custom path (e.g., secondary disk):
sudo VOLUMES_ROOT=/mnt/data/aithena/volumes ./scripts/init-volumes.sh
```

If using a custom `VOLUMES_ROOT`, you have two choices to make Docker Compose use it:

### Choice 1: Symlink (simple)

```bash
sudo ln -s /mnt/data/aithena/volumes /source/volumes
```

### Choice 2: Override volume paths

Create a `docker-compose.override.yml` that redefines the volume device paths. This is more explicit but requires maintaining the override file.

## Secondary disk options

### Option 1: Virtual disk (VHDX) — Best performance

Create a dedicated ext4 virtual disk and mount it inside WSL2. This avoids the 9P filesystem overhead of `/mnt/` paths.

**From PowerShell (Administrator):**

```powershell
# Create a 200 GB virtual disk on D: drive
wsl --shutdown
New-VHD -Path "D:\wsl-aithena-data.vhdx" -SizeBytes 200GB -Dynamic
```

**Mount in WSL2:**

```bash
# Identify the disk (from PowerShell: wsl --mount --vhd D:\wsl-aithena-data.vhdx --bare)
# Then inside WSL:
DISK="/dev/sdX"  # Check with lsblk after mounting
sudo mkfs.ext4 "$DISK"
sudo mkdir -p /mnt/aithena-data
sudo mount "$DISK" /mnt/aithena-data

# Set up Aithena volumes
sudo VOLUMES_ROOT=/mnt/aithena-data/volumes ./scripts/init-volumes.sh
sudo ln -s /mnt/aithena-data/volumes /source/volumes
```

> **Note:** `wsl --mount --vhd` requires Windows 11 or a recent Windows 10 insider build. For older Windows 10, use the `Attach-VHD` + `wsl --mount` approach.

**Auto-mount on WSL startup** — add to `/etc/fstab` or create a script in `/etc/wsl.conf`:

```ini
[boot]
command = mount /dev/sdX /mnt/aithena-data
```

### Option 2: Move the entire WSL distro — Simplest

Relocate the entire WSL2 Ubuntu distribution to a secondary disk. All data (including Docker) follows.

**From PowerShell (Administrator):**

```powershell
wsl --shutdown
wsl --export Ubuntu-24.04 D:\wsl-backup\ubuntu.tar
wsl --unregister Ubuntu-24.04
wsl --import Ubuntu-24.04 D:\wsl\Ubuntu-24.04 D:\wsl-backup\ubuntu.tar
```

After import, set your default user:

```bash
ubuntu2404.exe config --default-user your_username
```

### Option 3: Docker data-root — Docker CE only

Redirect Docker's storage root to a secondary disk mount point. This works only with Docker CE (not Docker Desktop).

```bash
# Mount secondary disk (ext4 formatted)
sudo mkdir -p /mnt/docker-data
sudo mount /dev/sdX1 /mnt/docker-data

# Configure Docker to use new root
sudo tee /etc/docker/daemon.json <<EOF
{
  "data-root": "/mnt/docker-data"
}
EOF

sudo service docker restart
docker info | grep "Docker Root Dir"
# Should show: /mnt/docker-data
```

### Option 4: Symlink `/mnt/d/` path — Easiest but slowest

Mount a Windows drive folder directly. This uses the 9P protocol, which is slower than native ext4.

```bash
sudo VOLUMES_ROOT=/mnt/d/aithena/volumes ./scripts/init-volumes.sh
sudo ln -s /mnt/d/aithena/volumes /source/volumes
```

> **⚠️ Performance warning:** 9P filesystem access through `/mnt/` is significantly slower than native ext4. This option is acceptable for development but **not recommended for production workloads**.

## Performance comparison

| Option | Filesystem | Performance | Complexity |
|--------|-----------|-------------|------------|
| VHDX virtual disk | ext4 (native) | ⭐⭐⭐ Best | Medium |
| Move WSL distro | ext4 (native) | ⭐⭐⭐ Best | Low |
| Docker data-root | ext4 (native) | ⭐⭐⭐ Best | Low |
| `/mnt/d/` symlink | 9P (Windows) | ⭐ Slow | Low |

## Moving Docker Desktop data to a secondary disk

Docker Desktop stores its data in a managed VHDX. To move it:

1. Open Docker Desktop → Settings → Resources → Advanced
2. Change **Disk image location** to your secondary disk path (e.g., `D:\DockerDesktop\data`)
3. Click **Apply & Restart**

Docker Desktop will move the VHDX automatically.

## Troubleshooting

### "permission denied" on volume directories

Ensure the volume directories have correct ownership:

```bash
sudo ./scripts/init-volumes.sh
```

### Docker daemon not starting in WSL2

If `sudo service docker start` fails, enable systemd:

```bash
echo -e "[boot]\nsystemd=true" | sudo tee /etc/wsl.conf
# Then restart WSL from PowerShell: wsl --shutdown
```

### Slow file I/O

If you're using `/mnt/` paths (9P), switch to a native ext4 solution (VHDX, distro move, or data-root). See [Secondary disk options](#secondary-disk-options).

### "No space left on device"

The default WSL2 virtual disk is limited to 256 GB. Expand it:

```powershell
wsl --shutdown
Resize-VHD -Path "$env:LOCALAPPDATA\...\ext4.vhdx" -SizeBytes 512GB
wsl
sudo resize2fs /dev/sda  # or appropriate device
```

# Aithena — Air-Gapped Offline Deployment Guide

This guide covers building, transferring, and deploying Aithena on a machine
with **no internet access** (air-gapped / disconnected environment).

## Overview

The offline deployment workflow has three phases:

1. **Build** — On an internet-connected machine, build all Docker images and
   create a self-contained archive.
2. **Transfer** — Move the archive to the target machine via USB drive, SCP
   over a local network, or any other physical/network transfer method.
3. **Install** — On the disconnected target, load images, configure, and
   start services.

```
┌─────────────────┐     USB / SCP     ┌─────────────────┐
│  Connected Host  │ ───────────────►  │  Target Machine  │
│  (build + export)│  .tar.gz archive  │  (load + deploy) │
└─────────────────┘                    └─────────────────┘
```

---

## Prerequisites

### Build Machine (internet-connected)

| Requirement         | Minimum          |
|---------------------|------------------|
| Docker Engine       | ≥ 24.0           |
| Docker Compose v2   | ≥ 2.20           |
| Git                 | ≥ 2.30           |
| Disk space          | 15 GB free       |
| gzip, tar           | standard install  |

### Target Machine (disconnected)

| Requirement         | Minimum          |
|---------------------|------------------|
| Docker Engine       | ≥ 24.0           |
| Docker Compose v2   | ≥ 2.20           |
| Disk space          | 20 GB free       |
| RAM                 | 16 GB minimum    |
| CPU                 | 4 cores minimum  |

> **Note:** Docker and Docker Compose must be pre-installed on the target
> machine before the offline deployment. Use `installer/setupdev.sh` on a
> connected machine, or install Docker packages from a local `.deb` mirror.

---

## Phase 1: Build the Package

On the **connected** machine, from the Aithena repository root:

```bash
# Ensure you're on the correct branch/tag
git checkout v1.11.0   # or your target version

# Build and export all images
./scripts/export-images.sh
```

### What it does

1. Resolves the version from `VERSION` file or git tag
2. Runs `docker compose build` to build all custom images
3. Pulls all official base images (Redis, RabbitMQ, Solr, ZooKeeper, nginx)
4. Exports each image as a compressed tarball (`docker save | gzip`)
5. Copies compose files, configs, and installer scripts
6. Bundles everything into `staging/aithena-offline-v{VERSION}.tar.gz`

### Options

| Flag           | Effect                                    |
|----------------|-------------------------------------------|
| `--dry-run`    | Show what would happen without executing   |
| `--skip-build` | Skip `docker compose build`; use existing images |

### Images Included

**Custom images (built from source):**
- `aithena-embeddings-server`
- `aithena-document-lister`
- `aithena-document-indexer`
- `aithena-solr-search`
- `aithena-aithena-ui`

**Official images (pulled from registries):**
- `redis:latest`
- `rabbitmq:4.0-management`
- `rediscommander/redis-commander:latest`
- `nginx:1.27-alpine`
- `zookeeper:3.9`
- `solr:9.7`

### Package Structure

```
aithena-offline-v{VERSION}/
├── images/                         # Docker images as .tar.gz
│   ├── aithena-embeddings-server_{VERSION}.tar.gz
│   ├── aithena-document-lister_{VERSION}.tar.gz
│   ├── aithena-document-indexer_{VERSION}.tar.gz
│   ├── aithena-solr-search_{VERSION}.tar.gz
│   ├── aithena-aithena-ui_{VERSION}.tar.gz
│   ├── redis_latest.tar.gz
│   ├── rabbitmq_4.0-management.tar.gz
│   ├── redis-commander_latest.tar.gz
│   ├── nginx_1.27-alpine.tar.gz
│   ├── zookeeper_3.9.tar.gz
│   └── solr_9.7.tar.gz
├── compose/
│   ├── docker-compose.yml          # Base compose definition
│   ├── docker-compose.prod.yml     # Production overrides
│   └── .env.example                # Environment template
├── config/
│   ├── solr/                       # Solr configsets (books schema)
│   ├── nginx/                      # nginx reverse proxy config
│   └── rabbitmq/                   # RabbitMQ config
├── install.sh                      # Offline installer script
├── verify.sh                       # Post-install health check
├── VERSION                         # Version identifier
└── README.md                       # Quick-start guide
```

---

## Phase 2: Transfer the Package

The archive is a single `.tar.gz` file. Transfer it to the target machine
using any available method:

### USB Drive

```bash
# On the build machine
cp staging/aithena-offline-v1.11.0.tar.gz /mnt/usb/

# On the target machine
cp /mnt/usb/aithena-offline-v1.11.0.tar.gz /tmp/
```

### SCP (if local network is available)

```bash
scp staging/aithena-offline-v1.11.0.tar.gz user@target:/tmp/
```

### Split for Size Constraints

If the archive is too large for your transfer medium:

```bash
# Split into 2 GB chunks
split -b 2G staging/aithena-offline-v1.11.0.tar.gz aithena-part-

# On the target, reassemble
cat aithena-part-* > aithena-offline-v1.11.0.tar.gz
```

---

## Phase 3: Install on the Target Machine

### Extract the Package

```bash
cd /tmp   # or wherever you transferred the archive
tar xzf aithena-offline-v1.11.0.tar.gz
cd aithena-offline-v1.11.0/
```

### Run the Installer

```bash
sudo ./install.sh
```

### What the installer does

1. **Validates prerequisites** — Docker version, Compose plugin, disk space
2. **Loads Docker images** — `docker load` from each `.tar.gz`
3. **Copies files** — Compose files and configs to `/opt/aithena/`
4. **Generates `.env`** — Creates config from template with random secrets
5. **Creates directories** — Volume bind-mount paths with correct ownership
6. **Starts services** — `docker compose up -d`
7. **Health check** — Waits for nginx to respond

### Installer Options

| Flag                  | Effect                                      |
|-----------------------|---------------------------------------------|
| `--dry-run`           | Show what would happen without executing     |
| `--skip-load`         | Skip image loading (already loaded)          |
| `--install-dir DIR`   | Custom install path (default: `/opt/aithena`)|

### Post-Install Configuration

After installation, review and edit `/opt/aithena/.env`:

```bash
sudo nano /opt/aithena/.env
```

Key settings to adjust:

| Variable       | Description                        | Default              |
|----------------|------------------------------------|----------------------|
| `BOOKS_PATH`   | Path to your book/document library | `/data/booklibrary`  |
| `PUBLIC_ORIGIN` | Server URL (for CORS)             | `http://localhost`   |
| `AUTH_DB_DIR`  | Auth database directory            | `/opt/aithena/data/auth` |

After editing, restart services:

```bash
cd /opt/aithena
sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml restart
```

---

## Phase 4: Verify the Deployment

```bash
./verify.sh
```

Or from the install directory:

```bash
/tmp/aithena-offline-v1.11.0/verify.sh --install-dir /opt/aithena
```

The verification script checks:

| Check                  | What it verifies                       |
|------------------------|----------------------------------------|
| Docker daemon          | Docker is running                      |
| Container status       | All 15+ containers are healthy         |
| nginx gateway          | `GET /health` returns 200              |
| solr-search API        | `GET /v1/health` returns 200           |
| Version endpoint       | `GET /v1/version` responds             |
| Frontend               | `GET /` serves the UI                  |
| Internal connectivity  | embeddings-server, solr reachable internally |

All checks green? Access Aithena at `http://<server-ip>/`.

---

## Updating an Existing Installation

To update a running offline deployment:

1. **On the connected machine:** Check out the new version and rebuild:
   ```bash
   git checkout v1.12.0
   ./scripts/export-images.sh
   ```

2. **Transfer** the new archive to the target machine.

3. **On the target machine:**
   ```bash
   # Stop current services
   cd /opt/aithena
   sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml down

   # Extract new package
   cd /tmp
   tar xzf aithena-offline-v1.12.0.tar.gz
   cd aithena-offline-v1.12.0/

   # Install (preserves existing .env)
   sudo ./install.sh --install-dir /opt/aithena

   # Verify
   ./verify.sh
   ```

> **Important:** The installer preserves your existing `.env` file. It will
> NOT overwrite your secrets or custom paths. If new environment variables
> were added in the update, check the changelog and add them manually.

---

## Troubleshooting

### Images fail to load

```
Error processing tar file: ... no space left on device
```

**Cause:** Insufficient disk space for Docker image storage.

**Fix:** Free up space or expand the Docker storage partition:
```bash
docker system prune -af   # Remove unused images/containers
df -h /var/lib/docker     # Check Docker storage
```

### Services fail to start

```bash
# Check which services are down
cd /opt/aithena
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps

# View logs for a specific service
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs solr-search

# View all logs
docker compose -f docker-compose.yml -f docker-compose.prod.yml logs --tail 50
```

### Permission errors on bind-mount directories

```
Error: permission denied: /source/volumes/solr-data
```

**Cause:** Bind-mount directories don't have the correct UID.

**Fix:** Re-run the installer or fix ownership manually:
```bash
sudo chown 8983:8983 /source/volumes/solr-data
sudo chown 8983:8983 /source/volumes/solr-data2
sudo chown 8983:8983 /source/volumes/solr-data3
sudo chown 999:999   /source/volumes/redis
sudo chown 100:100   /source/volumes/rabbitmq-data
```

### Health check fails for embeddings-server

The embeddings server takes 60-120 seconds to start because it loads the ML
model into memory at boot. Wait and re-run `./verify.sh --wait 120`.

### RabbitMQ credentials not applied

RabbitMQ credentials are only applied on first Mnesia database creation.
If you see authentication failures after changing `RABBITMQ_USER` or
`RABBITMQ_PASS`:

```bash
# Remove the old data
sudo rm -rf /source/volumes/rabbitmq-data/*
# Restart RabbitMQ
docker compose restart rabbitmq
```

### Cannot connect to Aithena from another machine

1. Check the server firewall allows port 80 (and 443 if using SSL):
   ```bash
   sudo ufw allow 80/tcp
   ```

2. Ensure `PUBLIC_ORIGIN` in `.env` matches the server's address:
   ```
   PUBLIC_ORIGIN=http://192.168.1.100
   CORS_ORIGINS=http://192.168.1.100
   ```

3. Restart nginx after changing origins:
   ```bash
   docker compose restart nginx
   ```

---

## Architecture Reference

### Service Map

```
                              ┌─────────────┐
                              │    nginx     │ :80
                              │  (gateway)   │
                              └──────┬───────┘
                    ┌────────────┬───┴────┬──────────────┐
                    │            │        │              │
              ┌─────┴─────┐ ┌───┴───┐ ┌──┴───┐   ┌─────┴──────┐
              │ aithena-ui │ │ solr- │ │ Solr │   │ redis-     │
              │  (React)   │ │search │ │ Admin│   │ commander  │
              └────────────┘ │ (API) │ └──────┘   └────────────┘
                             └───┬───┘
                    ┌────────┬───┴────┬──────────┐
                    │        │        │          │
              ┌─────┴─┐ ┌───┴───┐ ┌──┴───┐ ┌───┴────┐
              │ Redis  │ │Rabbit │ │ Solr │ │embeddings│
              │        │ │  MQ   │ │Cloud │ │ server   │
              └────────┘ └───┬───┘ │(3×)  │ └──────────┘
                             │     └──┬───┘
                        ┌────┴────┐   │
                        │document-│   │
                        │indexer  ├───┘
                        └────┬────┘
                        ┌────┴────┐
                        │document-│
                        │lister   │
                        └─────────┘
```

### Resource Requirements

| Service           | Memory Limit | Instances |
|-------------------|-------------|-----------|
| Solr nodes        | 2 GB each   | 3         |
| ZooKeeper nodes   | 512 MB each | 3         |
| embeddings-server | 2 GB        | 1         |
| RabbitMQ          | 1 GB        | 1         |
| solr-search       | 512 MB      | 1         |
| Redis             | 512 MB      | 1         |
| document-indexer  | 512 MB      | 1         |
| aithena-ui        | 256 MB      | 1         |
| document-lister   | 256 MB      | 1         |
| redis-commander   | 256 MB      | 1         |
| nginx             | 256 MB      | 1         |
| **Total**         | **~13 GB**  | **16**    |

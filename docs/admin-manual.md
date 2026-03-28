# Admin Manual

This manual covers deployment, configuration, monitoring, and troubleshooting for Aithena. If you are looking for end-user instructions, start with the [User Manual](user-manual.md). For the latest release features, see the [v1.17.1 Release Notes](release-notes/v1.17.1.md).

**v1.15.0 / v1.16.0 / v1.17.0 / v1.17.1 operator note:** v1.15.0 includes admin portal enhancements (sidebar navigation, per-service log viewer, Solr SSO passthrough), critical bug fixes (document indexer OOM on large PDFs, thumbnail write failures), build-time dependency installation, and volume permission hardening. v1.16.0 adds search UI bug fixes, similar-books endpoint fix, admin dashboard pagination, nginx thumbnail routing fix, RabbitMQ deprecation warning fix, CI smoke test timeout fix, and a new pre-release container workflow. v1.17.0 introduces GPU acceleration for embeddings (opt-in via environment variables), security dependency updates (`requests`, `picomatch`), and comprehensive GPU documentation. v1.17.1 hardens GitHub Actions CI secrets behind a dedicated environment; no deployment changes. See the [v1.15.0 Deployment Updates](#deployment-updates-for-v1150), [v1.16.0 Deployment Updates](#deployment-updates-for-v1160), [v1.17.0 Deployment Updates](#deployment-updates-for-v1170), and [v1.17.1 Deployment Updates](#deployment-updates-for-v1171) sections below.

## System architecture overview

Aithena runs as a Docker Compose stack built around Solr, a document ingestion pipeline, and a React web UI.

### Core services

| Service | Purpose | Default access |
|---|---|---|
| `nginx` | Main reverse proxy and public entry point | `80`, `443` |
| `aithena-ui` | User-facing React frontend | proxied through `nginx` |
| `solr-search` | FastAPI search, status, stats, and document endpoints | proxied through `nginx`; direct `8080` via override |
| `solr`, `solr2`, `solr3` | SolrCloud search nodes | proxied admin through `nginx`; direct `8983`-`8985` via override |
| `solr-init` | One-shot collection/config bootstrap for `books` | internal only |
| `zoo1`, `zoo2`, `zoo3` | ZooKeeper ensemble for SolrCloud | internal only; direct `18080`, `2181`-`2183` via override |
| `redis` | Indexing state tracking | internal only; direct `6379` via override |
| `rabbitmq` | Queue for document ingestion | internal AMQP; admin proxied through `nginx`; direct `5672`, `15672` via override |
| `document-lister` | Scans the mounted library and enqueues PDFs | internal only |
| `document-indexer` | Consumes queue items and indexes books into Solr | internal only |
| `embeddings-server` | Embedding service used by the search stack | internal only; direct `8085` via override |
| `redis-commander` | Web UI for Redis inspection | proxied through `nginx`; direct `8081` via override |
| `certbot` | Certificate renewal helper (optional — see `docker-compose.ssl.yml`) | internal only |

### Service dependencies

At a high level:

1. `document-lister` scans the mounted book library.
2. New or changed PDFs are pushed into RabbitMQ.
3. `document-indexer` consumes queue messages and writes metadata plus extracted content into Solr.
4. `solr-search` serves search results, PDF document links, status, and stats.
5. `aithena-ui` and `nginx` present the user-facing application.

### Pipeline dependency ordering (v0.5.0)

The v0.5.0 Compose update tightens startup ordering so pipeline services wait for healthy dependencies instead of merely started containers.

Current shipped behavior:

- `document-lister` waits for **RabbitMQ** and **Redis** with `condition: service_healthy`
- `document-indexer` waits for **RabbitMQ** and **Redis** with `condition: service_healthy`
- `redis-commander` waits for **Redis** health
- `nginx` also waits for **RabbitMQ** health before exposing the admin surfaces

This reduces startup races where the lister, indexer, or admin tools could come up before the queue or cache was actually ready.

## Deployment with Docker Compose

### 1. Choose the host library path

The stack mounts the library through the `document-data` volume. The host path is controlled by:

- `BOOKS_PATH`

If `BOOKS_PATH` is not set, Docker Compose falls back to:

- `/data/booklibrary`

Example:

```bash
export BOOKS_PATH=/absolute/path/to/your/booklibrary
```

### 2. Run the installer (v0.11.0+)

Before starting the stack, bootstrap the runtime configuration and auth storage:

```bash
python3 -m installer
# or: python3 installer/setup.py --library-path /absolute/path/to/books \
#       --admin-user admin --admin-password 'change-me' --origin http://localhost
```

The installer writes `.env`, creates the host auth directory used by Docker Compose, generates the JWT secret, and seeds the initial admin account. Re-run it whenever you need to rotate credentials or rebuild auth storage.

### 3. Start the stack

```bash
docker compose up -d
```

This starts the full stack, including SolrCloud, Redis, RabbitMQ, the indexing services, the search API, and the UI. In the default local workflow, Docker Compose also auto-loads `docker-compose.override.yml`, which republishes debug ports for direct host access.

For a production-style run with only the nginx gateway exposed on the host, use:

```bash
docker compose -f docker-compose.yml up -d
```

### 4. Watch initial bootstrap

The `solr-init` container waits for all three Solr nodes, uploads the `books` configset, creates the `books` collection if needed, and applies the config overlay.

Useful checks:

```bash
docker compose ps
docker compose logs -f solr-init
```

### 5. Open the service endpoints

Common local URLs:

| Surface | URL | Access |
|---|---|---|
| Main UI | `http://localhost/` | Protected — redirects to `/login` until authenticated |
| Login page | `http://localhost/login` | Public |
| Search API | `http://localhost/v1/search/` | Protected |
| Status API | `http://localhost/v1/status/` | Protected |
| Stats API | `http://localhost/v1/stats/` | Protected |
| Solr admin | `http://localhost/admin/solr/` | Protected |
| RabbitMQ management | `http://localhost/admin/rabbitmq/` | Protected |
| Redis Commander | `http://localhost/admin/redis/` | Protected |

Health, info, version, and auth bootstrap endpoints remain available for operational checks and login flows. Direct host ports (`8080`, `8983`-`8985`, `15672`, `6379`, `2181`-`2183`, `18080`, `8081`, `8085`) are available only when the local `docker-compose.override.yml` file is loaded.

## GPU Acceleration Setup (v1.17.0)

GPU acceleration is opt-in and requires host-level driver installation before Docker can access GPU hardware. This section covers prerequisites, installation, and verification for both NVIDIA and Intel GPUs.

### Architecture

The `embeddings-server` container accepts two environment variables:

| Variable | Values | Default | Purpose |
|----------|--------|---------|---------|
| `DEVICE` | `auto`, `cpu`, `cuda`, `xpu` | `cpu` | PyTorch device selection |
| `BACKEND` | `torch`, `openvino` | `torch` | Inference backend |

GPU acceleration is activated via Docker Compose override files that:
1. Set the correct `DEVICE` and `BACKEND` environment variables
2. Pass through the GPU device to the container

### NVIDIA GPU Setup

#### Prerequisites
- NVIDIA GPU with CUDA Compute Capability 5.0+ (GeForce GTX 900 series or newer)
- NVIDIA driver 525.60.13+ (Linux) or 528.33+ (Windows)
- Docker Engine 19.03+ with GPU support

#### Install NVIDIA Container Toolkit

**Ubuntu/Debian:**
```bash
# Add NVIDIA package repository
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
  sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

#### Verify NVIDIA setup
```bash
# Host GPU check
nvidia-smi

# Docker GPU passthrough check
docker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu22.04 nvidia-smi
```

#### Start with NVIDIA
```bash
docker compose -f docker-compose.yml -f docker-compose.nvidia.override.yml up -d
```

### Intel GPU Setup

#### Prerequisites
- Intel GPU with OpenCL/Level Zero support (Arc A-series, Iris Xe, or integrated GPU with Gen12+)
- Intel compute-runtime drivers
- `/dev/dxg` device accessible

#### Install Intel compute-runtime

**Ubuntu/Debian:**
```bash
# Add Intel package repository
wget -qO - https://repositories.intel.com/gpu/intel-graphics.key | \
  sudo gpg --dearmor -o /usr/share/keyrings/intel-graphics.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/intel-graphics.gpg] \
  https://repositories.intel.com/gpu/ubuntu jammy unified" | \
  sudo tee /etc/apt/sources.list.d/intel-gpu.list

sudo apt-get update
sudo apt-get install -y intel-opencl-icd intel-level-zero-gpu
```

#### Verify Intel setup
```bash
# Check /dev/dxg exists
ls -la /dev/dxg/

# Check Intel GPU is recognized
sudo apt-get install -y clinfo
clinfo | head -20
```

#### Start with Intel
```bash
docker compose -f docker-compose.yml -f docker-compose.intel.override.yml up -d
```

### WSL2 GPU Passthrough (Windows)

Many users run Aithena on Windows via WSL2. GPU passthrough works for both NVIDIA and Intel GPUs.

#### NVIDIA on WSL2
1. Install latest NVIDIA Game Ready or Studio drivers on **Windows** (not inside WSL)
2. WSL2 automatically exposes `/dev/dxg` for GPU access
3. Install NVIDIA Container Toolkit inside WSL (same steps as Ubuntu above)
4. Docker Desktop WSL2 backend automatically supports `--gpus`

#### Intel on WSL2

For comprehensive setup, prerequisites, and troubleshooting specific to Intel GPUs on WSL2, see the [Intel GPU WSL2 Setup Guide](guides/intel-gpu-wsl2.md).

Quick reference:
1. Install latest Intel GPU drivers on **Windows** (v30.0.100.9684+)
2. Run `wsl --update` to ensure latest WSL2 kernel
3. Inside WSL, add Intel GPU repositories and install runtime packages
4. Verify: `clinfo | head -20` should show your Intel GPU
5. Use the Intel override: `docker compose -f docker-compose.prod.yml -f docker-compose.intel.override.yml up -d`

### Verification

After starting with a GPU override, check the embeddings-server health endpoint:

```bash
curl -s http://localhost:8080/health | python3 -m json.tool
```

Expected output with GPU:
```json
{
    "status": "healthy",
    "model": "intfloat/multilingual-e5-base",
    "embedding_dim": 768,
    "device": "cuda",
    "backend": "torch"
}
```

### Troubleshooting Quick Reference

| Symptom | Cause | Fix |
|---------|-------|-----|
| `CUDA not available` in logs | NVIDIA drivers not installed or toolkit missing | Install NVIDIA Container Toolkit |
| `xpu device not found` | Intel compute-runtime missing | Install intel-opencl-icd |
| Health shows `device: cpu` despite override | Override file not loaded | Check `docker compose config` output |
| Container crash on startup | GPU memory insufficient | Try `DEVICE=cpu` to verify, then check GPU memory |
| `/dev/dxg` not found in WSL2 | GPU drivers not installed on Windows host | Install Windows GPU drivers, restart WSL |

### Windows Users: Intel GPU on WSL2

If you're running Aithena on Windows with Intel GPU acceleration in WSL2, see the dedicated [Intel GPU WSL2 Setup Guide](guides/intel-gpu-wsl2.md). This guide covers:

- Prerequisites (Windows 11, WSL2 kernel updates, Intel driver requirements)
- Step-by-step driver and repository setup
- GPU verification and container startup
- WSL2-specific troubleshooting (DirectX vs. DRM device differences)
- Performance tuning and monitoring

The guide includes a quick-start command and detailed explanations of WSL2's GPU architecture, making it ideal for first-time users.

## Backup dashboard and restore workflow (v1.14.x)

The current UI includes an admin-only backup dashboard at:

- `/admin/backups`

This route is wired through the React application and exposes a dedicated operator workflow for backup visibility and restore actions.

### What the dashboard provides

The page renders three main surfaces:

1. **Tier status** — a quick view of backup tier health/state
2. **Backup now controls** — on-demand backup triggers from the UI
3. **Backup history** — a table of known backups with restore entry points

When you choose **Restore**, the UI opens a modal restore wizard with these steps:

- `select`
- `preview`
- `confirm`
- `progress`

The page logic supports both a direct restore action and a test-restore action. Treat both as privileged operational tools and validate them in staging before relying on them in production runbooks.

### Recommended operator practice

- Verify backup history loads before starting maintenance windows
- Prefer test-restore on non-production environments when available
- Use the preview/confirm steps to verify you selected the correct backup set
- Monitor restore progress and application health before reopening the system to users

## Configuration

### Host-mounted volume

`docker-compose.yml` defines the document library volume like this:

- volume name: `document-data`
- container path: `/data/documents`
- host path: `${BOOKS_PATH:-/data/booklibrary}`

That means every service using `/data/documents` is reading from the same mounted library root.

### Key environment variables by service

#### `document-lister`

| Variable | Value in Compose | Purpose |
|---|---|---|
| `RABBITMQ_HOST` | `rabbitmq` | RabbitMQ hostname |
| `REDIS_HOST` | `redis` | Redis hostname |
| `QUEUE_NAME` | `shortembeddings` | Queue/routing key for discovered documents |
| `BASE_PATH` | `/data/documents/` | Directory scanned inside the container |
| `DOCUMENT_WILDCARD` | `*.pdf` | File pattern to scan |
| `POLL_INTERVAL` | `60` | Seconds between scans |

#### `document-indexer`

| Variable | Value in Compose | Purpose |
|---|---|---|
| `RABBITMQ_HOST` | `rabbitmq` | RabbitMQ hostname |
| `REDIS_HOST` | `redis` | Redis hostname |
| `QUEUE_NAME` | `shortembeddings` | Queue consumed by the indexer |
| `BASE_PATH` | `/data/documents/` | Root path for source documents |
| `SOLR_HOST` | `solr` | Primary Solr hostname |
| `SOLR_PORT` | `8983` | Primary Solr port |
| `SOLR_COLLECTION` | `books` | Target collection |
| `EMBEDDINGS_HOST` | `embeddings-server` | Embeddings service hostname |
| `EMBEDDINGS_PORT` | `8085` | Embeddings service port |
| `THUMBNAIL_DIR` | `/data/thumbnails` | Writable directory for generated document thumbnails (v1.15.0+) |

#### `solr-search`

| Variable | Value in Compose | Purpose |
|---|---|---|
| `PORT` | `8080` | API listen port |
| `SOLR_URL` | `http://solr:8983/solr` | Base Solr URL |
| `SOLR_COLLECTION` | `books` | Collection used for search |
| `BASE_PATH` | `/data/documents` | Base path for document downloads |
| `CORS_ORIGINS` | `http://localhost:5173` | Allowed dev origin |
| `EMBEDDINGS_URL` | `http://embeddings-server:8001/v1/embeddings/` | Embeddings endpoint |
| `EMBEDDINGS_TIMEOUT` | `120` | Max wait for query embeddings before semantic/hybrid degrade to keyword |
| `DEFAULT_SEARCH_MODE` | `keyword` | Default API search mode |
| `RRF_K` | `60` | Reciprocal-rank fusion damping constant for hybrid ranking |
| `KNN_FIELD` | `book_embedding` | Dense-vector field used by the semantic/hybrid kNN leg |
| `UPLOAD_MAX_SIZE_MB` | `50` | Maximum upload file size (v0.6.0+) |
| `UPLOAD_RATE_LIMIT` | `10` | Uploads per minute per IP (v0.6.0+) |
| `UPLOAD_STAGING_DIR` | `/data/uploads/` | Temporary upload staging area (v0.6.0+) |
| `EXPOSE_CONTAINER_STATS` | `false` | Enable `/v1/admin/containers` endpoint (v0.7.0+) |
| `AUTH_DB_PATH` | `/data/auth/users.db` | SQLite auth database path inside the container (v0.11.0+) |
| `AUTH_JWT_SECRET` | installer-generated | JWT signing secret required at startup (v0.11.0+) |
| `AUTH_JWT_TTL` | `24h` | Session lifetime for issued JWTs (v0.11.0+) |
| `AUTH_COOKIE_NAME` | `aithena_auth` | Cookie name used for browser auth (v0.11.0+) |

#### Infrastructure services

- `rabbitmq` sets `RABBITMQ_SERVER_ADDITIONAL_ERL_ARGS=-rabbit consumer_timeout 3600000000`
- `embeddings-server` sets `PORT=8085`
- Solr nodes set `SOLR_MODULES=extraction,langid` and `ZK_HOST=zoo1:2181,zoo2:2181,zoo3:2181`
- ZooKeeper nodes set `ZOO_4LW_COMMANDS_WHITELIST`, `ZOO_MY_ID`, and `ZOO_SERVERS`

### RabbitMQ startup hardening (v0.5.0)

The Compose definition now pins RabbitMQ to:

- `rabbitmq:3.13-management`

It also adds a more realistic health check:

- command: `rabbitmqctl ping`
- `interval: 10s`
- `timeout: 30s`
- `retries: 12`
- `start_period: 30s`

Additional runtime settings now include:

- `RABBITMQ_VM_MEMORY_HIGH_WATERMARK=0.6`
- `RABBITMQ_SERVER_ADDITIONAL_ERL_ARGS=-rabbit consumer_timeout 3600000000`

Operationally, this means RabbitMQ is given time to finish booting before Compose marks it unhealthy, and dependent services can safely rely on `service_healthy` ordering.

### Search mode and hybrid tuning

`solr-search` supports three request modes:

- `keyword` — BM25 / edismax only
- `semantic` — embeddings + Solr kNN only
- `hybrid` — BM25 plus kNN, merged with Reciprocal Rank Fusion (RRF)

Operators can tune the search path with these controls:

- `DEFAULT_SEARCH_MODE` sets the API default when clients do not pass a `mode` query parameter.
- Clients can switch modes per request with `GET /v1/search?mode=keyword|semantic|hybrid`.
- `RRF_K` controls how aggressively hybrid mode favors top-ranked documents from each leg.
- `KNN_FIELD` selects the Solr dense-vector field used by semantic and hybrid search.
- `EMBEDDINGS_TIMEOUT` controls how long semantic/hybrid requests wait before falling back to keyword results.

Hybrid currently uses equal contribution from the BM25 and semantic legs through standard RRF. There are no separate per-leg weight environment variables today.

### Language detection (v0.5.0)

Language metadata now comes from two coordinated sources:

1. **Solr langid** writes content-based detection into `language_detected_s`.
2. **document-indexer** inspects folder names and writes recognized ISO 639-1 language folders into `language_s`.

Examples of recognized top-level folders include `ca`, `es`, `fr`, `en`, and `la`.

Why this matters:

- prior to the fix, Solr's langid processor was aligned to the wrong field name,
- folder-based language hints were not being captured at all,
- the search API now reads language values with a `language_detected_s` first / `language_s` fallback for filters and normalized results.

This improves language facets and search filters for libraries organized as `<language>/<category>/<author>/file.pdf`.

## Deployment Updates for v0.6.0 (PDF Upload, Security Scanning, Docker Hardening)

### Docker Health Checks

v0.6.0 adds health checks to all services in `docker-compose.yml`. Services now verify they are:

1. Running
2. Ready to accept connections
3. Responsive to queries

**Example (Redis):**
```yaml
redis:
  healthcheck:
    test: ["CMD", "redis-cli", "ping"]
    interval: 5s
    timeout: 15s
    retries: 1
  restart: unless-stopped
```

**Key changes:**

- Services that depend on others now use `condition: service_healthy` instead of just `service_started`
- This prevents race conditions where the indexer or admin tools come up before their dependencies are actually ready

### Resource Limits and Restart Policies

v0.6.0 enforces memory and CPU limits on all services to prevent resource exhaustion:

| Service | Memory Limit | Restart Policy |
|---------|--------------|-----------------|
| Redis | 512 MB | `unless-stopped` |
| RabbitMQ | 2 GB | `unless-stopped` |
| Solr nodes | 2 GB each | `unless-stopped` |
| Embeddings Server | 2 GB | `unless-stopped` |
| Solr Search API | 512 MB | `unless-stopped` |
| Document Indexer | 512 MB | `on-failure` |
| Document Lister | 512 MB | `on-failure` |

**Restart policies explained:**

- `restart: unless-stopped` — automatically restart unless explicitly stopped by user
- `restart: on-failure` — only restart if the container exits with a non-zero code
- `stop_grace_period` — allows graceful shutdown before forced termination

### Security Scanning

v0.6.0 adds continuous security scanning to the CI/CD pipeline:

- **Bandit** scans Python code for security vulnerabilities
- **Checkov** scans Infrastructure-as-Code (Docker Compose, deployment files)
- **Zizmor** scans GitHub Actions workflows for security issues

All scans run on every push to any branch. Results are available in GitHub Actions workflow logs.

**To review findings:**

```bash
# Check the latest Bandit scan
gh run view --log bandit 2>/dev/null | grep -A 20 "security"

# Check Checkov results for docker-compose
gh run view --log checkov 2>/dev/null | grep -i "docker-compose"
```

See `docs/security/baseline-v0.6.0.md` for the complete security findings triage (287 items catalogued).

## Deployment Updates for v0.7.0 (Versioning, Admin Observability, Release Automation)

### Semantic Versioning Infrastructure

v0.7.0 adds version tracking across all services:

- **VERSION file** in project root is the single source of truth
- Each service reads version from git tags (development) or container image labels (production)
- `docker-compose.yml` includes version in Dockerfile labels

**To check the current version:**

```bash
cat VERSION
echo "Current tag: v$(cat VERSION)"
```

**To verify all services report the same version:**

```bash
# Version endpoint on solr-search
curl -s http://localhost:8080/version | jq '.version'

# In Streamlit admin dashboard
# Navigate to System Status > Versions tab
```

### Version Endpoints (GET /version)

v0.7.0 adds `/version` endpoints to all services. Use these for monitoring and health checks:

```bash
# Get version info from solr-search
curl -s http://localhost:8080/version | jq '.'
```

**Response format:**
```json
{
  "service": "solr-search",
  "version": "0.7.0",
  "build_time": "2026-03-15T14:30:00Z",
  "git_commit": "a1b2c3d4",
  "git_branch": "main",
  "python_version": "3.11.7"
}
```

### Container Stats Endpoint (GET /v1/admin/containers)

v0.7.0 adds an endpoint for querying Docker container metadata without needing direct Docker socket access:

```bash
# Get container stats (requires EXPOSE_CONTAINER_STATS=true)
curl -s http://localhost:8080/v1/admin/containers | jq '.containers[] | "\(.name) - \(.state) (\(.cpu_percent)% CPU, \(.memory_mb)MB)"'
```

**Security note:** This endpoint is **disabled by default**. To enable it, set the environment variable:

```bash
export EXPOSE_CONTAINER_STATS=true
docker-compose up
```

### System Status Admin Page

v0.7.0 adds a new **System Status** page in the admin dashboard (Streamlit app):

**Navigation:**

1. Open the **Admin** tab in Aithena
2. Navigate to **System Status** (if not visible, ensure v0.7.0 is deployed)
3. Tabs available:
   - **Versions** — version matrix and update history for all services
   - **Health** — health check statuses and history
   - **Resources** — CPU and memory usage graphs
   - **Logs** — recent system events and state changes

![System status page](images/status-tab.png)

- Polls `/version` and `/admin/containers` every 30 seconds
- Changes highlighted in green (improvement) or red (degradation)
- Can be paused for detailed inspection

**To troubleshoot the System Status page:**

```bash
# Verify version endpoints are responsive
curl -s http://localhost:8080/version | jq '.version'

# Verify container stats endpoint is responsive (if enabled)
export EXPOSE_CONTAINER_STATS=true
curl -s http://localhost:8080/v1/admin/containers | jq '.containers | length'
```

### Version Display in User Interface

v0.7.0 adds version display in the footer of the web app:

- Shows **Aithena v0.7.0** (or current version) in bottom-right corner
- Hover tooltip reveals full version metadata (commit hash, build time)
- Gracefully displays "unknown" if version endpoint is unavailable

### Monitoring Version Consistency

Use the System Status page to detect version skew (services at different versions):

**Workflow:**

1. After a deploy, open the **Versions** tab in System Status
2. Confirm all services are at v0.7.0 (or your target version)
3. If any service is at an older version, wait for it to restart or check deployment logs
4. Set up a monitoring alert: alert if any service version differs from the others

**Manual check:**

```bash
for service in solr-search document-indexer document-lister embeddings-server; do
  echo -n "$service: "
  # Requires knowledge of each service's version endpoint and port
done
```

### Release Automation

v0.7.0 includes a CI/CD workflow (`.github/workflows/release.yml`) that automates versioned releases:

**Trigger:** Merge to `main` branch (or manual trigger)

**What it does:**

1. Determines new version using conventional commits
2. Updates `VERSION` file
3. Updates `CHANGELOG.md` from commit messages
4. Creates git tag (e.g., `v0.7.0`)
5. Builds and tags container images (`:v0.7.0`, `:latest`)
6. Creates GitHub Release with changelog

**Supported pre-release tags:**

- `v0.7.0-rc1` (release candidate)
- `v0.7.0-beta` (beta)
- `v0.7.0-alpha` (alpha)

**Pre-release (RC) testing:**

Before creating a final release, you can build and test release candidate images using the pre-release workflow. This lets you validate RC images locally with `docker-compose.prod.yml` before merging to `main`. See the [Pre-Release Testing](pre-release-testing.md) guide for the full workflow, including how to trigger RC builds, pull images, and run the validation checklist.

**To test locally:**

```bash
# Check if release workflow would trigger
git log --oneline -5 | head -3

# Check current version
cat VERSION
```

## Deployment Updates for v0.12.0 (Metrics, Credential Rotation, Resilience)

### `/v1/metrics` and monitoring setup

`solr-search` now exposes Prometheus-compatible metrics at `/v1/metrics`. Because the public nginx surface protects `/v1/*`, operators should normally scrape the internal service target (`solr-search:8080`) or another private/authenticated path rather than relying on the public URL.

Current metrics cover:

- request volume by search mode (`keyword`, `semantic`, `hybrid`)
- search latency histograms
- indexing queue depth and failure counters
- embeddings availability
- Solr live-node count

For a ready-to-use scrape example and starter alert thresholds, see the dedicated [Monitoring guide](guides/monitoring.md).

### Credential rotation procedure

The v0.12.0 deployment path assumes operator-managed credential rotation for the auth bootstrap user, JWT secret, and RabbitMQ credentials.

Preferred workflow:

1. Re-run the installer:
   ```bash
   python3 -m installer
   python3 -m installer --reset  # when you need to rebuild auth storage and rotate generated secrets
   ```
2. If you manage service credentials manually, update `.env` with strong replacements for `RABBITMQ_USER` and `RABBITMQ_PASS`.
3. Recreate every dependent service so clients reconnect with the new credentials:
   ```bash
   docker compose up -d --force-recreate rabbitmq document-lister document-indexer solr-search nginx
   ```

The full production procedure and recovery notes are documented in the [Production deployment guide](deployment/production.md).

### Password reset

The `reset_password.py` CLI tool lets administrators reset any user's password without restarting the service or deleting the database.

#### Usage

```bash
# Inside the solr-search container (recommended for production)
docker compose exec solr-search python reset_password.py

# With a specific password
docker compose exec solr-search python reset_password.py --password "new-secure-password"

# For a specific user
docker compose exec solr-search python reset_password.py --username myuser --password "new-pass"
```

#### On the host (development)

If the auth database is bind-mounted to the host:

```bash
cd src/solr-search
uv run python reset_password.py --db-path ~/.local/share/aithena/auth/users.db
```

#### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--db-path` | From `AUTH_DB_PATH` env or `/data/auth/users.db` | Path to the SQLite auth database |
| `--username` | `admin` | User account to reset |
| `--password` | *(auto-generated)* | New password. If omitted, generates a secure 32-character random password |

#### Behavior

- If `--password` is omitted, the tool generates a secure random password and prints it to stdout
- Status messages go to stderr, so you can pipe the password: `docker compose exec solr-search python reset_password.py | clip`
- Passwords are hashed with Argon2 (same algorithm as the login flow)
- The tool validates the database exists and the user is found before making changes

#### First-time setup

If the auth database is empty (e.g., after a fresh install or volume recreation), you can create the initial admin user:

```bash
docker compose exec solr-search python -c "
from auth import init_auth_db, hash_password
from pathlib import Path
import sqlite3
init_auth_db(Path('/data/auth/users.db'))
conn = sqlite3.connect('/data/auth/users.db')
conn.execute('INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)',
    ('admin', hash_password('your-password'), 'admin'))
conn.commit()
"
```

Or use the installer: `python3 -m installer --reset`

### Degraded-mode semantic search behavior

When Solr is healthy but the embeddings service is unavailable, semantic and hybrid requests no longer fail closed. Instead, `solr-search` automatically reruns the request in keyword mode and returns a normal search payload with extra metadata describing the degradation:

- `degraded: true`
- `message: "Embeddings unavailable — showing keyword results"`
- `requested_mode: "semantic"` or `"hybrid"`
- `mode: "keyword"` to show the effective execution path

Operationally, this keeps the UI and API available during embeddings outages. It does **not** replace Solr failover; if Solr is down, all search modes still fail.

### Failover runbook and drill reference

v0.12.0 adds an operator runbook for outage handling across Solr, Redis, RabbitMQ, embeddings-server, and nginx.

Use these artifacts together:

- [Failover & Recovery Runbook](deployment/failover-runbook.md)
- `e2e/failover-drill.sh` for rehearsal in a Docker-capable environment

The runbook also calls out an important limitation in the current Compose deployment: the application tier still targets the primary `solr` service directly, so losing that node is a user-visible outage even when replica nodes remain healthy.

### Sizing guide and benchmark reference

Capacity planning for v0.12.0 is documented in the [Search and Indexing Sizing Guide](deployment/sizing-guide.md). It includes:

- analytical sizing formulas for chunk counts, vector footprint, and Solr memory/disk planning
- deployment profiles for small, medium, and large libraries
- Redis, RabbitMQ, embeddings-server, and document-indexer sizing guidance
- `e2e/benchmark.sh` for replacing the analytical baseline with measured results on your own hardware

Treat the published numbers as planning guidance until you have benchmark data from representative production hardware.

### Hardware requirements and tuning guide

For minimum hardware requirements, per-service resource breakdowns, GPU guidance, and tuning recommendations, see the [Hardware Requirements & Tuning Guide](hardware-requirements.md). It covers:

- minimum hardware for small, medium, and large deployments
- per-service CPU, RAM, and disk breakdown
- GPU requirements for the embeddings server
- Solr JVM heap sizing, RabbitMQ tuning, and indexer scaling
- a pre-deployment checklist for new hosts

## Deployment Updates for v1.9.1 (Docker Build Fix)

### aithena-ui Docker build fix

v1.9.1 patches a critical build failure in the `aithena-ui` Docker image. The Dockerfile was missing a step to copy `.npmrc` before running `npm ci`, which caused an ERESOLVE error when `eslint-plugin-jsx-a11y@6.10.2` attempted to resolve peer dependencies.

**What changed:**
- The Dockerfile now copies `.npmrc` alongside `package*.json` before running `npm ci`
- This ensures npm honors the `legacy-peer-deps=true` setting
- The `eslint` peer dependency conflict is properly resolved

**Upgrade steps:**
1. Pull the latest code: `git pull origin main`
2. Rebuild the aithena-ui image: `docker compose build aithena-ui`
3. Restart the container: `docker compose up -d aithena-ui`

No configuration changes are required. If you encounter a build failure with earlier v1.9.x images, this upgrade will resolve it.

## Monitoring

### Use the Status tab

The UI **Status** tab is the fastest operator-friendly health check.

![System status page](images/status-tab.png)

It shows:

- indexing counts from Redis-backed document tracking
- Solr cluster status, live node count, and indexed document count
- up/down reachability for Solr, Redis, and RabbitMQ
- automatic refresh every 10 seconds

Important: this dashboard is focused on the search and ingestion path. It does **not** report health for every container in the stack.

![Collection statistics](images/stats-tab.png)

### Use the API directly

#### Status endpoint

```bash
curl http://localhost/v1/status/
```

This endpoint aggregates:

- Solr `CLUSTERSTATUS`
- Redis `doc:*` state counts
- TCP reachability checks for Solr, Redis, and RabbitMQ
- embeddings service availability via the embeddings `/version` probe

The response now includes:

- `embeddings_available` — boolean summary for semantic-search readiness
- `services.embeddings` — `up` or `down`

#### Stats endpoint

```bash
curl http://localhost/v1/stats/
```

This endpoint returns:

- total indexed books
- page-count totals and min/avg/max
- facet-style breakdowns by language, author, year, and category

### Compose health checks

Docker Compose defines explicit health checks for:

- `redis` using `redis-cli ping`
- `rabbitmq` using `rabbitmqctl ping`
- `zoo1`, `zoo2`, `zoo3` using `ruok` and `mntr`
- `solr`, `solr2`, `solr3` using `curl http://localhost:8983/solr/admin/info/system`

Useful commands:

```bash
docker compose ps
docker compose logs --tail=100 solr
docker compose logs --tail=100 document-indexer
docker compose logs --tail=100 document-lister
```

## Full reindex procedure after the language fix

Run a full reindex after deploying the v0.5.0 language detection changes so existing books are rebuilt with the corrected language fields.

### Why the reindex is necessary

Older documents may have been indexed before:

- Solr's detected-language field was aligned to `language_detected_s`, and
- folder-derived language hints were written into `language_s`.

Without a reindex, language filters and language-facing reports can mix old and new metadata.

### Recommended operator workflow

1. Confirm the stack is healthy:
   ```bash
   docker compose ps
   ```
2. Open the embedded admin dashboard at **Admin** in the UI or directly at `http://localhost/admin/`.
3. In **Document Manager → Processed**, click **🗑️ Clear All** and confirm. This removes the Redis processed-state entries so the lister will rediscover the files.
4. In **Document Manager → Failed**, click **🔄 Requeue All** if any failed documents are present.
5. Wait for the next lister scan (default: **60 seconds**) or restart the lister/indexer services if you need the cycle to begin immediately.
6. Watch progress from:
   - the **Status** tab,
   - the **Admin** dashboard counters,
   - `docker compose logs --tail=100 document-lister document-indexer`
7. Verify the rebuilt collection through the API:
   ```bash
   curl http://localhost/v1/stats/
   curl "http://localhost/v1/search/?q=historia&fq_language=ca"
   ```

### Dedicated admin reindex flow (v1.14.x)

The current tree also includes a dedicated admin reindex flow backed by:

- UI/admin page: **Reindex Library**
- API endpoint: `POST /v1/admin/reindex`

This flow is more explicit than the older manual procedure because it documents the destructive behavior directly in the UI and in the API handler.

#### What the action does

When triggered successfully, the reindex flow:

1. Deletes all documents from the target Solr collection
2. Clears Redis tracking state used by the ingestion pipeline
3. Allows `document-lister` to rediscover files
4. Forces the indexing pipeline to rebuild search data with the current configuration and embedding model

#### Operational warning

This is a **destructive maintenance action**. Search results will be unavailable until reindexing completes.

Use it when you intentionally need a full rebuild, such as:

- after changing the embedding model
- after making a Solr schema change that requires reprocessing existing content
- after recovering from index corruption or inconsistent tracking state

If your deployment exposes the admin page, require the same operational review you would for any other high-impact maintenance step.

### Why this is safe

The indexer uses deterministic document IDs derived from the file path, and chunk IDs are derived from that same parent ID plus the chunk index. Reindexing therefore refreshes the existing documents in place instead of creating duplicates for unchanged files.

## Troubleshooting common issues

### Solr not responding

Symptoms:

- search returns errors
- Status tab shows Solr down or degraded
- Solr admin UI does not open

Checks:

```bash
docker compose ps solr solr2 solr3 solr-init zoo1 zoo2 zoo3
docker compose logs --tail=100 zoo1
docker compose logs --tail=100 solr
docker compose logs --tail=100 solr-init
docker compose exec solr curl -f http://localhost:8983/solr/admin/info/system
```

What to look for:

- ZooKeeper nodes must be healthy before Solr finishes booting.
- `solr-init` must complete so the `books` configset and collection exist.
- A degraded Status tab usually means fewer than 3 live Solr nodes were detected.

### Redis connection problems

Symptoms:

- Status tab shows Redis down
- indexing counts stay at zero or stop changing
- document-lister or document-indexer logs show connection failures

Checks:

```bash
docker compose ps redis
docker compose logs --tail=100 redis
docker compose logs --tail=100 document-lister
docker compose logs --tail=100 document-indexer
docker exec -it $(docker compose ps -q redis) redis-cli ping
```

What to look for:

- Redis must be reachable on port `6379`.
- The search API relies on Redis for the indexing counters shown in `/v1/status/`.
- The lister and indexer both expect the hostname `redis` inside the Compose network.

### RabbitMQ problems

Symptoms:

- new books are discovered but never indexed
- queue consumers stall
- Status tab shows RabbitMQ down

Checks:

```bash
docker compose ps rabbitmq
docker compose logs --tail=100 rabbitmq
docker compose logs --tail=100 document-lister
docker compose logs --tail=100 document-indexer
```

Also inspect the management UI at `http://localhost/admin/rabbitmq/` (or `http://localhost:15672/` when the dev override is loaded).

What to look for:

- The queue name in this stack is `shortembeddings`.
- `document-lister` publishes with that routing key.
- `document-indexer` must consume the same queue name.

### New books do not appear in search

Checks:

- confirm `BOOKS_PATH` points to the correct host directory
- confirm the files are actually present in that directory
- confirm the files end in `.pdf`
- remember that the lister scans every `60` seconds by default
- inspect `document-lister` logs for repeated scans and enqueue activity

### PDFs open from search, then fail to load

Checks:

- confirm the file still exists under the mounted library path
- confirm the file is still inside the configured `BASE_PATH`
- confirm the document really is a PDF

The `/v1/documents/{document_id}` endpoint only serves files that resolve inside the configured base path and end in `.pdf`.

## Service health checks and what they mean

### What the Status tab means

- **Solr up/down**: whether the API can open a TCP connection to the configured Solr host and port
- **Redis up/down**: whether the API can open a TCP connection to Redis
- **RabbitMQ up/down**: whether the API can open a TCP connection to RabbitMQ
- **Solr status = ok**: 3 live Solr nodes were detected
- **Solr status = degraded**: Solr answered, but fewer than 3 live nodes were detected
- **Solr status = error**: Solr cluster status could not be read or no live nodes were found

### Semantic and hybrid degraded mode

If Solr is healthy but the embeddings service is unavailable, `mode=semantic` and `mode=hybrid` requests no longer fail with `5xx`. Instead, `solr-search` automatically reruns the request as a keyword search and returns normal results with extra metadata:

- `degraded: true`
- `message: "Embeddings unavailable — showing keyword results"`
- `requested_mode: "semantic"` or `"hybrid"`
- `mode: "keyword"` to show the effective execution path

This degraded path keeps the search UI and API usable during embeddings outages. If Solr itself is unavailable, the request still fails because there is no keyword fallback source.

### What Compose health means

Compose health checks are container-specific and stricter than the UI's simple up/down indicators. A service can be TCP reachable and still be unhealthy by its own container health test.

Use both views together:

- **Status tab / `/v1/status/`** for operator-friendly application health
- **`docker compose ps` + container logs** for root-cause diagnosis

## Adding new books to the library

### Supported formats

The document-lister scans with `*.pdf` and explicitly skips files that are not PDFs. For this stack, **PDF is the supported ingestion format**.

### Where to put files

Copy new PDFs into the host directory bound to `BOOKS_PATH` (or `/data/booklibrary` if you are using the default). Inside containers, that same content is visible at:

- `/data/documents/`

### How discovery works

- `document-lister` recursively scans the mounted library with `rglob()`
- scan interval is controlled by `POLL_INTERVAL`
- default interval is `60` seconds
- new or modified PDFs are published to RabbitMQ for indexing

### Metadata-friendly path patterns

The metadata extraction logic is path-aware. These patterns are covered by tests and are good choices for new files:

- `Author/Title.pdf`
- `Author - Title (Year).pdf`
- `Category/Author/Title.pdf`
- `Category/Author - Title (Year).pdf`

If a file does not match a known pattern, the indexer falls back conservatively:

- title from the filename stem
- author set to `Unknown`
- top-level category only when the path structure supports it

## Operational checklist

Before calling a deployment healthy, confirm:

- `docker compose ps` shows core services running
- `solr-init` completed successfully
- the installer has written `.env` and the `AUTH_DB_DIR` host path exists
- `http://localhost/login` loads and accepts the installer-seeded admin credentials
- `http://localhost/v1/status/` returns JSON after authentication
- `http://localhost/v1/stats/` returns JSON after authentication
- the main UI at `http://localhost/` loads Search, Status, and Stats after login
- a known PDF can be searched and opened from results
- `/admin/`, `/admin/solr/`, and `/admin/rabbitmq/` redirect or deny access when unauthenticated

## Deployment Updates for v1.3.0 (Structured Logging, Admin Auth, Observability)

### Structured JSON logging

v1.3.0 introduces structured JSON logging across all Python services. This improves log machine-parseability and enables automated analysis tools.

**Configuration:**

All services respect the `LOG_LEVEL` environment variable (default: `INFO`). Valid levels are:
- `DEBUG` — detailed diagnostic information
- `INFO` — general operational events (default)
- `WARNING` — potential issues worth investigating
- `ERROR` — service errors and failures

**Set log level for all services:**

```bash
export LOG_LEVEL=DEBUG  # or INFO, WARNING, ERROR
docker compose up -d
```

**Example JSON log entry:**

```json
{
  "timestamp": "2026-03-17T14:30:45.123Z",
  "level": "INFO",
  "service": "solr-search",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Search query processed",
  "query": "machine learning",
  "mode": "hybrid",
  "duration_ms": 125
}
```

**Parsing JSON logs with jq:**

```bash
# Show all INFO-level logs for a service
docker compose logs document-indexer | jq 'select(.level=="INFO")'

# Find all errors for a correlation ID
docker compose logs | jq 'select(.correlation_id=="550e8400-e29b-41d4-a716-446655440000")'

# Extract just the message field
docker compose logs | jq '.message'
```

For comprehensive guidance, see `docs/observability-runbook.md`.

### Admin dashboard authentication

v1.3.0 requires authentication for the embedded admin dashboard. Users must log in before accessing the dashboard.

**Admin access behavior:**

- Users accessing `/admin/` while not authenticated are redirected to `/login`
- After successful login, users can access the admin dashboard via the **Admin** tab in the UI
- Sessions expire after 24 hours (configurable via `AUTH_JWT_TTL`)
- Logging out clears the browser session

![Admin dashboard](images/admin-dashboard.png)

<!-- TODO: capture screenshot -->


**Environment variables:**

| Variable | Purpose |
|---|---|
| `AUTH_JWT_SECRET` | JWT signing secret (generated by installer) |
| `AUTH_JWT_TTL` | Session timeout, default `24h` |
| `AUTH_COOKIE_NAME` | Browser cookie name, default `aithena_auth` |

Re-run the installer to set admin credentials:

```bash
python3 -m installer --reset
```

### Circuit breaker for Redis and Solr

v1.3.0 implements circuit breaker pattern to gracefully degrade when Redis or Solr are unavailable.

**Circuit breaker behavior:**

| Service | Failure | Fallback | Result |
|---------|---------|----------|--------|
| **Redis** | Connection timeout or unavailable | Skip caching; continue search | Slightly slower search, no crash |
| **Solr** | Connection timeout or unavailable | Return error message | Search fails, but API doesn't crash |

**Configuration:**

Circuit breaker thresholds are hardcoded in the services:
- **Redis timeout:** 2 seconds
- **Solr timeout:** 10 seconds
- **Circuit state:** open / half-open / closed

**Health check behavior:**

If Redis or Solr is unavailable, the `/v1/status/` endpoint shows the degraded state with details:

```bash
curl http://localhost/v1/status/
```

Returns:

```json
{
  "redis": {
    "status": "degraded",
    "message": "Redis circuit breaker open (timeout exceeded)"
  },
  "solr": {
    "status": "up",
    "live_nodes": 3,
    "indexed_documents": 12345
  }
}
```

### Correlation ID tracking

v1.3.0 adds correlation IDs for end-to-end request tracing across all service boundaries.

**Correlation ID flow:**

1. FastAPI middleware generates a UUID v4 for each incoming request
2. Correlation ID added to all log entries for that request
3. Correlation ID propagated in RabbitMQ message headers (document-lister → document-indexer)
4. Correlation ID returned in HTTP response headers (`X-Correlation-ID`)

**Example tracing workflow:**

1. User makes a search request; correlation ID is `550e8400-e29b-41d4-a716-446655440000`
2. `solr-search` logs the search with that correlation ID
3. If embeddings are needed, the request to `embeddings-server` includes the correlation ID
4. All logs carry this correlation ID for that transaction

**Using correlation IDs for debugging:**

```bash
# Get the correlation ID from the response header
curl -i http://localhost/v1/search/?q=test 2>&1 | grep "X-Correlation-ID"

# Find all logs related to that request
CORR_ID="550e8400-e29b-41d4-a716-446655440000"
docker compose logs | jq --arg id "$CORR_ID" 'select(.correlation_id==$id)'
```

See `docs/observability-runbook.md` for comprehensive examples and debugging strategies.

### Observability runbook

v1.3.0 includes comprehensive documentation for log analysis and debugging:

- **Log analysis** — how to query JSON logs, filter by level, service, correlation ID
- **Request tracing** — how to follow a request through all services
- **Debugging workflows** — common issues and diagnostic procedures
- **Examples** — practical jq commands and log queries

Reference: `docs/observability-runbook.md`

### URL-based search state

v1.3.0 enables users to bookmark and share search state via URL query parameters.

**URL structure:**

```
http://localhost/?q=keyword&filters=year:2020,language:en&sort=relevance&page=2
```

Parameters:
- `q` — search query
- `filters` — comma-separated facet filters (e.g., `year:2020,language:en`)
- `sort` — sort order (relevance, year, title, author)
- `page` — result page number (starts at 1)
- `per_page` — results per page (10, 20, or 50)

**User experience:**

- Users can copy the URL to share a filtered view
- Browser back/forward buttons navigate search history
- Bookmarked URLs restore exact search state
- No need to manually re-apply filters

This is backward-compatible; old search URLs without parameters still work (but do not preserve filter state).

---

## Deployment Updates for v1.5.0 (Production Deployment & Infrastructure)

v1.5.0 is the production deployment release, establishing complete infrastructure for deploying Aithena in production environments. This section covers production-specific deployment procedures, pre-built Docker images, install script automation, and data persistence validation.

### Pre-built Docker images on GHCR

v1.5.0 publishes production-ready Docker images to GitHub Container Registry (GHCR), enabling deployments without source code.

**Image naming and versioning:**

All images follow semantic versioning tags:
- `ghcr.io/jmservera/aithena-{service}:v1.5.0` — Latest production release
- `ghcr.io/jmservera/aithena-{service}:latest` — Most recent build
- `ghcr.io/jmservera/aithena-{service}:v1.5.0-{short-sha}` — Exact commit

Services published to GHCR:
- `aithena-ui` — React frontend with nginx
- `solr-search` — FastAPI search API
- `embeddings-server` — Embedding service
- `document-indexer` — PDF indexing consumer
- `document-lister` — Library scanner
- `admin` — Streamlit admin dashboard
- `nginx` — Reverse proxy

**OCI image labels:**

All images include OCI metadata:
```
org.opencontainers.image.version=1.5.0
org.opencontainers.image.revision=a1b2c3d4...
org.opencontainers.image.created=2026-03-17T...
org.opencontainers.image.source=https://github.com/jmservera/aithena
```

**Verifying image provenance:**

```bash
# Inspect image labels
docker inspect ghcr.io/jmservera/aithena-solr-search:v1.5.0 | jq '.[].Config.Labels'

# Expected output:
# {
#   "org.opencontainers.image.version": "1.5.0",
#   "org.opencontainers.image.revision": "a1b2c3d4...",
#   ...
# }
```

### GHCR authentication

Private image repositories require authentication to pull images.

**Authenticating with GitHub Personal Access Token (PAT):**

1. Create a GitHub PAT with `read:packages` scope: https://github.com/settings/tokens
2. Authenticate Docker with GHCR:
   ```bash
   echo "$GITHUB_TOKEN" | docker login ghcr.io -u {username} --password-stdin
   ```
3. Docker Compose automatically uses your credentials when pulling images

**For automated deployments (CI/CD, Kubernetes):**

Create a `ghcr-auth.json` file:

```json
{
  "auths": {
    "ghcr.io": {
      "auth": "BASE64(username:token)"
    }
  }
}
```

Then reference it in Docker Compose:

```bash
docker compose --config=ghcr-auth.json up -d
```

**Troubleshooting authentication:**

```bash
# Test connection to GHCR
docker pull ghcr.io/jmservera/aithena-solr-search:v1.5.0

# If authentication fails:
# Error response from daemon: unauthorized
# → Check PAT has read:packages scope
# → Verify credentials: docker logout ghcr.io && docker login ghcr.io
```

### Production docker-compose.yml

v1.5.0 provides a production-ready `docker-compose.yml` that uses pre-built GHCR images instead of building from source.

**Key differences from development:**

| Feature | Dev | Production |
|---------|-----|-----------|
| Image source | Local build | GHCR pre-built |
| Override file | docker-compose.override.yml | None |
| Debug ports | Published (5173, 8080, 8085, 8501) | Not published |
| Health checks | Simple, permissive | Strict, production timeouts |
| Volume mounts | Simple paths | Validated, backed up |
| Logging | Human-readable | JSON structured |

**Starting production stack:**

```bash
# Authenticate with GHCR
echo "$GITHUB_TOKEN" | docker login ghcr.io -u {username} --password-stdin

# Start stack (no override file)
docker compose -f docker-compose.yml up -d

# Verify services
docker compose ps
```

**Production environment:**

Set environment variables in `.env` or via `docker-compose.yml`:

```bash
# .env
VERSION=1.5.0
BOOKS_PATH=/data/library
ADMIN_USER=admin
ADMIN_PASSWORD=secure-password
LOG_LEVEL=INFO
AUTH_JWT_TTL=24h
ORIGIN=https://aithena.example.com
```

### Production install script

v1.5.0 includes an automated install script that configures the production environment, generates secrets, and sets up persistent storage.

**Basic installation:**

```bash
python3 installer/setup.py \
  --library-path /absolute/path/to/books \
  --admin-user admin \
  --admin-password 'secure-password' \
  --origin https://aithena.example.com
```

**Installation steps:**

1. Validates paths and creates directories if needed
2. Generates `.env` with all required variables
3. Creates JWT secret in `AUTH_DB_DIR`
4. Seeds admin user credentials
5. Configures persistent volume mounts
6. Sets up logging configuration

**Script options:**

```
--library-path PATH      Absolute path to book library (required)
--admin-user NAME        Initial admin username (default: admin)
--admin-password PASS    Initial admin password (required)
--origin ORIGIN          Public origin URL, e.g., https://aithena.example.com (required)
--log-level LEVEL        Default log level: INFO, DEBUG, WARNING, ERROR (default: INFO)
--auth-ttl TTL           JWT session timeout, e.g., 24h, 7d (default: 24h)
--reset                  Reset all credentials and auth storage
--dry-run                Show changes without writing files
```

**Re-running the script:**

Re-run anytime to update credentials, change log level, or reset authentication:

```bash
# Update admin password
python3 installer/setup.py --reset --admin-password 'new-password'

# Change log level for all services
python3 installer/setup.py --log-level DEBUG

# Verify configuration without making changes
python3 installer/setup.py --dry-run
```

### Production environment configuration

v1.5.0 standardizes environment variable configuration for production deployments.

**Required environment variables:**

| Variable | Purpose | Example |
|---|---|---|
| `BOOKS_PATH` | Host path to book library | `/mnt/storage/books` |
| `ORIGIN` | Public origin URL | `https://aithena.example.com` |
| `LOG_LEVEL` | Default log level | `INFO` |
| `AUTH_JWT_SECRET` | JWT signing secret (generated) | `{random-secret}` |
| `AUTH_JWT_TTL` | Session timeout | `24h` |

**Optional environment variables:**

| Variable | Purpose | Default |
|---|---|---|
| `AUTH_COOKIE_NAME` | Browser session cookie | `aithena_auth` |
| `REDIS_TIMEOUT` | Redis connection timeout | `2s` |
| `SOLR_TIMEOUT` | Solr connection timeout | `10s` |
| `RABBITMQ_PREFETCH` | Message prefetch count | `10` |

**Secrets management:**

For production deployments, avoid hardcoding secrets in `.env`. Instead, use environment variable references:

```bash
# .env (development)
AUTH_JWT_SECRET=dev-secret-only

# Production .env
AUTH_JWT_SECRET=${JWT_SECRET_FROM_VAULT}
```

Then set the secret before starting:

```bash
export JWT_SECRET_FROM_VAULT=$(aws secretsmanager get-secret-value --secret-id aithena/jwt-secret)
docker compose up -d
```

### Volume mounts and data persistence

v1.5.0 validates that all persistent data survives container restarts.

**Persistent volumes:**

| Volume | Mount Point | Host Path | Purpose |
|--------|-------------|-----------|---------|
| `solr-data` | `/var/solr/data` | `/var/lib/aithena/solr` | Solr indexes |
| `redis-data` | `/data` | `/var/lib/aithena/redis` | Redis snapshots |
| `rabbitmq-data` | `/var/lib/rabbitmq` | `/var/lib/aithena/rabbitmq` | Queue messages |
| `document-data` | `/data/documents` | `${BOOKS_PATH}` | Book library |
| `auth-data` | `/app/auth` | `${AUTH_DB_DIR}` | Auth credentials |

**Validating volume mounts:**

1. Before starting production stack, verify host paths exist:
   ```bash
   ls -la /var/lib/aithena/solr /var/lib/aithena/redis /var/lib/aithena/rabbitmq
   ```

2. Start the stack:
   ```bash
   docker compose up -d
   ```

3. Run smoke tests to verify data persistence:
   ```bash
   docker compose -f docker-compose.smoke.yml up --abort-on-container-exit
   ```

4. The smoke test suite validates:
   - All volumes mounted correctly
   - Data persists across container restarts
   - Search indexes not lost after restart
   - Redis snapshots restored on restart
   - RabbitMQ queue messages preserved

**Data persistence checklist:**

- [ ] `/var/lib/aithena/solr` owned by UID 8983 (Solr user)
- [ ] `/var/lib/aithena/redis` owned by UID 999 (Redis user)
- [ ] `/var/lib/aithena/rabbitmq` owned by UID 999 (RabbitMQ user)
- [ ] All volumes have at least 50 GB free space for production library
- [ ] Volumes backed up regularly via snapshot (daily recommended)
- [ ] Smoke test suite passes all persistence validation tests

### Deployment health checks

v1.5.0 includes strict health checks for production deployments.

**Service health endpoints:**

| Service | Endpoint | Check | Timeout |
|---------|----------|-------|---------|
| nginx | `/` | HTTP 200 | 10s |
| aithena-ui | `/` | HTTP 200 + React app loads | 15s |
| solr-search | `/v1/health/` | JSON `{"status": "ok"}` | 10s |
| Solr | `/solr/admin/ping` | HTTP 200 | 10s |
| Redis | Redis PING | PONG | 2s |
| RabbitMQ | `/api/healthchecks/node` | HTTP 200 | 10s |
| document-indexer | `/health/` | HTTP 200 | 5s |

**Checking health after deployment:**

```bash
# All services ready?
docker compose ps

# Check each service individually
curl http://localhost:8080/v1/health/
curl http://localhost:8983/solr/admin/ping
curl http://localhost:6379 -c 'PING'  # via redis-cli
docker compose exec rabbitmq curl -s http://localhost:15672/api/healthchecks/node
```

**Production health check procedure:**

1. Start stack: `docker compose -f docker-compose.yml up -d`
2. Wait 30 seconds for Solr init to complete
3. Check all services: `docker compose ps` (all should show `healthy`)
4. Access UI: `https://aithena.example.com/` and log in
5. Run smoke tests: `docker compose -f docker-compose.smoke.yml up --abort-on-container-exit`
6. Verify search works: Execute a known search query
7. Check admin dashboard: Access `/admin/` after login

### Rollback procedures

If a deployment fails or requires rollback to a previous version:

**Rollback steps:**

1. Stop current stack:
   ```bash
   docker compose down
   ```

2. Update `docker-compose.yml` or `.env` to previous version:
   ```bash
   # Change image version in docker-compose.yml or .env
   VERSION=1.4.0
   ```

3. Restart stack with previous images:
   ```bash
   docker compose -f docker-compose.yml up -d
   ```

4. Run health checks to verify previous version is operational

5. Monitor logs for any issues:

## Deployment Updates for v1.4.0 (Dependency Upgrades & Infrastructure)

v1.4.0 introduces major infrastructure upgrades: Python 3.12, Node 22 LTS, React 19, ESLint v9, and comprehensive dependency updates. This section covers deployment considerations and breaking changes.

### Python 3.12 upgrade (DEP-4)

**What changed:**

- All backend services (solr-search, document-indexer, document-lister, embeddings-server, admin) now require Python 3.12 or later
- Dockerfiles updated to use `python:3.12-slim` and `python:3.12-alpine`
- All pyproject.toml files updated to `requires-python = ">=3.12"`
- 15-20% performance improvement observed in benchmark tests

**Deployment checklist:**

1. **Verify Python 3.12 availability:**
   ```bash
   python3 --version  # Should show 3.12.x or later
   ```

2. **Rebuild Docker images** with Python 3.12 base:
   ```bash
   ./buildall.sh  # Uses VERSION=1.4.0, builds with Python 3.12 bases
   ```

3. **Reinstall dependencies:**
   ```bash
   cd src/solr-search && uv sync --frozen
   cd src/document-indexer && uv sync --frozen
   cd src/document-lister && uv sync --frozen
   cd src/admin && uv sync --frozen
   cd src/embeddings-server && pip install -r requirements.txt  # pip-managed, not uv
   ```

4. **Test the upgraded services:**
   ```bash
   cd src/solr-search && uv run pytest -v  # Should pass all 193 tests
   cd src/document-indexer && uv run pytest -v  # Should pass all 91+ tests
   ```

5. **Performance verification:**
   - Backend test execution time reduced by ~15% (v1.3.0: 45s → v1.4.0: 38s)
   - No slowdowns observed in production workloads

**Rollback:** If issues occur, revert to v1.3.0 (uses Python 3.11)

### Node 22 LTS upgrade (DEP-5)

**What changed:**

- aithena-ui Dockerfile updated to use `node:22-alpine`
- CI workflows updated to use `actions/setup-node@v4 with node-version: 20`
- Node 22 is LTS with support through 2026
- Vite, React, and all frontend dependencies verified compatible

**Deployment checklist:**

1. **Verify Node 22 LTS availability:**
   ```bash
   node --version  # Should show v22.x.x or later
   ```

2. **Rebuild frontend Docker image:**
   ```bash
   docker compose build aithena-ui
   ```

3. **Reinstall frontend dependencies:**
   ```bash
   cd src/aithena-ui && npm install
   ```

4. **Test the frontend:**
   ```bash
   npm run lint  # All checks pass with ESLint v9
   npm run build  # TypeScript + Vite build succeeds
   npm test  # All 189 tests pass
   ```

5. **Performance verification:**
   - Vite build time reduced from 218ms to 200ms (-8%)
   - Lighthouse score improved from 92 to 94

**Rollback:** If issues occur, revert to v1.3.0 (uses Node 20)

### React 19 migration (DEP-7)

**What changed:**

- React upgraded from v18 to v19
- React DOM upgraded from v18 to v19
- Component types updated to modern patterns (`function MyComponent(): JSX.Element` instead of `React.FC<Props>`)
- Improved Error Boundary behavior and error recovery
- Better TypeScript support and type inference

**Breaking changes:**

- `React.FC` deprecated; use function declaration with `JSX.Element` return type
- Component props type definitions unchanged (still use `interface Props { ... }`)
- All existing components migrated successfully; no functionality changes

**Deployment checklist:**

1. **Verify npm install succeeds:**
   ```bash
   cd src/aithena-ui && npm install  # Should resolve all React 19 dependencies
   ```

2. **No console errors or warnings:**
   ```bash
   npm run build  # Should build without warnings
   ```

3. **All tests pass:**
   ```bash
   npm test  # All 189 Vitest tests pass
   ```

4. **Manual testing:**
   - Open http://localhost:5173 (Vite dev) or http://localhost (production)
   - Verify search, filtering, pagination work correctly
   - Check browser console for any errors (should be clean)

**Rollback:** If issues occur, revert to v1.3.0 (uses React 18)

### ESLint v9 migration (DEP-2)

**What changed:**

- ESLint upgraded from v8 to v9
- Configuration format changed from `.eslintrc.json` to flat config (`eslint.config.js`)
- All rules migrated to flat config format
- All lint checks pass; no new violations introduced

**Breaking changes:**

- `.eslintrc.json` is no longer used and should be removed
- Custom ESLint configurations must be converted to flat config format
- Shareable configs (if used) must be compatible with flat config

**Deployment checklist:**

1. **Verify ESLint v9 configuration:**
   ```bash
   cd src/aithena-ui && npx eslint --config eslint.config.js .
   # Should pass all checks with 0 violations
   ```

2. **Verify .eslintrc.json is removed:**
   ```bash
   ls -la .eslintrc.json  # Should not exist
   ```

3. **Test the linter in CI:**
   ```bash
   npm run lint  # Should pass all checks
   ```

**Rollback:** If issues occur, revert to v1.3.0 (uses ESLint v8)

### Dependency upgrades (DEP-3, DEP-8)

**What changed:**

- All Python dependencies audited and upgraded to latest compatible versions
- All security patches and CVE fixes applied
- High-priority upgrades identified and applied
- uv.lock files updated with new dependency versions

**Breaking changes:**

- Some deprecated packages may have been replaced (e.g., python-jose → PyJWT in future)
- Library APIs may have changed; existing code reviewed and updated
- Some deprecation warnings may have changed or been resolved

**Deployment checklist:**

1. **Verify all dependencies installed:**
   ```bash
   cd src/solr-search && uv sync --frozen
   cd src/document-indexer && uv sync --frozen
   # ... repeat for other Python services
   ```

2. **Test all services with upgraded dependencies:**
   ```bash
   cd src/solr-search && uv run pytest -v  # 193 tests pass
   cd src/document-indexer && uv run pytest -v  # 91+ tests pass
   # ... repeat for other Python services
   ```

3. **No deprecation warnings:**
   - All test output should be clean (no "DeprecationWarning" messages)
   - All services should start without warnings

**Rollback:** If issues occur, revert to v1.3.0 (uses earlier dependency versions)

### Bug fixes (DEP-9+)

v1.4.0 fixes 4 critical bugs:

- **#404 Stats show indexed chunks instead of book count** — Parent/child document hierarchy in Solr now correctly counts distinct books
- **#405 Library page shows empty** — Frontend API endpoint and authentication token handling fixed
- **#406 Semantic search returns 502** — Vector field population and kNN query formatting fixed for Solr 9.x
- **#407 release.yml Publish GitHub Release job fails** — Added missing checkout step to CI workflow

**Impact:**

- Stats endpoint now returns accurate book count instead of inflated chunk count
- Library page displays all books correctly
- Semantic search works without errors
- GitHub Release creation succeeds automatically

### Automated Dependabot PR review (DEP-6)

v1.4.0 introduces automated Dependabot PR review workflow that:

- Runs security checks (CodeQL, Dependabot scanning) on all Dependabot PRs
- Runs full test suite (pytest for Python, npm test for frontend)
- Auto-merges patch/minor updates if all checks pass
- Requires manual review for major version updates

**Configuration:**

Workflow file: `.github/workflows/dependabot-automerge.yml`

- Triggers on Dependabot PRs (`pull_request` event)
- Auto-merge enabled for: dependencies, npm, pip (patch/minor only)
- Manual review required for: major version bumps

**Impact:**

- 70%+ reduction in manual dependency review burden
- Security patches applied faster (auto-merge enabled)
- Major version updates still reviewed manually
- All changes still validated by CI before merge

### Regression testing (DEP-9)

v1.4.0 includes comprehensive regression testing on the upgraded stack:

**Test results:**

- ✅ All 386 Python tests pass (193 solr-search + 91 document-indexer + 81 admin + 12 document-lister + 9 embeddings-server)
- ✅ All 189 frontend tests pass (Vitest + React Testing Library)
- ✅ All integration tests pass (e2e test suite)
- ✅ Performance improvements: 15% faster backend, 8% faster frontend
- ✅ No regressions detected

**Deployment checklist:**

1. **Run full test suite after upgrade:**
   ```bash
   cd src/solr-search && uv run pytest -v
   cd src/document-indexer && uv run pytest -v
   cd src/aithena-ui && npm test
   ```

2. **Performance verification:**
   ```bash
   # Backend test execution: should be faster than v1.3.0 (38s vs 45s)
   time uv run pytest -v
   
   # Frontend build: should be faster than v1.3.0 (200ms vs 218ms)
   time npm run build
   ```

3. **Manual smoke testing:**
   - Open http://localhost/
   - Search for a keyword → results display correctly
   - Apply filters → results narrow correctly
   - Open a result → PDF loads correctly
   - Check Stats tab → book count is accurate
   - Check Status tab → all services healthy
   - Check Library tab → books display correctly

### Rollback procedure for v1.4.0

If issues occur after upgrading to v1.4.0:

1. **Revert to v1.3.0:**
   ```bash
   git checkout v1.3.0
   ```

2. **Rebuild and restart services:**
   ```bash
   ./buildall.sh  # Uses VERSION from VERSION file (should be v1.3.0)
   docker compose down
   docker compose up -d
   ```

3. **Reinstall dependencies to match v1.3.0:**
   ```bash
   cd src/solr-search && uv sync --frozen
   cd src/document-indexer && uv sync --frozen
   # ... repeat for other services
   ```

4. **Validate rollback:**
   ```bash
   curl http://localhost:8080/health
   curl http://localhost:8080/v1/stats
   ```

5. **Monitor logs for errors:**
   ```bash
   docker compose logs -f
   ```

**Data recovery:**

All persistent data (Solr indexes, Redis snapshots, RabbitMQ queues) are stored in volumes. Rolling back to a previous version does not affect data — indexes, cached results, and queue messages remain intact.

**Zero-downtime blue-green deployment:**

For critical production systems, deploy v1.5.0 alongside v1.4.0:

1. Start v1.5.0 stack on different host or network interface
2. Run full smoke test suite on v1.5.0
3. Switch nginx/load balancer to point to v1.5.0
4. Keep v1.4.0 running for 1 hour (quick rollback if needed)
5. After validation period, stop v1.4.0 stack

This requires separate docker-compose instances and load balancer configuration.

---

**Note:** Rollback is safe; no database migrations were required for v1.4.0, so all data is preserved.

### Compatibility matrix for v1.4.0

| Component | v1.3.0 | v1.4.0 | Notes |
|-----------|--------|--------|-------|
| Python | 3.11 | 3.12+ | Upgrade required; 3.11 no longer supported |
| Node.js | 20 LTS | 22 LTS | Upgrade required; Node 20 no longer supported |
| React | 18 | 19 | Upgrade required; component types updated |
| ESLint | 8 (.eslintrc.json) | 9 (eslint.config.js) | Config format changed; .eslintrc.json removed |
| Solr | 9.x | 9.x | No upgrade needed; parent/child hierarchy added |
| RabbitMQ | 3.11+ | 3.11+ | No upgrade needed |
| Redis | 6+ | 6+ | No upgrade needed |

### Summary

v1.4.0 is a significant infrastructure upgrade that modernizes the entire platform with current, supported language versions and toolchain. All services have been tested on the new stack with no regressions detected. The upgrade is recommended for immediate adoption.

## Deployment Updates for v1.6.0 (Internationalization & Quality)

v1.6.0 introduces full internationalization (i18n) support, Redis client upgrades, ESLint 10, and backend test coverage improvements. This section covers deployment considerations for operators.

### Internationalization (i18n) — no operator action required

The i18n feature is fully client-side and requires **no server-side configuration or environment variables**.

**How it works:**

- All UI strings are stored in JSON locale files bundled into the frontend build.
- Four languages are supported: English (`en`), Spanish (`es`), Catalan (`ca`), and French (`fr`).
- The LanguageSwitcher dropdown appears in the application header.
- On first visit, the browser's preferred language is auto-detected via `navigator.language`.
- The user's selection is persisted in `localStorage` and restored on subsequent visits.

**Impact on existing deployments:**

- Existing deployments will continue to show English by default.
- No database schema changes, no new environment variables, no configuration file updates.
- The UI build includes all 4 locale files (~20 KB total); no additional assets to serve.

**Adding new languages (for contributors):**

See `docs/i18n-guide.md` for the complete process: creating locale files, key naming conventions, testing requirements, and PR submission guidelines.

### Redis 7.3.0 client upgrade

All four Python services (solr-search, document-indexer, document-lister, admin) now use **redis-py 7.3.0** (upgraded from 4.x).

**Server compatibility:**

| Redis server version | Compatible with redis-py 7.3.0 | Notes |
|---------------------|-------------------------------|-------|
| Redis 6.x           | ✅ Yes                         | Fully compatible; recommended minimum |
| Redis 7.x           | ✅ Yes                         | Full feature support; recommended for new deployments |
| Redis 5.x or older  | ⚠️ Untested                   | May work but not validated |

**Operator actions:**

- No Redis server upgrade is mandatory. redis-py 7.3.0 is backward-compatible with Redis 6+ servers.
- For new deployments, Redis 7.x server is recommended to match the client version.
- Connection pool configuration remains unchanged (`ConnectionPool` singleton with double-checked locking).
- `scan_iter()`, `mget()`, and pipeline operations continue to work identically.

**Verifying Redis compatibility after upgrade:**

```bash
# Check Redis server version
docker compose exec redis redis-cli INFO server | grep redis_version

# Verify service health after deploying v1.6.0
curl -s http://localhost:8080/health | jq .
```

### ESLint 10 and react-hooks 7

ESLint has been upgraded from v9 to v10 with the react-hooks plugin upgraded to v7.

**Impact on operators:** None. This is a development-only toolchain change with no runtime impact.

**Impact on contributors:**

- ESLint 10 uses flat config format (`eslint.config.js`), continuing from the v9 migration in v1.4.0.
- react-hooks v7 enforces stricter hook dependency rules. Contributors should run `npm run lint` before submitting PRs.

### Frontend code quality fixes

- `useRef` usage corrected across components to pass TypeScript strictNullChecks.
- URL search parameters standardized for consistent behavior with the URL-based search state introduced in v1.2.0.

**Impact on operators:** None. These are internal code quality improvements with no configuration or behavioral changes.

### Test coverage improvements

- **solr-search:** 231 tests (up from 198 in v1.5.0), 94.76% coverage. 38 new tests cover the `/v1/books` endpoint comprehensively.
- **aithena-ui:** 212 tests (up from 132 in v1.5.0), including new i18n tests for locale switching and translation completeness.
- **Total across all services:** 640 tests (up from 579 in v1.5.0).

### Upgrade procedure for v1.6.0

1. Pull the latest images:
   ```bash
   docker compose pull
   ```
2. Restart the stack:
   ```bash
   docker compose up -d
   ```
3. Verify services are healthy:
   ```bash
   curl -s http://localhost:8080/health | jq .
   ```
4. Open the UI and verify the language switcher appears in the header.
5. No database migrations, no configuration changes, no Redis server upgrade required.

### Rollback procedure for v1.6.0

To roll back to v1.5.0:

1. Stop the current stack:
   ```bash
   docker compose down
   ```
2. Switch to v1.5.0 images:
   ```bash
   # Update image tags in docker-compose.yml to v1.5.0, or:
   git checkout v1.5.0 -- docker-compose.yml
   docker compose pull
   docker compose up -d
   ```
3. No data migration rollback needed — v1.6.0 makes no schema changes.

## Deployment Updates for v1.7.0 (Quality & Infrastructure)

v1.7.0 is a quality and infrastructure release focusing on CI/CD robustness, data persistence consistency, and internationalization foundation. This section covers operator-relevant changes and deployment validation.

### localStorage key standardization and auto-migration

v1.7.0 renames the language preference storage key from `aithena-locale` to `aithena.locale` for consistency.

**What changed:**

- UI now reads and writes language preference to `aithena.locale` (dot-notation) instead of `aithena-locale` (hyphen-notation).
- Auto-migration logic: on first load after v1.7.0 upgrade, the application checks for the old `aithena-locale` key and migrates it to `aithena.locale` automatically.
- Existing users retain their language preference without any action.

**Impact on operators:**

- No environment variables, configuration files, or database changes needed.
- No user action required — the migration is silent and happens on first app load.
- The `aithena.locale` key is the new standard; new deployments use it from startup.

**Verifying migration after upgrade:**

```bash
# Open the app in a browser and check the developer console (F12 → Application → Storage → Local Storage)
# Look for the new key 'aithena.locale' after the app loads
# The old 'aithena-locale' key should be gone if auto-migration succeeded
```

**New deployments:**

Fresh v1.7.0 deployments use `aithena.locale` from first startup. No old key exists, so no migration occurs.

### Page-level internationalization extraction

v1.7.0 extends i18n to all page components and the application shell.

**What changed:**

- All UI strings in `SearchPage`, `LibraryPage`, `UploadPage`, `LoginPage`, `AdminPage`, and `App.tsx` are now extracted and use `react-intl` for rendering.
- New strings are registered in the locale files (en, es, ca, fr) but default to English.
- The application is now fully i18n-ready at the component and page layer.

**Impact on operators:**

- No configuration changes, no new environment variables.
- No visible behavior change — the UI renders identically in English (default language).
- If operators have deployed locale files or custom translations, all new page strings will appear in English until translated.

**Impact on contributors:**

Contributors can now add translations for page-level strings by editing the locale files in `src/aithena-ui/src/locales/`.

**Verifying page i18n after upgrade:**

```bash
# Switch language using the LanguageSwitcher (top-right corner)
# Verify that page text updates correctly for all 4 languages (en, es, ca, fr)
# Check browser console for any missing translation warnings
```

### Dependabot CI improvements

v1.7.0 upgrades the Dependabot auto-merge workflow to Node 22 and adds explicit failure handling.

**What changed:**

- `dependabot-automerge.yml` now runs on Node 22 instead of Node 20 (the last holdout).
- Removed `continue-on-error: true` from the auto-merge step; failures now trigger explicit labeling and comments for visibility.
- Enhanced heartbeat workflow (`squad-heartbeat.yml`) detects Dependabot PRs and routes them to the appropriate squad member by dependency domain.

**Impact on operators:**

- No direct operator impact — these are CI/CD changes internal to GitHub Actions.
- The heartbeat workflow may route more Dependabot PRs to maintainers with clearer signals about which domain (Node, Python, Docker) owns the dependency.

**Verifying CI after upgrade:**

- Dependabot auto-merge will continue to work for qualifying PRs (automerge label, passing CI, no conflicts).
- If auto-merge fails, the PR is now labeled and commented with clear failure reasons instead of silent skips.

### Deployment checklist for v1.7.0

1. **Pre-upgrade:**
   - Verify all services are healthy: `curl -s http://localhost/health`
   - Note any active Dependabot PRs for manual review post-upgrade

2. **Upgrade:**
   ```bash
   docker compose pull
   docker compose up -d
   ```

3. **Post-upgrade validation:**
   - Check that the app loads and displays in your preferred language
   - Switch languages using the LanguageSwitcher to verify all page text updates
   - Verify the new `aithena.locale` key appears in browser localStorage after the first page load
   - Confirm no console warnings about missing translations
   - Check `docker compose ps` to ensure all services are running

4. **No rollback-specific actions needed:**
   - All v1.7.0 changes are additive (new key name, new extracted strings, CI improvements).
   - If you roll back to v1.6.0, the app will recreate the old `aithena-locale` key on first load.

### Rollback procedure for v1.7.0

To roll back to v1.6.0:

1. Stop the current stack:
   ```bash
   docker compose down
   ```
2. Switch to v1.6.0 images:
   ```bash
   git checkout v1.6.0 -- docker-compose.yml
   docker compose pull
   docker compose up -d
   ```
3. No data migration rollback needed — v1.7.0 makes no schema or volume changes. Note: v1.6.0 code reads only the old `aithena-locale` key, so after rollback it will not find the migrated `aithena.locale` key. Users who switched languages during v1.7.0 will revert to browser locale detection on their next visit. This is a cosmetic reset, not data loss.

## Deployment Updates for v1.8.1 (Bug Fixes & Stability)

v1.8.1 is a patch release addressing four critical bugs discovered after v1.8.0: incomplete i18n translations, admin login loop, incorrect service status reporting, and version display errors. This section covers operator-relevant changes and deployment validation.

### Incomplete i18n translations (#564)

v1.8.1 completes internationalization coverage for all user-facing pages.

**What changed:**

- Search, Library, and Upload pages now have all UI strings extracted and integrated into the i18n translation system.
- All hardcoded English strings on these pages have been replaced with `react-intl` message keys.
- Full multilingual support (en, es, ca, fr) is now available on all pages.

**Impact on operators:**

- No environment variables, configuration files, or database changes needed.
- Users switching languages will see all UI text in their selected language, including page headers, labels, button text, and placeholder strings.
- No migration or special deployment steps required.

**Verifying i18n after upgrade:**

```bash
# Open the app and switch language using the LanguageSwitcher
# Visit each page (Search, Library, Upload) and confirm all text is translated
# Check that no English hardcoded strings remain on these pages
# Verify browser console shows no missing translation warnings
```

### Admin page login loop fix (#561)

v1.8.1 fixes the authentication flow preventing admin dashboard access.

**What changed:**

- Admin (Streamlit) page authentication flow now works correctly without login redirects.
- Session state persists across admin page navigation.

**Impact on operators:**

- No configuration changes, no new environment variables.
- Administrators can now access the admin dashboard without being stuck in a login loop.
- Session authentication is now reliable.

**Verifying admin access after upgrade:**

```bash
# Navigate to the Admin tab in the application
# Log in if prompted
# Verify that login succeeds and the admin dashboard displays
# Verify that you can navigate within the admin dashboard without being redirected to login
# Reload the page and confirm the session persists
```

### Service status reporting improvements (#563)

v1.8.1 enhances the status endpoint to report all critical services accurately.

**What changed:**

- The status endpoint now reports health for Solr (all 3 nodes), ZooKeeper (all 3 nodes), RabbitMQ, embeddings-server, and Redis.
- The Stats page UI now displays accurate real-time status for all services.
- RabbitMQ is no longer incorrectly reported as down when it is actually healthy.

**Impact on operators:**

- No configuration changes needed.
- Monitoring and troubleshooting become more accurate — operators see true service status instead of false negatives.
- The status endpoint can be used for health monitoring and alerting.

**Verifying status reporting after upgrade:**

```bash
# Open the Status tab in the application
# Verify that all services (Solr, ZooKeeper, RabbitMQ, embeddings-server, Redis) are listed
# Confirm that healthy services show a healthy indicator (not "down")
# If any service is actually down, verify it shows as down (not false healthy indicator)
# Test by stopping a service and confirming the status updates correctly
```

### Version display correction (#569)

v1.8.1 fixes version reporting in the application.

**What changed:**

- The application version display now shows the actual deployed release value.
- Version information is updated and consistent across the application.

**Impact on operators:**

- No configuration changes needed.
- Version reporting is now accurate for monitoring and troubleshooting.

**Verifying version display after upgrade:**

```bash
# Check the application version display — it should show v1.8.1
# Reload the page and confirm the version remains correct
```

### Deployment checklist for v1.8.1

1. **Pre-upgrade:**
   - Verify all services are healthy: `curl -s http://localhost/health`
   - Back up any user accounts or custom admin configurations

2. **Upgrade:**
   ```bash
   docker compose pull
   docker compose up -d
   ```

3. **Post-upgrade validation:**
   - Open the application and verify the footer displays v1.8.1
   - Test the Status tab — all services should be listed and show accurate status
   - Navigate to the Admin tab and verify login succeeds without redirects
   - Switch language and verify all pages display translated text
   - Check `docker compose ps` to ensure all services are running
   - Check `docker compose logs` for any errors or warnings

4. **No rollback-specific actions needed:**
   - All v1.8.1 changes are backward-compatible bug fixes.
   - If you roll back to v1.8.0, the app will work correctly but with the four bugs re-present.

### Rollback procedure for v1.8.1

To roll back to v1.8.0:

1. Stop the current stack:
   ```bash
   docker compose down
   ```
2. Switch to v1.8.0 images:
   ```bash
   git checkout v1.8.0 -- docker-compose.yml
   docker compose pull
   docker compose up -d
   ```
3. No data migration rollback needed — v1.8.1 makes no schema or volume changes. The four bugs will reappear (i18n, admin login, status display, version), but data integrity is unchanged.

## Auth Database Management

### Schema versioning

The authentication database (`AUTH_DB_PATH`, default `/data/auth/users.db`) tracks its own version in a `schema_version` table. Every time `solr-search` starts it checks the current version and applies any pending migrations automatically — no manual intervention required.

You can inspect the current schema version at any time:

```bash
docker compose exec solr-search sqlite3 /data/auth/users.db "SELECT * FROM schema_version ORDER BY version;"
```

### Migration framework

Forward-only migrations live in `src/solr-search/migrations/` as Python modules named `mNNNN_<description>.py`. Each module exposes:

| Attribute | Type | Purpose |
|---|---|---|
| `VERSION` | `int` | Target schema version (must be > all previous) |
| `DESCRIPTION` | `str` | Human-readable summary |
| `upgrade(conn)` | function | DDL/DML using the provided `sqlite3.Connection` |

Migrations run inside a transaction — do **not** call `conn.commit()`. The framework handles commit and records the version after success.

To add a new migration, copy `migrations/template.py` to a new file:

```bash
cp src/solr-search/migrations/template.py src/solr-search/migrations/m0002_add_email.py
```

Edit the file to set `VERSION`, `DESCRIPTION`, and implement `upgrade()`. On next startup the migration will apply automatically.

### Backup

The auth database is a single SQLite file. Use the included backup script for a safe, non-locking snapshot:

```bash
# Inside the container (recommended)
docker compose exec solr-search /app/scripts/backup_auth_db.sh

# Custom backup directory
docker compose exec solr-search /app/scripts/backup_auth_db.sh /data/auth/my-backups

# From the host (if the volume is bind-mounted)
sqlite3 /path/to/auth/users.db ".backup '/path/to/backup/users_backup.db'"
```

The script uses SQLite's `.backup` command, which creates a consistent snapshot without locking the database. Backups are written to `/data/auth/backups/` by default with UTC timestamps.

**Scheduled backups:** Add a cron entry on the Docker host:

```cron
0 2 * * * docker compose -f /path/to/docker-compose.yml exec -T solr-search /app/scripts/backup_auth_db.sh
```

### Restore

To restore from a backup:

```bash
# 1. Stop the service
docker compose stop solr-search

# 2. Replace the database file
cp /data/auth/backups/users_20250115T020000Z.db /data/auth/users.db

# 3. Restart — migrations will re-apply if the backup is from an older version
docker compose start solr-search
```

> **Note:** Restoring an older backup may lose user accounts created after that backup. The migration framework will automatically apply any missing migrations on startup.

### Docker volume considerations

The auth database directory (`/data/auth/`) is bind-mounted from the host. Key points:

- The `entrypoint.sh` script ensures correct ownership (`app:app`, UID 1000) on startup.
- **Always back up before upgrading** — while migrations are forward-only and additive, a backup lets you roll back if needed.
- Named Docker volumes vs. bind mounts: bind mounts are recommended for the auth DB because they make backup and restore trivial from the host filesystem.

---

## Deployment Updates for v1.9.0 (User Management & Security)

v1.9.0 is a major release introducing full user management (CRUD API + UI), role-based access control (RBAC), strong password policies, and multiple security fixes. This section covers operator-relevant changes and deployment validation.

### User Management System

v1.9.0 adds complete user lifecycle management with role-based access control.

#### New Features

- **User Management API** — `/v1/auth/` endpoints for user CRUD (register, list, update, delete)
- **User Management UI** — `/admin/users` page for admin operations, `/profile` page for user self-service
- **Three-role RBAC** — `admin` (full access), `user` (search/upload), `viewer` (read-only search)
- **Default admin seeding** — `admin` user automatically created on first startup if no users exist
- **Password policy** — Enforced minimum 10 characters, 3+ complexity categories, no username in password

#### Deployment checklist for v1.9.0

1. **Backup existing auth database:**
   ```bash
   docker compose exec solr-search /app/scripts/backup_auth_db.sh
   ```

2. **Start the v1.9.0 stack:**
   ```bash
   git fetch origin
   git checkout v1.9.0
   docker compose pull
   docker compose up -d
   ```

3. **Verify default admin user created:**
   ```bash
   docker compose logs solr-search | grep -i "default admin"
   ```

4. **Test admin access:**
   - Open http://localhost/ and log in with `admin` / (password from installer or generated)
   - Navigate to `/admin/users` — should display user list
   - Create a new user with strong password (10+ characters, at least 3 of 4 categories: uppercase, lowercase, digits, special chars)

5. **Test role-based access:**
   ```bash
   # As admin: full access to /admin/users
   # As user: access to search/upload, not admin features
   # As viewer: access to search only, no upload
   ```

6. **Verify PDF viewer:**
   - Search for a document and click to open
   - PDF should render in iframe without X-Frame-Options errors

7. **Test login rate limiting:**
   - Send 6 failed login attempts within 60 seconds
   - Confirm 429 Too Many Requests response on the 6th attempt

8. **Check embeddings server offline mode:**
   ```bash
   docker compose logs embeddings-server | grep -E "(offline|HF_HUB_OFFLINE)"
   ```

### Password Policy Changes

**Breaking change:** Minimum password length increased from 8 to 10 characters.

Existing users with passwords created under the old 8-character policy may be unable to change their password until an administrator resets it if their current password does not meet the new strong policy (10+ characters, 3+ complexity categories). Use the CLI tool:

```bash
docker compose exec solr-search python reset_password.py --username <username>
```

The tool generates a secure 32-character random password if `--password` is omitted.

**Complexity categories:**
- Uppercase letters (A–Z)
- Lowercase letters (a–z)
- Digits (0–9)
- Special characters (!@#$%^&*)

Passwords must contain at least 3 of these 4 categories. Examples:
- ✅ `MyPassword123` (uppercase, lowercase, digits)
- ✅ `Password12` (uppercase, lowercase, digits)
- ✅ `pass!word123` (lowercase, special, digits)
- ✅ `MyP@ssw0rd` (uppercase, lowercase, special, digits)
- ❌ `password` (lowercase only)

### Rate Limiting Improvements

The login rate limiter now correctly identifies client IP addresses via the `X-Forwarded-For` header set by nginx. Previously, all users behind the proxy appeared as a single IP (`172.x.x.x`), making rate limits ineffective.

**Configuration:** Rate limits are built-in; no changes required:
- Limit: 5 failed login attempts per 60 seconds per IP
- Response: `429 Too Many Requests`
- Auto-reset: 60-second window slides

### Security Fixes

v1.9.0 includes four critical security improvements:

1. **PDF viewer iframe fix** — Added `X-Frame-Options SAMEORIGIN` to `/documents/` location, allowing same-origin iframe embedding for PDF viewer
2. **Embeddings offline mode** — Enforced `HF_HUB_OFFLINE=1` to prevent outbound HuggingFace Hub requests
3. **Rate limiter IP spoofing** — Fixed to read real client IP from nginx `X-Forwarded-For` header
4. **Password policy consistency** — Integrated strong policy validation into CLI password reset tool

### Data Migration

v1.9.0 automatically applies schema migrations on startup. The auth database tracks its own version:

```bash
# Check current schema version
docker compose exec solr-search sqlite3 /data/auth/users.db "SELECT * FROM schema_version ORDER BY version DESC LIMIT 1;"
```

Migrations are forward-only and safe for production. If you roll back to v1.8.x, the schema is backwards-compatible.

### Troubleshooting v1.9.0 Deployment

**Issue:** Admin user not created on startup
- **Cause:** Existing auth database from v1.8.x
- **Solution:** The admin seeding only happens if no users exist. This is intentional — your existing admin user is preserved. Log in with your existing credentials.

**Issue:** Login returns 401 even with correct credentials
- **Cause:** Invalid credentials or authentication service misconfiguration
- **Solution:** Verify credentials and check service logs: `docker compose logs solr-search | grep -i auth`

**Issue:** PDF viewer shows blank iframe
- **Cause:** Old nginx cache with wrong X-Frame-Options header
- **Solution:** Clear browser cache or restart nginx: `docker compose restart nginx`

**Issue:** Users can access admin features they shouldn't
- **Cause:** User role not enforced correctly
- **Solution:** Restart solr-search and verify RBAC test results in logs: `docker compose logs solr-search | grep -i rbac`

### Upgrade procedure for v1.9.0

**From v1.8.x:**

```bash
# 1. Backup
docker compose exec solr-search /app/scripts/backup_auth_db.sh

# 2. Pull new version
git fetch origin
git checkout v1.9.0

# 3. Start the stack
docker compose pull
docker compose up -d

# 4. Verify migrations completed
docker compose logs solr-search | grep -i "migration\|successfully"

# 5. Test admin and user creation
curl -X GET http://localhost:8080/v1/auth/users \
  -H "Authorization: Bearer <token>" | jq .

# 6. Reset weak passwords
docker compose exec solr-search python reset_password.py --username <username>
```

### Rollback procedure for v1.9.0

To roll back to v1.8.1:

```bash
# 1. Stop the current stack
docker compose down

# 2. Restore from backup (if you have one)
docker compose exec solr-search sqlite3 /data/auth/users.db ".restore /path/to/backup.db"

# 3. Checkout v1.8.1
git checkout v1.8.1

# 4. Restart
docker compose pull
docker compose up -d
```

**Data integrity:** v1.9.0 schema is backwards-compatible with v1.8.x. Existing user accounts, passwords, and roles are preserved. If you restore an older backup, you lose any user accounts created after that backup was taken.

---

## Metadata Editing

Aithena allows administrators to correct or enrich document metadata directly, without re-indexing files. Changes are persisted in both Solr (for immediate search impact) and Redis (to survive re-indexing).

### Prerequisites

- An admin user account (role `admin`)
- The `ADMIN_API_KEY` environment variable configured in the deployment

### Single document edit

Edit one document at a time from the UI detail view or via the API:

```
PATCH /v1/admin/documents/{doc_id}/metadata
X-API-Key: <your-admin-key>
Authorization: Bearer <admin-jwt>

{
  "title": "Corrected Title",
  "author": "Corrected Author",
  "year": 2020,
  "category": "Science Fiction",
  "series": "Foundation"
}
```

All fields are optional — only include the fields you want to change. The response confirms which fields were updated:

```json
{
  "id": "doc-id",
  "updated_fields": ["title", "author", "year", "category", "series"],
  "status": "ok",
  "message": "Metadata updated in Solr and override store"
}
```

### Batch edit by document IDs

Update multiple documents at once (up to 1 000 IDs per request):

```
PATCH /v1/admin/documents/batch/metadata
X-API-Key: <your-admin-key>
Authorization: Bearer <admin-jwt>

{
  "document_ids": ["doc-1", "doc-2", "doc-3"],
  "updates": {
    "category": "History"
  }
}
```

The response reports partial failures:

```json
{
  "matched": 3,
  "updated": 2,
  "failed": 1,
  "errors": [
    { "document_id": "doc-3", "error": "Document does not exist" }
  ]
}
```

### Batch edit by query

Update all documents matching a Solr query (up to 5 000 results):

```
PATCH /v1/admin/documents/batch/metadata-by-query
X-API-Key: <your-admin-key>
Authorization: Bearer <admin-jwt>

{
  "query": "author_s:Asimov",
  "updates": {
    "series": "Foundation"
  }
}
```

### Field validation rules

| Field | Type | Constraint |
|-------|------|-----------|
| `title` | string | Max 255 characters |
| `author` | string | Max 255 characters |
| `year` | integer | 1000–2099 |
| `category` | string | Max 100 characters |
| `series` | string | Max 100 characters |

Whitespace is trimmed automatically. Whitespace-only strings are rejected (422).

### How overrides work

1. **Solr atomic update**: Each field is written to Solr using the `set` operation, preserving all other document fields.
2. **Redis override store**: A JSON record is stored at `aithena:metadata-override:{doc_id}` containing the updated Solr field values, `edited_by`, and `edited_at`. This ensures overrides survive full re-indexing.

### Using the batch edit UI

1. Navigate to the search page and run a search.
2. Select documents using the checkboxes on each book card.
3. Click **Batch Edit** in the selection toolbar.
4. In the batch edit panel, enable the fields you want to change using the toggle checkboxes.
5. Enter new values. Category and series fields offer autocomplete from existing facet values.
6. Review the preview section showing which fields will be updated.
7. Click **Apply Changes** to submit.
8. Review the result summary (updated count, failed count, and error details).

### Troubleshooting

| Symptom | Cause | Resolution |
|---------|-------|------------|
| 401 on PATCH | Missing or invalid `X-API-Key` header | Verify `ADMIN_API_KEY` in `.env` and include it in the request |
| 403 on PATCH | JWT user is not an admin | Log in with an admin account |
| 404 on single edit | Document ID not in Solr | Verify the document was indexed; check `doc_id` spelling |
| 503 on single edit | Redis unavailable | Check Redis health; the Solr update may still have succeeded |
| 504 on single edit | Solr timeout | Check Solr health and load |

## Deployment Updates for v1.10.0 (Book Collections, Metadata Editing, Backup & Restore)

v1.10.0 is a major feature release introducing **user document collections** (personal bookshelves with notes), **admin book metadata editing** (single and batch mode), **folder path faceting** for better navigation, **series field** support for magazine/newspaper grouping, and foundational **backup and restore infrastructure**. This section covers operator-relevant infrastructure changes, new environment variables, and deployment validation.

### New Feature Overview

v1.10.0 adds four significant user-facing features and infrastructure improvements:

1. **User Collections** — Users can create personal reading lists and add notes to books
2. **Book Metadata Editing** — Admins can correct/edit document metadata (title, author, year, category, series)
3. **Folder Path Faceting** — Users can browse and filter by the document library folder structure
4. **Series/Collection Field** — New Solr field for grouping books into series, magazines, and newspapers
5. **BCDR Foundation** — Backup scripts and restore orchestration for critical infrastructure

### Collections Infrastructure: New Volume & Database

v1.10.0 introduces a dedicated SQLite database for user collections at `/data/collections/collections.db`.

#### Docker Compose Changes

The `docker-compose.yml` now includes:

```yaml
volumes:
  collections-db:
    driver: local
    driver_opts:
      type: "none"
      o: "bind"
      device: "${COLLECTIONS_DB_DIR:-/source/volumes/collections-db}"

services:
  solr-search:
    volumes:
      - collections-db:/data/collections  # New mount
    environment:
      - COLLECTIONS_DB_PATH=${COLLECTIONS_DB_PATH:-/data/collections/collections.db}  # New env var
```

#### Environment Variables (New in v1.10.0)

| Variable | Default | Purpose |
|----------|---------|---------|
| `COLLECTIONS_DB_PATH` | `/data/collections/collections.db` | Path to SQLite collections database inside container |
| `COLLECTIONS_DB_DIR` | `/source/volumes/collections-db` | Host bind-mount directory for collections database (production deployments) |
| `COLLECTIONS_NOTE_MAX_LENGTH` | `1000` | Maximum character length for per-document notes in collections |

#### Collections Database Schema

The collections database includes two tables:

```sql
CREATE TABLE collections (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE collection_items (
    id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    position INTEGER DEFAULT 0,
    note TEXT DEFAULT '',
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (collection_id) REFERENCES collections(id) ON DELETE CASCADE,
    UNIQUE(collection_id, document_id)
);
```

The schema is automatically initialized on first `solr-search` startup via a migration system (no manual SQL required).

### Solr Schema Changes: New `series_s` Field

v1.10.0 adds a new `series_s` field to the Solr schema to support grouping documents into series, magazine runs, and newspaper titles.

#### Field Definition

```xml
<field name="series_s" type="string" multiValued="false" indexed="true" stored="true"/>
```

This field is:
- **Indexed**: Can be searched and faceted
- **Stored**: Returned in search results
- **Single-valued**: One series per document

#### Facet Configuration

The `series_s` field is automatically configured as a facet in the search API. Users can filter by series alongside existing facets (author, category, language, folder).

#### Populating the Series Field

- **During indexing**: The `document-indexer` can populate `series_s` from folder structure or filename patterns (if configured)
- **Via metadata edit API**: Admins can manually set or correct the series for individual documents or batches
- **Re-index safety**: Manual series edits persist via Redis overrides (see Metadata Override Persistence below)

### Folder Path Facet

v1.10.0 exposes the existing `folder_path_s` field as a first-class facet in the search UI and API.

#### API Changes

The `/v1/search` and `/v1/facets` endpoints now return folder facet data:

```json
{
  "facets": {
    "folder": [
      {"value": "en/Science Fiction", "count": 125},
      {"value": "en/History", "count": 89},
      {"value": "es/Ciencia Ficción", "count": 47}
    ]
  }
}
```

#### Frontend Behavior

- **Hierarchical tree display**: Folders are shown as an expandable/collapsible tree in the sidebar
- **Multi-select**: Users can select multiple folders to filter results (AND logic)
- **Batch operations**: Admins can select all documents in a folder for batch metadata editing

### Book Metadata Editing: New API & Persistence

v1.10.0 adds admin-only APIs for editing document metadata with Solr atomic updates and Redis override persistence.

#### Single Document Edit Endpoint

```
PATCH /v1/admin/documents/{doc_id}/metadata
```

Request body (all fields optional; at least one required):

```json
{
  "title": "Corrected Title",
  "author": "Author Name",
  "year": 1984,
  "category": "Science Fiction",
  "series": "Foundation"
}
```

Response:

```json
{
  "id": "doc_id",
  "updated_fields": ["title", "year"],
  "status": "ok"
}
```

#### Batch Edit by Document IDs

```
PATCH /v1/admin/documents/batch/metadata
```

Request body:

```json
{
  "document_ids": ["id1", "id2", "id3"],
  "updates": {
    "year": 2023,
    "series": "Nature Magazine"
  }
}
```

#### Batch Edit by Solr Query

```
PATCH /v1/admin/documents/batch/metadata-by-query
```

Request body:

```json
{
  "query": "folder_path_s:\"en/Science Fiction\"",
  "updates": {
    "category": "Science Fiction"
  }
}
```

#### Environment Variables

Metadata override persistence uses Redis and is permanently enabled. No environment variables control it.

#### How Metadata Overrides Work

1. **Immediate Solr Update**: When an admin edits a document, a Solr atomic update is applied immediately using the `set` operation. The updated metadata is returned in search results within milliseconds.

2. **Redis Override Persistence**: A JSON record is stored at `aithena:metadata-override:{doc_id}` containing:
   - All updated field values
   - `edited_by` — the admin user who made the edit
   - `edited_at` — timestamp of the edit

3. **Re-index Survival**: When the document is re-indexed (e.g., after re-scanning the library folder), the `document-indexer` checks for Redis overrides and applies them on top of auto-detected metadata. This ensures manual edits survive document reprocessing.

4. **Field Mapping**: The API accepts friendly field names (title, author, year, category, series) which are mapped to Solr fields:
   - `title` → `title_s`, `title_t`
   - `author` → `author_s`, `author_t`
   - `year` → `year_i`
   - `category` → `category_s`
   - `series` → `series_s` (new in v1.10.0)

### Redis Configuration for Metadata Overrides

Metadata overrides use Redis keys with the pattern `aithena:metadata-override:{document_id}`. Ensure Redis is configured with:

- **Memory policy**: `maxmemory-policy=noeviction` (or `allkeys-lru`) — overrides should not be evicted
- **Persistence**: Enabled (RDB snapshots or AOF)
- **No TTL**: Overrides are stored permanently (TTL=0) unless explicitly configured otherwise

Check Redis memory usage for large libraries:

```bash
docker compose exec redis redis-cli INFO memory

# Expected overhead: ~1 KB per override (assuming ~100 bytes per metadata override JSON)
# For a 50,000-document library with 10% edited: ~5 MB
```

### Backup & Restore Foundation (v1.10.0 BCDR Phase 1)

v1.10.0 introduces the foundational **Backup & Restore** infrastructure with three-tier backup scripts and a restore orchestrator.

#### What's Being Backed Up

| Tier | What | Frequency | Retention | RPO |
|------|------|-----------|-----------|-----|
| **Critical** | Auth DB (`users.db`), Collections DB (`collections.db`), .env secrets | Every 30 min | 7 days | < 1 hour |
| **High** | Solr index, ZooKeeper state | Daily (2 AM UTC) | 30 days | < 24 hours |
| **Medium** | Redis RDB dump, RabbitMQ definitions | Daily (3 AM UTC) | 14 days | < 4 hours |

#### Backup Scripts

v1.10.0 includes three executable scripts in `scripts/`:

```bash
./scripts/backup-critical.sh   # Tier 1: Auth + Collections DBs + secrets (encrypted)
./scripts/backup-high.sh       # Tier 2: Solr + ZooKeeper volumes
./scripts/backup-medium.sh     # Tier 3: Redis + RabbitMQ state
./scripts/backup.sh            # Orchestrator: runs all three tiers
```

The orchestrator script includes a cron-friendly interface:

```bash
# Backup all tiers to default location
./scripts/backup.sh

# Backup only critical tier
./scripts/backup.sh --tier critical

# Dry-run (log actions without writing files)
./scripts/backup.sh --dry-run

# Custom destination
./scripts/backup.sh --dest /mnt/backup-storage
```

#### Restore Orchestrator

A new `./scripts/restore.sh` script orchestrates the restore process:

```bash
# Restore all components from latest backup
./scripts/restore.sh --from /path/to/backup/critical-latest.db

# Restore specific component
./scripts/restore.sh --from /path/to/backup --component auth

# Dry-run (show what would be restored)
./scripts/restore.sh --from /path/to/backup --dry-run
```

#### Post-Restore Verification

Backup/restore operations run the `./tests/verify-restore.sh` verification suite to ensure:
- All services report healthy
- Admin UI loads
- Authentication works
- Search queries return results
- Redis and RabbitMQ are accessible
- Solr collection status shows healthy replicas

#### Backup Directory Structure

Backups are organized by tier:

```
/source/backups/
├── critical/            # Auth DB, Collections DB, .env (encrypted)
│   ├── auth-20260321-0230.db.gpg
│   ├── auth-20260321-0230.db.gpg.sha256
│   ├── collections-20260321-0230.db.gpg
│   └── env-20260321-0230.gpg
├── high/                # Solr snapshot metadata
│   ├── books-20260321-0200.snap
│   └── books-20260321-0200.snap.sha256
├── zookeeper/           # ZooKeeper tar archives
│   └── zoo-data-20260321-0200.tar.gz
└── medium/              # Redis + RabbitMQ backups
    ├── redis-20260321-0300.rdb
    └── rabbitmq-defs-20260321-0300.json
```

#### Encryption

Critical-tier backups (auth, collections, .env) are encrypted with GPG using AES256:

```bash
# Encryption happens automatically during backup
# Decryption requires the encryption key:
gpg --batch --passphrase-file /etc/aithena/backup.key --output restore.db \
    --decrypt auth-20260321-0230.db.gpg
```

The encryption key file (`/etc/aithena/backup.key`) should be:
- Generated during initial setup (not committed to git)
- Backed up to a secure vault separate from backup files

#### Scheduled Backups (Cron)

To enable automated backups, add cron entries:

```bash
# Run as the aithena or root user
*/30 * * * *  /path/to/aithena/scripts/backup-critical.sh   # Every 30 min
0 2 * * *     /path/to/aithena/scripts/backup-high.sh        # Daily 2 AM UTC
0 3 * * *     /path/to/aithena/scripts/backup-medium.sh      # Daily 3 AM UTC
```

Logs are written to `/var/log/aithena-backup-*.log`.

### Deployment Checklist for v1.10.0

1. **Backup existing data (recommended):**
   ```bash
   # Backup critical databases using the new backup script
   ./scripts/backup-critical.sh
   ```

2. **Update to v1.10.0:**
   ```bash
   git fetch origin
   git checkout v1.10.0
   docker compose pull
   docker compose up -d
   ```

3. **Verify collections database initialized:**
   ```bash
   docker compose logs solr-search | grep -i "collections.*migration\|collections.*initialized"
   ```

4. **Test metadata edit endpoint:**
   ```bash
   # Find a document ID from a search result
   curl -X PATCH "http://localhost/v1/admin/documents/{doc_id}/metadata" \
     -H "X-API-Key: $ADMIN_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"year": 1984}'
   ```

5. **Verify folder facet in search:**
   - Open http://localhost and run a search
   - Look for "📁 Folder" facet in the sidebar alongside Author, Category, etc.
   - Expand a folder and verify document counts

6. **Test user collections:**
   - Search for documents
   - Click "Save to collection" on a book card
   - Create a new collection and add documents
   - Navigate to `/collections` and verify the collection appears

7. **Verify series field populated:**
   ```bash
   # Check if any documents have series_s populated
   curl "http://localhost/v1/search?q=*&rows=1" | jq '.results[0].series'
   ```

8. **Test metadata override persistence:**
   - Edit a document's metadata via the UI or API
   - Manually trigger a document re-index (admin panel)
   - Verify the metadata edit persists

9. **Set up automated backups (optional):**
   ```bash
   sudo bash -c 'crontab -e'
   # Add cron entries for backup scripts (see Scheduled Backups section above)
   ```

10. **Run backup test:**
    ```bash
    ./scripts/backup.sh --dry-run
    ./scripts/backup.sh --tier critical
    ls -la /source/backups/critical/
    ```

### Configuration Changes Summary

#### New Environment Variables

| Variable | Service | Default | Notes |
|----------|---------|---------|-------|
| `COLLECTIONS_DB_PATH` | solr-search | `/data/collections/collections.db` | Path inside container |
| `COLLECTIONS_DB_DIR` | docker-compose | `/source/volumes/collections-db` | Host bind-mount directory |
| `COLLECTIONS_NOTE_MAX_LENGTH` | solr-search | `1000` | Max characters per note |

#### Updated Solr Schema

- **New field**: `series_s` (string, indexed, stored)
- **New facet**: `folder_path_s` (already existed in schema, now exposed as facet)
- **Updated facet configuration**: `/facets` and `/search` endpoints now return folder and series facets

### Migration & Backward Compatibility

v1.10.0 is **fully backward-compatible** with v1.9.0:

- Existing documents are unaffected (series_s is optional)
- Collections database is created on first startup (no data loss)
- Metadata edit endpoints are new — no existing workflows break
- Folder faceting is additive — existing facets unchanged

### Troubleshooting

#### Collections Database Issues

| Symptom | Cause | Resolution |
|---------|-------|------------|
| 503 on collection API | Collections DB not initialized | Check logs: `docker compose logs solr-search | grep collections` |
| Collections persist but metadata doesn't | Redis unavailable | Verify Redis health: `docker compose exec redis redis-cli ping` |
| "Cannot access /data/collections" | Volume mount permission denied | Check file permissions: `ls -la /source/volumes/collections-db/` |

#### Metadata Editing Issues

| Symptom | Cause | Resolution |
|---------|-------|------------|
| 422 Unprocessable Entity | Field value too long or invalid format | Check field constraints (title ≤255, year 1000-2099) |
| Edit succeeds but Solr still has old value | Atomic update failed silently | Check Solr logs: `docker compose logs solr` |
| Edit survives single request but lost on re-index | Redis override not applied | Verify Redis key: `docker compose exec redis redis-cli GET "aithena:metadata-override:doc_id"` |

#### Folder Facet Issues

| Symptom | Cause | Resolution |
|---------|-------|------------|
| Folder facet not appearing | Field not in facet configuration | Redeploy with updated solr-search code |
| Folder counts incorrect | Stale Solr index | Re-index documents: trigger from admin UI or `document-lister` re-scan |

#### Backup & Restore Issues

| Symptom | Cause | Resolution |
|---------|-------|------------|
| Backup script not found | v1.10.0 not checked out | Verify: `git rev-parse --short HEAD` shows v1.10.0 commit |
| "Permission denied" on backup script | Script not executable | Fix: `chmod +x scripts/backup*.sh scripts/restore.sh` |
| Restore fails with "Backup integrity check failed" | Corrupted backup file | Re-run backup with `--tier critical` to create a fresh copy |

---

## Deployment Updates for v1.11.0 (Search Enhancements, Thumbnails, Book Detail Endpoint)

See the full [v1.11.0 release notes](https://github.com/jmservera/aithena/releases/tag/v1.11.0) for additional details.

### Key Changes

v1.11.0 introduces search improvements, thumbnail generation, and a book detail retrieval endpoint:

1. **Sentence-Boundary-Aware Chunking** — Indexing now respects sentence boundaries when breaking text into chunks
2. **Chunking Parameter Defaults Changed** — Default chunk size reduced from 400 to 90 words, overlap from 50 to 10 words
3. **Thumbnail Generation** — During indexing, first-page thumbnails are extracted and stored as `.thumb.jpg` alongside PDFs
4. **Thumbnail Serving** — nginx serves thumbnails at `/thumbnails/...`; the `thumbnail_url` field is indexed in Solr and returned in search results
5. **Book Detail Endpoint** — New `GET /v1/books/{id}` endpoint retrieves complete book metadata
6. **Nginx Routing Cleanup** — Removed dead `admin` upstream; `/admin/streamlit` now redirects to `/admin/`

### Critical Upgrade Action: Full Reindex Required

⚠️ **The chunking parameter changes (400/50 → 90/10 words) require a full reindex after upgrading to v1.11.0.**

Without a reindex:
- Documents indexed before v1.11.0 will retain the old chunking (400/50)
- Newly indexed documents will use the new chunking (90/10)
- This creates inconsistent search behavior across your index

**To reindex after upgrade:**

1. Deploy v1.11.0 and confirm all services are healthy
2. Follow your existing reindex procedure to clear the Solr index and trigger full reindexing via `document-lister`
3. Monitor `document-indexer` logs to confirm all documents process without errors
4. Verify the RabbitMQ queue is empty before relying on search results

**Note:** Operators should follow their site-specific reindex procedures. The exact commands depend on your deployment environment and operational practices.

### Thumbnail Storage and Serving

Thumbnails are generated automatically during indexing:
- Stored alongside PDFs with the naming pattern `{filename}.thumb.jpg`
- Indexed in Solr's `thumbnail_url` field
- Served by nginx at `/thumbnails/...`
- Returned in `/v1/search` responses when available

Documents indexed before v1.11.0 will have `null` for `thumbnail_url` until reindexed. The UI falls back to a placeholder image when thumbnails are unavailable.

### Book Detail Endpoint

The new `GET /v1/books/{id}` endpoint returns full book metadata (title, author, year, category, series, and other indexed fields).

### Admin Routing

The dead `admin` upstream has been removed from nginx configuration. The `/admin/streamlit` path now redirects to `/admin/`. Existing bookmarks will redirect automatically.

---

## Deployment Updates for v1.12.1 (Bug Fixes & UX Refinements)

v1.12.1 is a maintenance release addressing critical bug fixes and UX refinements from v1.11.0:

### What's Fixed in v1.12.1

1. **Collections API (Issue #897)** — Collections API now uses real backend data by default. The mock data fallback has been removed.
2. **Remember Me Checkbox (Issue #898)** — Login form now includes "Remember me" checkbox for persistent session support.
3. **Text Preview Truncation (Issue #896)** — Search result chunk text is truncated to ~15-20 characters for better readability.
4. **Thumbnail Generation (Issue #894)** — Alpine container now includes missing `libstdc++` library; PyMuPDF thumbnail generation works correctly.

### Key Changes

#### Collections API — Real Data By Default

- `VITE_COLLECTIONS_API` environment variable is no longer required
- Frontend API service calls real backend by default
- No configuration changes needed for operators

#### Container Build Fix

The `src/document-indexer/Dockerfile` now includes C++ runtime libraries:

```dockerfile
RUN apk add --no-cache libstdc++ libgomp libgcc
```

This resolves PyMuPDF import errors and enables thumbnail generation on Alpine Linux.

#### Login Form Update

The login form now includes an optional "Remember me" checkbox:
- **Checked:** Session persists for 30 days
- **Unchecked (default):** Session ends when browser closes

No operator configuration required.

### Backward Compatibility

v1.12.1 is **fully backward-compatible** with v1.11.0:
- Existing collections data is preserved
- No Solr schema changes
- No database migrations required
- No new environment variables required

### Upgrade Procedure

```bash
git fetch origin
git checkout v1.12.1
docker compose pull
docker compose up -d
```

### Deployment Validation Checklist

- [ ] All services start: `docker compose ps`
- [ ] No startup errors in logs: `docker compose logs | grep -i error`
- [ ] Collections feature works with real backend data
- [ ] New documents generate thumbnails during indexing
- [ ] Login form displays "Remember me" checkbox
- [ ] Test collections persistence (create → reload → verify)

---

## v1.13.0 — Offline Deployment & Security Hardening

v1.13.0 is a major release focusing on offline deployment and comprehensive infrastructure security. This section covers new features and configuration requirements.

### Offline Deployment (Air-Gapped Environments)

*New in v1.13.0:* Aithena now supports fully air-gapped deployment with no external network access.

#### Export Offline Bundle

On a machine with internet access, create an offline bundle:

```bash
# From the repository root at v1.13.0
./scripts/export-images.sh
```

This bundles:
- All Docker images (solr, redis, rabbitmq, zookeeper, python services, etc.)
- Python package dependencies
- Build artifacts
- Configuration templates
- Install script and verification utilities

Output: `staging/aithena-offline-v1.13.0.tar.gz`

#### Transfer Bundle

Transfer the bundle to your air-gapped network using approved methods:
- Physical USB drive
- Secure air-gap appliance
- Any non-networked transfer mechanism

#### Deploy from Offline Bundle

On the air-gapped host:

```bash
# 1. Extract the bundle
tar xzf aithena-offline-v1.13.0.tar.gz
cd aithena-offline-v1.13.0

# 2. Install from bundle (requires sudo)
sudo ./install.sh

# 3. Verify services are healthy
./verify.sh

# 4. Configure credentials (if needed)
# Edit .env at /opt/aithena/.env
# Then restart: docker compose up -d

# 5. Monitor services
docker compose ps
docker compose logs -f
```

**Important:** The installer generates all credentials, secrets, and configuration on the target host. This ensures no credentials are leaked or pre-shared across networks.

### Security Hardening in v1.13.0

v1.13.0 introduces comprehensive authentication and authorization hardening. This is a **major security improvement** but requires careful deployment.

#### Before You Upgrade

1. **Read the release notes** section on breaking changes
2. **Backup your `.env` file** (old credentials will not work)
3. **Test in staging first** if possible
4. **Plan for credential rotation** across your team

#### Authentication & Authorization Overview

All internal services now require authentication:

| Service | Auth Method | User Count | Scope |
|---------|-------------|-----------|-------|
| **Solr** | BasicAuth | 3 users | Per-collection ACLs |
| **ZooKeeper** | SASL Digest | 2 users | Per-znode ACLs |
| **RabbitMQ** | User/password | Per-service | Per-queue permissions |
| **Redis** | ACLs | Per-service | Command restrictions |
| **nginx** | TLS (optional) | — | HSTS headers if TLS enabled |

#### Solr Authentication Setup

Solr now uses BasicAuthPlugin. Three user roles are created:

```
solr-admin    → Full cluster and collection admin
solr-indexer  → Index write access
solr-search   → Read-only search access
```

Credentials are injected from `.env` at runtime. To view current Solr users:

```bash
docker compose exec solr-search curl \
  -u solr-admin:$SOLR_ADMIN_PASS \
  http://localhost:8983/api/users
```

#### ZooKeeper SASL Authentication

ZooKeeper cluster nodes authenticate using SASL Digest. This prevents unauthorized config modifications.

Credentials are stored in a JAAS config file injected at startup. No manual configuration needed; the installer handles setup.

#### RabbitMQ Per-Service Credentials

Each service has dedicated RabbitMQ credentials in `.env`:

```
document-lister   → RABBITMQ_LISTER_USER / RABBITMQ_LISTER_PASS
document-indexer  → RABBITMQ_INDEXER_USER / RABBITMQ_INDEXER_PASS
```

These are auto-generated and stored in `.env`. Services authenticate at startup; no manual intervention needed.

#### Redis ACLs

Redis now uses ACLs to restrict dangerous commands. Indexing services can perform safe operations (GET, SET, DEL, LPUSH, RPOP) but cannot:
- Flush databases (`FLUSHDB`, `FLUSHALL`)
- Modify configuration (`CONFIG SET`)
- Shut down Redis (`SHUTDOWN`)

If you use Redis for monitoring or custom integrations, you may need to adjust your ACL rules. Consult the admin manual or release notes.

#### Docker Network Segmentation

*Planned for future releases.* Currently, services run on the default Docker network. Per-service credentials provide logical isolation.

Operators can implement external network policies at the Docker daemon or orchestrator level if needed.

#### Non-Root Container Processes

All custom containers now run as non-root users (UID ≥ 1000):

```bash
docker compose exec solr-search id
# uid=1000(solr-search) gid=1000(solr-search) groups=1000(solr-search)
```

This reduces the blast radius if a container is compromised. Verify file permissions match the new user IDs.

#### Diacritic-Insensitive Search (ASCII Folding)

By default, search is now diacritic-insensitive: "café" matches "cafe". This is an analyzer-level change controlled by the `SOLR_ASCII_FOLDING` environment variable (defaults to true).

After upgrading, test search behavior on your indexed data to validate that the diacritic-insensitive analyzer works as expected for your library.

If you need diacritic-sensitive search, set `SOLR_ASCII_FOLDING=false` in `.env` and restart services.

#### TLS/HSTS Deployment (Optional)

For production deployments, use the provided SSL Compose file:

```bash
docker compose -f docker-compose.yml -f docker-compose.ssl.yml up -d
```

This configuration:
- Enables TLS on nginx
- Adds HSTS headers (1-year max-age, includeSubDomains)
- Automatically renews certificates via Certbot

### Backward Compatibility & Breaking Changes

**v1.13.0 introduces new per-service credentials:**

1. **Credentials Changed:** Services now use per-service credentials for Solr, RabbitMQ, ZooKeeper, and Redis. Run the installer to generate new credentials in `.env`.
2. **Authentication Required:** Services authenticate with Solr, ZooKeeper, RabbitMQ, and Redis. Direct tooling access may require credentials (see admin sections for CLI examples).
3. **Search Behavior:** Diacritic-insensitive search is now default (but configurable).
4. **Network Topology:** Services run on the default Docker network. Per-service credentials provide logical isolation. Network-level segmentation is planned for future releases.

**Migration Path:**

```bash
# 1. Backup current deployment
docker compose down
tar czf backup-v1.12.1.tar.gz docker-compose.*.yml .env

# 2. Upgrade to v1.13.0
git fetch origin
git checkout v1.13.0

# 3. Review and update .env (per-service credentials are now required)
# Compare your current .env with .env.example
# Add missing per-service credential variables if upgrading from v1.12.x

# 4. Pull new images
docker compose pull

# 5. Start with new configuration
docker compose up -d

# 6. Monitor bootstrap
docker compose ps
sleep 30 && docker compose logs | grep -i error
```

If you encounter auth failures during startup:
1. Check `.env` for missing per-service credentials (RABBITMQ_INDEXER_USER, RABBITMQ_LISTER_USER, etc.)
2. Verify service health: `docker compose ps`
3. Review logs: `docker compose logs <service-name>`
4. If needed, regenerate `.env` from `.env.example` and populate with your settings

### Deployment Validation Checklist

Before declaring v1.13.0 production-ready:

**Infrastructure:**
- [ ] All services report healthy: `docker compose ps`
- [ ] No startup errors in logs: `docker compose logs | grep -i error`
- [ ] Services reach healthy state within 60 seconds

**Authentication:**
- [ ] Solr requires auth: `curl http://localhost:8983/api/cluster` → 401
- [ ] Solr allows admin: `curl -u solr-admin:password http://localhost:8983/api/cluster` → 200
- [ ] Redis rejects dangerous commands (if ACL enabled)
- [ ] ZooKeeper cluster formed with SASL enabled

**Search & Collections:**
- [ ] Search for "cafe" → results include "café"
- [ ] Collections feature works (create, add, delete)
- [ ] Full-text search works
- [ ] Semantic search works

**Offline Deployment (if applicable):**
- [ ] Offline bundle exports without network errors
- [ ] Bundle verification passes on air-gapped host
- [ ] Installation completes without external network access
- [ ] Services start and reach healthy state

**Security:**
- [ ] Non-root containers verified: `docker compose exec solr-search id`
- [ ] HSTS headers present (TLS deployments): `curl -I https://... | grep Strict`
- [ ] Credentials stored in `.env` with restricted permissions (0600)

### Upgrade Procedure

```bash
# 1. Stop existing services
git checkout v1.12.2
docker compose down

# 2. Upgrade to v1.13.0
git fetch origin
git checkout v1.13.0

# 3. Update .env with new per-service credentials (if upgrading from < v1.13.0)
# Review and merge .env.example into your current .env
# Add new variables: RABBITMQ_INDEXER_USER, RABBITMQ_LISTER_USER, SOLR_ADMIN_PASS, etc.

# 4. Pull new images
docker compose pull

# 5. Start services
docker compose up -d

# 6. Verify bootstrap
docker compose ps
sleep 30
docker compose logs | grep -i error

# 7. Run validation checks (see checklist above)
```

### Troubleshooting v1.13.0 Authentication Failures

**Problem:** Services fail to start with auth errors.

**Solution:**
```bash
# 1. Check if credentials are in .env
grep SOLR_ADMIN_PASS .env
grep RABBITMQ_INDEXER_USER .env

# 2. If missing, add them to .env with unique values
# Services require per-service credentials to authenticate

# 3. Restart services
docker compose down
docker compose up -d

# 4. Monitor logs
docker compose logs -f
```

**Problem:** External tools (monitoring, backups) cannot reach services.

**Solution:**
1. Update tool configurations with new credentials (from `.env`)
2. Verify network membership: `docker network inspect <network-name>`
3. Update firewall rules if needed
4. Test connectivity: `docker compose exec <service> curl -u user:pass http://target:port/...`

---

## Deployment Updates for v1.15.0

v1.15.0 includes admin portal enhancements, infrastructure hardening, and operator-focused bug fixes. Key changes:

### Admin Portal Redesign

The admin portal (`/admin`) now features a sidebar navigation with organized menu:

- **Dashboard** — system overview
- **Indexing Status** — per-document progress and status information
- **Log Viewer** — per-service log streaming from the browser
- **Backups** — existing backup/restore dashboard
- **Solr Admin** — Solr admin UI with SSO passthrough

No configuration changes needed — the sidebar is purely a UI improvement.

### Per-Service Log Viewer

The log viewer at `/admin` → **Log Viewer** lets operators stream container logs directly from the admin portal. This reduces the need for SSH access for routine log inspection.

### Solr Admin SSO Passthrough

Nginx now injects BasicAuth credentials for Solr admin access when navigating through the admin portal. This eliminates the need for separate Solr credentials when using the admin UI.

The passthrough uses credentials from `.env`:

```bash
# Ensure these are set in .env (created by the installer)
SOLR_ADMIN_USER=admin
SOLR_ADMIN_PASS=<your-solr-password>
```

### Document Indexer Improvements

The document indexer has been hardened to handle large PDFs without memory exhaustion and to correctly manage thumbnail output paths.

**New environment variable:**

| Variable | Default | Purpose |
|---|---|---|
| `THUMBNAIL_DIR` | `/data/thumbnails` | Writable directory for generated document thumbnails |

**Operator action:** If you have a custom volume layout, ensure `THUMBNAIL_DIR` points to a writable location. The default works with the standard Docker Compose configuration.

### Infrastructure Enhancements

- **Volume permission hardening** — document-lister ensures correct directory permissions at startup
- **Build-time dependencies** — all Python packages installed during image build for faster cold starts and air-gapped deployments
- **Solr PDF font support** — improved text extraction for documents with non-standard fonts
- **Health checks** — nginx and aithena-ui containers include health check probes
- **Indexing progress sync** — System Status Redis key pattern aligned with indexer namespace

### Upgrade Procedure

1. Pull the latest images:
   ```bash
   docker compose pull
   ```
2. Stop and restart:
   ```bash
   docker compose down
   docker compose up -d
   ```
3. Verify the admin portal sidebar loads at `/admin`
4. Check the log viewer shows per-service logs

### Backward Compatibility

All changes are backward-compatible:

- Existing admin routes continue to work alongside the new sidebar navigation
- The `THUMBNAIL_DIR` variable has a sensible default; existing deployments work without changes
- Solr SSO passthrough is additive; direct Solr access still works with existing credentials

---

## Pre-Release Container Workflow (v1.16.0+)

Starting with v1.16.0, Aithena uses a formal release-candidate (RC) build and smoke-test workflow before promoting images to a final release tag. This reduces the risk of shipping regressions to production.

### What RC builds are

An RC build produces container images tagged `-rc.N` (e.g. `ghcr.io/owner/aithena-ui:1.16.0-rc.1`). RC images are built for all 6 services and run through the same smoke tests as a full release. RC images are **never** tagged `latest`, major (`1`), or minor (`1.16`) — only the final promoted release receives those tags.

### Triggering a manual RC build

1. Go to **Actions** → **Pre-release** in the GitHub repository.
2. Click **Run workflow**, select the `dev` branch, and optionally specify an RC number (leave blank to auto-increment).
3. The workflow builds all 6 services, pushes RC-tagged images, and runs smoke tests.

RC builds also trigger automatically on PRs targeting `main` (non-fork PRs only).

### RC auto-numbering

When no RC number is specified, the workflow queries ghcr.io for existing RC tags for the current version and increments to the next available number. If no RC tags exist yet, it defaults to `-rc.1`. You can override this with a manual input (e.g. `rc.3`) on the workflow dispatch form.

### Running RC images locally

Pull and start the RC stack using the production Compose file:

```bash
VERSION=1.16.0-rc.1 docker compose -f docker-compose.prod.yml pull
VERSION=1.16.0-rc.1 docker compose -f docker-compose.prod.yml up -d
```

Substitute `1.16.0-rc.1` with the actual RC tag you want to test. The `VERSION` environment variable overrides the image tag used by the production Compose file.

### Validation before promotion

Before promoting an RC to a final release tag, confirm:

- [ ] All smoke tests passed in the pre-release workflow run
- [ ] Search UI displays thumbnails, page numbers, and consistent chunk text across all search modes
- [ ] Similar books feature returns results (HTTP 200) from a book detail page
- [ ] Admin dashboard indexing status list is paginated
- [ ] Thumbnails load correctly in the UI (confirm nginx content-type is `image/jpeg`)
- [ ] No RabbitMQ deprecation warnings in container logs

### Rollback

If an RC reveals a blocking issue:

1. Stop the RC stack:
   ```bash
   docker compose -f docker-compose.prod.yml down
   ```
2. Pull and restart the previous release:
   ```bash
   VERSION=1.15.0 docker compose -f docker-compose.prod.yml pull
   VERSION=1.15.0 docker compose -f docker-compose.prod.yml up -d
   ```

### HF_TOKEN security note

The `embeddings-server` build requires a Hugging Face token (`HF_TOKEN`) to download model weights at build time. This token must be stored as a GitHub Actions secret named `HF_TOKEN` in your repository. It is never embedded in images or logged. Ensure the secret is set before triggering any RC or release build.

---

## Deployment Updates for v1.16.0

v1.16.0 delivers search UI fixes, a similar-books endpoint correction, admin UI pagination, and infrastructure fixes. There are no breaking changes from v1.15.0.

### Upgrade from v1.15.0

No migration steps required. Standard upgrade procedure:

```bash
docker compose pull
docker compose down
docker compose up -d
```

All fixes take effect automatically from the new images.

### RabbitMQ deprecation warning fix

v1.16.0 updates the RabbitMQ configuration to suppress the `management_metrics_collection` deprecation warning that appeared in container startup logs. No operator action is needed — the fix is applied inside the container image.

### Thumbnail serving fix

The nginx static content routing has been corrected so that thumbnail requests return `image/jpeg` instead of `text/html`. This restores thumbnail display across all views. No operator configuration change is required.

### Admin dashboard pagination

The admin indexing status list is now paginated automatically. No operator configuration is required. The change takes effect immediately on upgrade.

### Search UI fixes

All four search display regressions (#1221 – #1224) are fixed in the `aithena-ui` image. No operator action is required beyond pulling the new image.

### Similar books fix

The similar-books kNN query regression (#1220) is fixed in the `solr-search` image. No operator action is required.

### Backward compatibility

All changes are backward-compatible:

- No new environment variables introduced
- No volume layout changes
- No auth or configuration format changes
- Existing deployments can upgrade with a standard `docker compose pull && docker compose up -d`

## Deployment Updates for v1.17.0

v1.17.0 introduces GPU acceleration for embeddings indexing (opt-in), security dependency updates, and comprehensive GPU documentation. There are no breaking changes from v1.16.0. CPU-only deployments are completely unaffected.

### Upgrade from v1.16.0

No migration steps required. Standard upgrade procedure:

```bash
docker compose pull
docker compose down
docker compose up -d
```

The default CPU-only mode works exactly as before. GPU support is entirely opt-in.

### GPU Acceleration (New Feature)

v1.17.0 optionally supports GPU acceleration for document embeddings, speeding up indexing by 2–4× on NVIDIA GPUs and 1.5–2× on Intel GPUs.

#### Prerequisites for GPU support

**For NVIDIA GPUs:**
- NVIDIA GPU drivers installed on the host
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) installed and configured

**For Intel GPUs:**
- Intel Arc GPU drivers (or compatible Intel GPU drivers)
- Intel compute-runtime installed
- Device access to `/dev/dri` (automatic in most configurations)

**For WSL2 GPU support:**
- Windows 11 with GPU passthrough enabled (see Microsoft docs for [GPU support in WSL2](https://docs.microsoft.com/en-us/windows/wsl/tutorials/gpu-compute))

#### Enabling GPU acceleration

GPU support is accessed via Docker Compose profiles and environment variables.

**For NVIDIA GPUs:**
```bash
DEVICE=cuda BACKEND=torch docker compose --profile nvidia up -d
```

**For Intel GPUs:**
```bash
DEVICE=xpu BACKEND=openvino docker compose --profile intel up -d
```

**CPU-only (default):**
```bash
docker compose up -d  # No changes needed; runs in CPU mode
```

#### Verifying GPU is detected

Check container logs to confirm GPU detection:

```bash
docker compose logs embeddings-server | grep -i "device\|gpu\|cuda\|xpu"
```

Expected output (NVIDIA):
```
INFO: Device selection: DEVICE=cuda, BACKEND=torch
INFO: GPU detected: NVIDIA GeForce RTX 4090
```

Expected output (Intel with OpenVINO):
```
INFO: Device selection: DEVICE=xpu, BACKEND=openvino
INFO: GPU detected: Intel Arc GPU (DG2)
```

#### Troubleshooting GPU

See the updated [Admin Manual GPU Prerequisites](#gpu-prerequisites-v1170) and [GPU Troubleshooting](#gpu-troubleshooting-v1170) sections below, or consult the standalone [GPU Troubleshooting Guide](guides/gpu-troubleshooting.md).

### Security: Dependency Updates

v1.17.0 merges Dependabot security updates for two medium-severity vulnerabilities:

| Package | Vulnerability | Fix Version |
|---------|---|---|
| `requests` | Insecure Temp File Reuse in `extract_zipped_paths()` | 2.33.0 |
| `picomatch` | Method Injection in POSIX Character Classes | 4.0.4 |

Updated services:
- `document-indexer`: requests 2.33.0
- `solr-search`: requests 2.33.0
- `admin`: requests 2.33.0
- `aithena-ui`: picomatch 4.0.4

No operator action required; all fixes are included in the new container images.

### Embeddings-Server Build Optimization (Infrastructure)

Issue #1231 proposes creating a separate base image for embeddings-server to cache the ~1GB model and speed up CI builds by ~50%. This issue is closed with implementation planned for a future release. No operator changes in v1.17.0.

### Backward compatibility

All changes are backward-compatible:

- GPU support is opt-in via environment variables and compose profiles
- CPU-only deployments work identically to v1.16.0
- No new required environment variables (existing deployments unchanged)
- No volume layout changes
- No auth or configuration format changes
- Existing deployments can upgrade with a standard `docker compose pull && docker compose up -d`

---

## GPU Prerequisites (v1.17.0+)

This section covers GPU hardware and driver setup for Aithena operators.

### NVIDIA GPU Setup

#### Ubuntu/Debian

1. Install NVIDIA drivers:
```bash
ubuntu-drivers install  # or apt install nvidia-driver-XYZ
```

2. Install [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html):
```bash
curl https://nvidia.github.io/libnvidia-container/gpgkey | sudo apt-key add -
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker
```

3. Verify installation:
```bash
docker run --rm --runtime=nvidia nvidia/cuda:12.0.0-runtime-ubuntu22.04 nvidia-smi
```

#### RHEL/CentOS

1. Install NVIDIA drivers (see NVIDIA docs or use `nvidia-driver-install-utility`)

2. Install NVIDIA Container Toolkit:
```bash
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.repo | \
  sudo tee /etc/yum.repos.d/nvidia-container-toolkit.repo
sudo yum install -y nvidia-container-toolkit
sudo systemctl restart docker
```

3. Verify installation:
```bash
docker run --rm --runtime=nvidia nvidia/cuda:12.0.0-runtime-ubuntu22.04 nvidia-smi
```

#### Windows WSL2

Follow [Microsoft's GPU support guide for WSL2](https://docs.microsoft.com/en-us/windows/wsl/tutorials/gpu-compute) to enable GPU passthrough from Windows to WSL2. Requires Windows 11 with a GPU.

### Intel GPU Setup

#### Ubuntu/Debian

1. Install Intel GPU drivers:
```bash
sudo apt-get install -y intel-level-zero-gpu libze-loader
```

2. Install Intel compute-runtime:
```bash
sudo apt-get install -y intel-level-zero-gpu intel-metrics-discovery intel-media-driver intel-igc-core intel-igc-media
# Or via oneAPI (recommended):
wget -O- https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB | gpg --dearmor | sudo tee /usr/share/keyrings/oneapi-archive-keyring.gpg > /dev/null
echo "deb [signed-by=/usr/share/keyrings/oneapi-archive-keyring.gpg] https://apt.repos.intel.com/oneapi all main" | sudo tee /etc/apt/sources.list.d/oneAPI.list
sudo apt-get update && sudo apt-get install -y intel-oneapi-level-zero-gpu
```

3. Verify installation:
```bash
clinfo  # or another Intel GPU tool
```

#### RHEL/CentOS

1. Enable Intel oneAPI repository and install:
```bash
sudo dnf install -y intel-level-zero-gpu
```

2. Verify:
```bash
clinfo
```

### Monitoring GPU Usage

Use the following commands to monitor GPU utilization during indexing:

**NVIDIA:**
```bash
watch -n 1 nvidia-smi  # Real-time GPU stats
```

**Intel:**
```bash
gpu-top  # Part of Intel Metrics Discovery
# Or:
clinfo
```

Monitor embeddings-server logs for device selection:
```bash
docker compose logs -f embeddings-server | grep -i "device\|gpu"
```

---

## GPU Troubleshooting (v1.17.0+)

For a comprehensive troubleshooting guide, see [docs/guides/gpu-troubleshooting.md](guides/gpu-troubleshooting.md). This section covers common deployment issues.

### GPU Not Detected

**Symptom:** Logs show `DEVICE=cuda` but fall back to CPU.

**Check:**
1. Verify NVIDIA Container Toolkit is installed and Docker is restarted:
   ```bash
   docker run --rm --runtime=nvidia nvidia/cuda:12.0.0-runtime nvidia-smi
   ```
   If this fails, reinstall the toolkit and restart Docker.

2. Check Docker daemon configuration for `nvidia` runtime:
   ```bash
   cat /etc/docker/daemon.json | grep nvidia
   ```
   Should include `"runtimes": {"nvidia": ...}`.

3. Verify NVIDIA drivers are installed:
   ```bash
   nvidia-smi
   ```

### CUDA Version Mismatch

**Symptom:** Logs show errors like `CUDA version mismatch` or `driver version is insufficient`.

**Check:**
1. Host NVIDIA driver version:
   ```bash
   nvidia-smi | head -1  # Shows driver version
   ```

2. CUDA version in embeddings-server image:
   ```bash
   docker compose logs embeddings-server | grep -i "cuda"
   ```

3. Update drivers or adjust `docker-compose.yml` to use a compatible CUDA base image.

### Slow Indexing with GPU Enabled

**Symptom:** GPU enabled but indexing is not faster than CPU mode.

**Check:**
1. Verify GPU is actually being used:
   ```bash
   watch -n 1 nvidia-smi  # Should show embeddings process using GPU memory
   ```

2. Check for GPU memory exhaustion:
   ```bash
   nvidia-smi | grep "Processes"
   ```
   If memory is full, reduce batch size or use CPU mode.

3. Verify embeddings-server is using GPU in logs:
   ```bash
   docker compose logs embeddings-server | grep -i "device"
   ```

### Intel GPU Not Available

**Symptom:** Logs show `DEVICE=xpu` but no Intel GPU detected.

**Check:**
1. Verify Intel GPU drivers are installed:
   ```bash
   clinfo  # Should list Intel GPU
   ```

2. Check `/dev/dri` device access:
   ```bash
   ls -la /dev/dri/  # Should show GPU devices
   ```

3. Verify compose profile is being used:
   ```bash
   docker compose --profile intel up -d  # Must include --profile intel
   ```

For more detailed troubleshooting, see the [GPU Troubleshooting Guide](guides/gpu-troubleshooting.md).

---

## Deployment Updates for v1.17.1

v1.17.1 is a **security patch** that hardens GitHub Actions CI secrets handling. There are **no deployment changes** from v1.17.0. CPU-only and GPU-enabled deployments continue to work without modification.

### What Changed in v1.17.1

**GitHub Actions CI/CD security hardening (#1237):**

The `build-containers.yml` GitHub Actions workflow now uses a dedicated `build` environment with protection rules to gate access to container registry secrets (`GHCR_TOKEN`, `GHCR_USERNAME`). This resolves GitHub code scanning alert #230 (zizmor).

**Operator impact:** None. This change affects only the build pipeline in GitHub Actions. Runtime services, configuration, volumes, and environment variables remain unchanged from v1.17.0.

### Upgrade Path

Standard upgrade from v1.17.0 to v1.17.1:

```bash
docker compose pull
docker compose down
docker compose up -d
```

All existing GPU and CPU-mode deployments continue to work without modification.

### No Configuration Changes

- No new environment variables
- No volume layout changes
- No database migrations
- No auth or configuration format changes
- Existing `.env` files work unchanged
- Existing GPU profiles (`--profile nvidia`, `--profile intel`) work unchanged

### Operator Validation Checklist

Before considering v1.17.1 production-ready:

- [ ] Run `docker compose pull` and verify new image digests are fetched
- [ ] Run `docker compose up -d` and verify all services start without errors
- [ ] Run a test search query and confirm results are returned
- [ ] Check container logs for any warnings or errors: `docker compose logs`
- [ ] (If GPU enabled) Verify GPU detection is still working: `docker compose logs embeddings-server | grep -i device`

---

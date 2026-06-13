# Configuration Guide

This guide centralizes all configuration documentation for Aithena. For deployment procedures, see the [Admin Manual](../admin-manual.md).

## Quick Start

The fastest way to configure Aithena is to use the installer:

```bash
python3 -m installer
```

This tool:
- Generates `.env` with secure random secrets for auth, Solr, and RabbitMQ
- Creates the SQLite auth database at `volumes/auth/users.db`
- Prompts for library path, admin credentials, and deployment topology
- Preserves existing secrets on subsequent runs (unless `--reset` is passed)

For a manual setup, copy `.env.example` to `.env` and customize as needed:

```bash
cp .env.example .env
# Edit .env with your library path, secrets, and overrides
docker compose config  # Validate syntax
docker compose up -d   # Start the stack
```

> ⚠️ **Replace all placeholder secrets before deploying.** The installer generates secure random values for `AUTH_JWT_SECRET`, `ADMIN_API_KEY`, and all `RABBITMQ_*_PASS` variables automatically. If manually editing `.env`, these must be replaced with secure values before any production deployment.

## Environment Variables Reference

All configuration is controlled through environment variables loaded from `.env`. Here is the complete reference with defaults, purposes, and security notes.

### General Paths, Origins, and Build Metadata

| Variable | Default | Purpose | Required |
|---|---|---|---|
| `BOOKS_PATH` | `./volumes/booklibrary` | Host path mounted as the document library. Point at your real library before indexing. | Yes |
| `BOOK_LIBRARY_PATH` | `./volumes/booklibrary` | Compatibility alias consumed by installer and scripts. Keep in sync with `BOOKS_PATH`. | No |
| `PUBLIC_ORIGIN` | `http://localhost` | Public browser origin served by nginx. Set to your FQDN for production. | Yes |
| `CORS_ORIGINS` | `http://localhost,http://127.0.0.1,http://localhost:5173,http://127.0.0.1:5173` | Browser origins allowed by solr-search (comma-separated). Keep localhost:5173 for Vite dev. | Yes |
| `VERSION` | `2.5.1` | Build metadata used by image labels, `/version` endpoints, and GHCR tags. | No |
| `GIT_COMMIT` | `unknown` | Git commit hash embedded in build metadata. | No |
| `BUILD_DATE` | `unknown` | Build timestamp. Updated automatically at image build. | No |

### Authentication, Admin Bootstrap, and API Safety

| Variable | Default | Purpose | Required | Security |
|---|---|---|---|---|
| `AUTH_DB_DIR` | `./volumes/auth` | Host directory bind-mounted into solr-search for SQLite auth database. | Yes | Must be readable/writable by Docker user. |
| `AUTH_DB_PATH` | `/data/auth/users.db` | Container path for SQLite auth database. Change only if modifying compose mount. | No | Internal only; do not modify unless customizing mounts. |
| `AUTH_JWT_SECRET` | `generate-with-installer` | JWT secret for auth tokens. **Must be regenerated for production.** | **Yes** | Secrets-managed only; never commit real values. Use installer. |
| `AUTH_JWT_TTL` | `24h` | JWT token lifetime (`24h`, `30m`, `7d`, etc.). Shorter TTL = more frequent re-auth. | No | Adjust for security posture. |
| `AUTH_COOKIE_NAME` | `aithena_auth` | Cookie name used for browser auth sessions. | No | Can be customized for branding. |
| `ADMIN_API_KEY` | `generate-with-installer` | Defense-in-depth API key for `/v1/admin/*` endpoints. **Must be regenerated for production.** | **Yes** | Secrets-managed only; never commit real values. Use installer. |
| `AUTH_ADMIN_USERNAME` | `admin` | Bootstrap admin account username written into auth database by installer. | Yes | Set only at first initialization. |
| `AUTH_ADMIN_PASSWORD` | (blank) | Bootstrap admin account password. Installer prompts for this. | Yes | Never commit real passwords. |
| `AUTH_ENABLED` | `true` | Enable/disable auth. Keep `true` in production; set `false` only for isolated tests. | No | Disabling auth is dangerous; only for development. |
| `RATE_LIMIT_REQUESTS_PER_MINUTE` | `100` | Global request limit for authenticated API traffic. Set `0` to disable all rate limiting. | No | Tune for load and security. |
| `UPLOAD_RATE_LIMIT_REQUESTS_PER_MINUTE` | `10` | Upload-specific rate limit. When blank, solr-search falls back to 10 or inherits global limit. | No | Usually tighter than global limit. |

### RabbitMQ Credentials

| Variable | Default | Purpose | Required | Security |
|---|---|---|---|---|
| `RABBITMQ_USER` | `aithena` | Legacy broker admin username. Kept for backwards compatibility with installer output. | No | Deprecated; use per-service credentials below. |
| `RABBITMQ_PASS` | `generate-with-installer` | Legacy broker admin password. **Must be regenerated for production.** | No | Deprecated; use per-service credentials below. |
| `RABBITMQ_LISTER_USER` | `lister` | Username for document-lister service. | Yes | Secrets-managed only; use installer. |
| `RABBITMQ_LISTER_PASS` | `generate-with-installer` | Password for document-lister. Least-privilege account. | **Yes** | Secrets-managed only; never commit real values. |
| `RABBITMQ_INDEXER_USER` | `indexer` | Username for document-indexer service. | Yes | Secrets-managed only; use installer. |
| `RABBITMQ_INDEXER_PASS` | `generate-with-installer` | Password for document-indexer. Least-privilege account. | **Yes** | Secrets-managed only; never commit real values. |
| `RABBITMQ_SEARCH_USER` | `search` | Username for solr-search service (admin API queue access). | Yes | Secrets-managed only; use installer. |
| `RABBITMQ_SEARCH_PASS` | `generate-with-installer` | Password for solr-search. | **Yes** | Secrets-managed only; never commit real values. |
| `RABBITMQ_ADMIN_USER` | `admin` | RabbitMQ management UI admin username. | Yes | Secrets-managed only; use installer. |
| `RABBITMQ_ADMIN_PASS` | `generate-with-installer` | RabbitMQ management UI admin password. | **Yes** | Secrets-managed only; never commit real values. |

### Embeddings Runtime and Search Configuration

| Variable | Default | Purpose | Required | Notes |
|---|---|---|---|---|
| `DEVICE` | `cpu` | Compute device: `cpu` (default, portable) or `cuda` (NVIDIA GPU), `xpu` (Intel GPU). | No | GPU overlays auto-detect; see [GPU Acceleration](../admin-manual.md#gpu-acceleration-setup-v1170). |
| `BACKEND` | `torch` | Embedding backend. Currently `torch` and `openvino` are supported. | No | Future support for alternative backends TBD. |
| `EMBEDDINGS_BASE_TAG` | `3.12-slim-multilingual-e5-base` | Source-build base image tag for local builds via docker-compose.yml. | No | Used only if building embeddings image locally. |
| `EMBEDDINGS_VERSION` | `2.5.1` | Prebuilt embeddings image tag used by production/offline deployments. | No | Set when pulling prebuilt images from GHCR. |
| `VECTOR_QUANTIZATION` | `none` | Stored vector precision: `none` (full fp32), `fp16`, or `int8`. Smaller = faster search, less accurate. | No | Requires reindexing when changed. Quantization evidence-gated until v2.6. |
| `SEARCH_ARCHITECTURE` | `hnsw` | Search mode implementation: `hnsw` (default, single-node optimized) or `hybrid-rerank` (experimental). | No | `hybrid-rerank` combines full-text BM25 with vector similarity. |
| `KNN_FIELD` | `embedding_v` | Solr vector field name for k-nearest-neighbor search. | No | Keep aligned with schema unless customizing collections. |
| `BOOK_EMBEDDING_FIELD` | `embedding_v` | Solr vector field name for book documents. | No | Keep aligned with `KNN_FIELD` unless testing schema variants. |
| `COLLECTIONS_DB_PATH` | `/data/collections/collections.db` | solr-search collections metadata database (inside container). | No | Internal only; do not modify. |

### Solr Authentication, Versioning, and Topology

| Variable | Default | Purpose | Required | Security |
|---|---|---|---|---|
| `SOLR_ADMIN_USER` | `solr_admin` | Solr admin credentials used by solr-init, health checks, and nginx auth proxying. | Yes | Secrets-managed only; use installer. |
| `SOLR_ADMIN_PASS` | `generate-with-installer` | Solr admin password. **Must be regenerated for production.** | **Yes** | Secrets-managed only; never commit real values. |
| `SOLR_READONLY_USER` | `solr_read` | Solr read-only credentials used by solr-search query traffic (least-privilege). | Yes | Secrets-managed only; use installer. |
| `SOLR_READONLY_PASS` | `generate-with-installer` | Solr read-only password. | **Yes** | Secrets-managed only; never commit real values. |
| `SOLR_VERSION` | `10` | Solr runtime selection: `10` (default) or `9` (legacy/rollback only). | No | Use `10` unless explicitly testing rollback. See [Solr 10 Migration](#solr-10-migration). |
| `SOLR_BASE_IMAGE` | `solr:10` | Official Solr image tag from Docker Hub. | No | Aligned with `SOLR_VERSION`. |
| `SOLR_OPTS` | (empty) | Optional extra JVM/Solr flags appended on every Solr node (e.g., `-Xmx2g -Xms1g`). | No | Leave empty unless tuning JVM or debugging. |
| `SOLR_CLOUD_OVERSEER_ENABLED` | `false` | Production overlay appends this into `SOLR_OPTS` to enable Solr overseer. Keep `false` unless hardening for multi-shard deployments. | No | Required for distributed/HA deployments. |
| `SOLR_TOPOLOGY` | `single-node` | Deployment topology: `single-node` (dev, lightweight) or `distributed` (3 Solr + 3 ZK, production-ready). | No | Hint consumed by installer and `start.sh`. |
| `SOLR_NUM_SHARDS` | `1` | Initial shard count for `books` collection. Single-node deployments keep `1`. | No | Set by installer based on `SOLR_TOPOLOGY`. |
| `SOLR_REPLICATION_FACTOR` | `1` | Collection replication factor. Lightweight deployments keep `1`; HA deployments use `2` or `3`. | No | Must not exceed cluster node count. Set by installer. |

### Reverse Proxy, SSL, and Test Overlays

| Variable | Default | Purpose | Required | Notes |
|---|---|---|---|---|
| `NGINX_HOST` | `aithena.example.com` | FQDN for TLS certificate generation. Required only with `docker/compose.ssl.yml`. | Conditional | Required if using SSL overlay. |
| `E2E_LIBRARY_PATH` | `./volumes/e2e-booklibrary` | Library path used only by `docker/compose.e2e.yml` for integration tests. | Conditional | Required only for E2E test runs. |

## Docker Compose Customization

### Using Overlays

Docker Compose supports overlay files for environment-specific configurations. The canonical overlays are:

| Overlay | Purpose | When to Use |
|---|---|---|
| `docker-compose.yml` (base) | Base distributed topology (3 Solr + 3 ZK). | Always included; production-ready deployments. |
| `docker/compose.single-node.yml` | Single Solr node + single ZooKeeper. Lightweight. | Development, testing, resource-constrained VMs. |
| `docker/compose.ssl.yml` | Adds nginx TLS certificate management via certbot. | HTTPS deployments; requires `NGINX_HOST`. |
| `docker/compose.prod.yml` | Production hardening: larger limits, volume persistence, reserved memory. | Hardened production environments. |
| `docker/compose.e2e.yml` | E2E test environment with isolated library path. | Running integration tests. |

**Example: start single-node with SSL:**

```bash
docker compose -f docker-compose.yml \
  -f docker/compose.single-node.yml \
  -f docker/compose.ssl.yml \
  up -d
```

### Custom Environment Variable Override

You can override specific variables without modifying `.env`:

```bash
BOOKS_PATH=/data/my-books PUBLIC_ORIGIN=https://search.myorg.com docker compose up -d
```

### Custom Mount Points

To use different volume paths on the host, modify the `.env` variables rather than editing `docker-compose.yml`:

```bash
# .env
BOOKS_PATH=/mnt/nfs/library
AUTH_DB_DIR=/mnt/persistent/auth
```

This approach keeps `docker-compose.yml` stable and enables reuse across environments.

## Solr 10 Migration

If upgrading from Solr 9 (v2.3.0) to Solr 10 (v2.5.0+):

1. **Review schema changes:** HNSW vector field names changed in Solr 10. See [migration guide](../migration/solr-9-to-10.md).

2. **Back up collections before starting:**

```bash
# Download Solr 9 collections to a backup directory
curl http://localhost:8983/solr/api/collections/books/backups -X POST -H 'Content-Type: application/json' \
  -u ${SOLR_ADMIN_USER}:${SOLR_ADMIN_PASS} \
  -d '{"name": "books_backup_pre_v2.5"}'
```

Replace `${SOLR_ADMIN_USER}` and `${SOLR_ADMIN_PASS}` with the credentials from your `.env` file.

3. **Update topology if necessary:** If upgrading single-node, keep `SOLR_TOPOLOGY=single-node` and `SOLR_NUM_SHARDS=1`.

4. **Start with new image:**

```bash
docker compose pull
docker compose up -d
```

5. **Monitor bootstrap:** Watch `solr-init` logs for collection creation success.

```bash
docker compose logs -f solr-init
```

For detailed runbook, see [Solr 10 Production Migration](../migration/solr-10-production-runbook.md).

## Advanced Topics

### RabbitMQ Queue Configuration

RabbitMQ definitions are initialized via `src/rabbitmq/init-definitions.sh` at first startup. The script creates:

- Per-service users (lister, indexer, search, admin) with minimal required permissions
- Exchanges: `documents` (topic), `admin` (direct)
- Queues: `doc.scan`, `doc.index`, `admin.reindex`, `admin.delete`
- Bindings connecting services to queues

To customize queue topology, edit `src/rabbitmq/init-definitions.sh` and rebuild:

```bash
docker compose down -v  # Remove RabbitMQ volume
docker compose up -d
docker compose logs -f rabbitmq  # Wait for definitions to load
```

### Solr Collection Schema

The `books` collection schema is bootstrapped by `solr-init` on first start. Key fields:

- `id`: Document UUID (primary key)
- `title`, `author`, `description`: Indexed text fields with language-specific analyzers
- `embedding_v`: KNN vector field (dimension and quantization controlled by `VECTOR_QUANTIZATION`)
- `paths`: Hierarchical folder path facet
- `created_at`, `modified_at`: Timestamps for incremental indexing

To apply schema changes:

1. Edit `src/solr/books/managed-schema.xml`
2. Restart solr-init or use Solr API to reload config
3. Reindex documents if field definitions changed

See [Solr Data Model](../architecture/solr-data-model.md) for full schema reference.

### Custom Embeddings Model

By default, Aithena uses the `multilingual-e5-base` model. To use a different model:

1. Edit `src/embeddings-server/Dockerfile`
2. Change the model checkpoint (e.g., `intfloat/e5-large` for higher quality)
3. Rebuild and tag: `docker build -t aithena-embeddings:custom docker/embeddings`
4. Update compose to use the custom image
5. Reindex all documents

**Note:** Different models have different embedding dimensions and may require schema updates.

### Redis Configuration

Redis is configured via `src/redis/redis.conf` and volumes mount as read-only. To customize:

1. Edit `src/redis/redis.conf`
2. Rebuild compose: `docker compose down && docker compose up -d redis`

Key settings:

- `maxmemory`: Memory limit (default ~256M; adjust for library size)
- `maxmemory-policy`: Eviction strategy (default LRU)
- `save`: Persistence snapshot frequency

### Host-Level Kernel Tuning

#### Redis Memory Overcommit (Required)

Redis background saves (RDB snapshots) require kernel memory overcommit:

```bash
# Apply immediately:
sudo sysctl vm.overcommit_memory=1

# Make persistent:
echo "vm.overcommit_memory = 1" | sudo tee /etc/sysctl.d/90-redis-overcommit.conf
sudo sysctl --system
```

Without this, Redis logs `WARNING Memory overcommit must be enabled!` and snapshots may fail.

#### ZooKeeper Security (Production)

ZooKeeper is internal-only in the default Compose deployment. For production hardening:

- **Do not publish ZooKeeper ports** (2181, 2888, 3888) to the host
- **Solr BasicAuth** protects HTTP APIs; ZooKeeper ACLs are a secondary layer
- See [ZooKeeper Access Control](https://solr.apache.org/guide/solr/latest/deployment-guide/zookeeper-access-control.html) and the [Admin Manual](../admin-manual.md#zookeeper-credentials-production-hardening) for hardening guidance

## Troubleshooting

### Stack fails to start

**Symptom:** `docker compose up` fails with service unhealthy or cannot connect.

**Diagnosis:**

1. Check host prerequisites:
```bash
# Verify Redis memory overcommit
sysctl vm.overcommit_memory

# Verify Docker is running
docker ps
```

2. Check `.env` validity:
```bash
docker compose config
```

3. Check service logs:
```bash
docker compose logs solr-init   # Collection bootstrap
docker compose logs solr         # Solr errors
docker compose logs rabbitmq     # Queue errors
```

**Solutions:**

- If `solr-init` fails: check Solr logs and ensure `SOLR_VERSION` matches running image
- If RabbitMQ fails: delete volume and restart (`docker compose down -v && docker compose up -d`)
- If Redis fails: check `vm.overcommit_memory=1` on host

### Slow search or indexing

**Symptom:** Searches take >1s or indexing crawls.

**Check:**

1. Solr GC and memory: `curl http://localhost:8983/solr/admin/info/jvm`
2. Redis memory: `docker compose exec redis redis-cli info memory`
3. Vector quantization: if `VECTOR_QUANTIZATION=none`, switch to `fp16` or `int8`

**Tune:**

```bash
# Increase Solr JVM heap
SOLR_OPTS="-Xmx4g -Xms2g" docker compose up -d

# Increase Redis memory
# Edit src/redis/redis.conf and restart
```

### Authentication failures

**Symptom:** Login fails or admin endpoints return 401/403.

**Check:**

1. Auth database exists: `ls -la volumes/auth/users.db`
2. JWT secret is set: `echo $AUTH_JWT_SECRET`
3. Admin user exists: `docker compose exec solr-search sqlite3 /data/auth/users.db 'SELECT username FROM users;'`

**Solutions:**

- Reinitialize auth: `rm volumes/auth/users.db && python3 -m installer`
- Reset admin password: `python3 -m installer --reset-auth`

### Solr 10 migration issues

See [Solr 10 Migration Troubleshooting](../migration/solr-10-production-runbook.md#troubleshooting).

## Related Documentation

- [Admin Manual](../admin-manual.md) — Deployment, monitoring, operations
- [User Manual](../user-manual.md) — End-user features and workflows
- [Hardware Requirements](../hardware-requirements.md) — CPU, memory, disk sizing
- [Solr Data Model](../architecture/solr-data-model.md) — Collection schema reference
- [Solr 10 Migration Guide](../migration/solr-9-to-10.md) — Upgrade from Solr 9
- [GPU Acceleration Guide](../guides/gpu-troubleshooting.md) — NVIDIA and Intel setup
- [Monitoring and Observability](../guides/monitoring.md) — Health checks and logging

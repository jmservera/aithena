# Production Deployment Guide

This guide covers production deployment of the Aithena book library search system using Docker Compose. Pair it with the [Search and indexing sizing guide](sizing-guide.md) when you need capacity estimates for Solr, Redis, RabbitMQ, the embeddings server, and indexing throughput.

For service-by-service outage handling and recovery drills, see the [failover runbook](failover-runbook.md).

For service-by-service outage handling and recovery drills, see the [failover runbook](failover-runbook.md).

## Table of Contents

- [Prerequisites](#prerequisites)
- [Resource Requirements](#resource-requirements)
- [Service Startup Order](#service-startup-order)
- [Volume Initialization](#volume-initialization)
- [Health Validation](#health-validation)
- [Graceful Shutdown](#graceful-shutdown)
- [Monitoring & Logging](#monitoring--logging)
- [Troubleshooting](#troubleshooting)
- [Backup & Restore](#backup--restore)
- [Failover Runbook](failover-runbook.md)

## Prerequisites

### System Requirements

- **OS**: Linux (Ubuntu 22.04 LTS or Debian 12 recommended)
- **Docker**: 24.0+ with Docker Compose V2
- **CPU**: Minimum 8 cores (12+ recommended for production load)
- **RAM**: Minimum 16GB (32GB+ recommended)
- **Disk**: 100GB+ SSD for volumes, plus library storage

### Network

- Ports 80/443 available for nginx
- Internal service ports isolated via Docker networks
- Firewall rules configured for public access to nginx only

### Memory Overcommit (Critical for Redis)

```bash
echo "vm.overcommit_memory = 1" | sudo tee /etc/sysctl.d/aithena-memory-overcommit.conf
sysctl -p /etc/sysctl.d/aithena-memory-overcommit.conf
```

## Resource Requirements

### Service Memory Allocation

| Service | Memory Limit | Memory Reservation | Notes |
|---------|-------------|-------------------|-------|
| **Core Infrastructure** | | | |
| Solr (3 nodes) | 2GB each | 1GB each | Total: 6GB limit, 3GB reserved |
| ZooKeeper (3 nodes) | 512MB each | 256MB each | Total: 1.5GB limit, 768MB reserved |
| Redis | 512MB | 256MB | Persistent key-value store |
| RabbitMQ | 1GB | 512MB | Message queue |
| **Application Services** | | | |
| embeddings-server | 2GB | 1GB | Model loading requires RAM |
| solr-search | 512MB | 256MB | Search API |
| document-indexer | 512MB | 256MB | Worker process |
| document-lister | 256MB | 128MB | File system poller |
| **User Interfaces** | | | |
| aithena-ui | 256MB | 128MB | React SPA (nginx) |
| streamlit-admin | 512MB | 256MB | Admin dashboard |
| redis-commander | 256MB | 128MB | Redis UI |
| nginx | 256MB | 128MB | Reverse proxy |

**Total System Requirements:**
- **Memory Limits**: ~15GB
- **Memory Reservations**: ~8GB
- **Recommended Host RAM**: 16GB minimum, 32GB for headroom

### CPU Reservations

Services with CPU reservations (guaranteed cores):
- **Solr nodes** (3x): 1.0 core each = 3.0 cores total
- **embeddings-server**: 1.0 core (model inference)
- **solr-search**: 0.5 core

**Recommended Host CPU**: 8+ cores

### Disk Space

| Volume | Typical Size | Growth Rate | Description |
|--------|-------------|-------------|-------------|
| `solr-data*` (3 nodes) | 10-50GB | High | Indexed documents + embeddings |
| `zoo-data*` (3 nodes) | 1-5GB | Low | Cluster metadata |
| `rabbitmq-data` | 1-10GB | Medium | Queue state |
| `redis-data` | 100MB-1GB | Low | Pipeline state |
| `document-data` | User library size | N/A | Read-only mount |

**Minimum Disk**: 100GB for infrastructure + library size  
**Recommended**: 500GB SSD for fast Solr indexing

## Service Startup Order

Docker Compose automatically orchestrates startup based on `depends_on` health checks. The dependency graph ensures correct initialization:

### Tier 1: Core Infrastructure (0-60s)
1. **redis** — Starts first, health check via `redis-cli ping`
2. **rabbitmq** — Starts in parallel, health check via `rabbitmqctl ping` (30s start_period)
3. **zoo1, zoo2, zoo3** — ZooKeeper ensemble formation (30s start_period, 4LW ruok + leader/follower check)

### Tier 2: Search Cluster (60-120s)
4. **solr, solr2, solr3** — Solr nodes wait for ZooKeeper quorum (30s start_period, curl to `/admin/info/system`)
5. **solr-init** — One-shot bootstrap (uploads schema, creates collection, applies overlay)

### Tier 3: Application Services (120-180s)
6. **embeddings-server** — Loads sentence-transformers model (60s start_period due to model download)
7. **document-lister** — Polls filesystem, publishes to RabbitMQ (waits for redis + rabbitmq healthy)
8. **document-indexer** — Consumes queue, indexes to Solr (waits for redis + rabbitmq + embeddings healthy)
9. **solr-search** — FastAPI search service (waits for solr + embeddings healthy)

### Tier 4: User Interfaces (180-210s)
10. **aithena-ui** — React search UI (waits for solr-search healthy)
11. **streamlit-admin** — Admin dashboard (waits for redis + rabbitmq healthy)
12. **redis-commander** — Redis UI (waits for redis healthy)

### Tier 5: Ingress (210-240s)
13. **nginx** — Starts LAST, waits for all upstreams healthy (aithena-ui, solr-search, streamlit-admin, redis-commander, rabbitmq, solr)

### Expected Startup Time

- **Minimal stack** (infra only): 60-90 seconds
- **Full stack** (cold start): 3-5 minutes
- **Warm restart** (volumes intact): 2-3 minutes

## Volume Initialization

### First-Time Setup

1. **Run the first-run installer** to generate `.env`, create the auth database, and seed the admin user:
   ```bash
   python3 -m installer
   # or: python3 installer/setup.py
   ```

   The installer prompts for the book library path, admin credentials, and the public origin URL.
   It writes `.env` (chmod 600), bootstraps the SQLite auth DB at `AUTH_DB_DIR`,
   and generates non-default RabbitMQ/Redis credentials unless you already have
   secure values in place.
   For non-interactive environments (CI/scripts), use flags:
   ```bash
   python3 installer/setup.py \
     --library-path /path/to/books \
     --admin-user admin \
     --admin-password secret \
     --origin http://localhost
   ```

   > **Note:** `AUTH_DB_DIR` must exist on the host before `docker compose up` because Docker
   > Compose uses it as a bind-mount source for the auth database. The installer creates this
   > directory automatically. If you ever re-run the installer it preserves the existing JWT
   > secret, service credentials, and user records unless you pass `--reset`.

2. **Create volume directories**:
   ```bash
   sudo mkdir -p /source/volumes/{rabbitmq-data,redis,solr-data,solr-data2,solr-data3,zoo-backup}
   sudo mkdir -p /source/volumes/{zoo-data1,zoo-data2,zoo-data3}/{data,logs,datalog}
   sudo chown -R 8983:8983 /source/volumes/solr-data*  # Solr UID
   sudo chown -R 1000:1000 /source/volumes/zoo-data*   # ZooKeeper UID
   ```

3. **Start infrastructure tier**:
   ```bash
   docker compose up -d redis rabbitmq zoo1 zoo2 zoo3
   docker compose logs -f zoo1 zoo2 zoo3  # Wait for quorum
   ```

4. **Start Solr cluster**:
   ```bash
   docker compose up -d solr solr2 solr3
   docker compose logs -f solr-init  # Wait for "Solr init complete"
   ```

5. **Verify cluster**:
   ```bash
   curl http://localhost:8983/solr/admin/collections?action=CLUSTERSTATUS
   # Should show 3 live nodes + books collection RF=3
   ```

### Subsequent Starts

```bash
docker compose up -d
# All services start with correct dependencies automatically
```

To rotate the JWT secret, RabbitMQ password, Redis password, or bootstrap admin password, re-run the installer before restarting:

```bash
python3 -m installer          # interactive — keeps existing secrets unless they match insecure placeholders
python3 -m installer --reset  # recreate auth DB and rotate generated secrets
```

If you prefer to rotate service credentials manually, generate strong replacements (for example with `openssl rand -base64 32`), update `.env`, and then recreate every service that connects to Redis or RabbitMQ:

```dotenv
RABBITMQ_USER=aithena
RABBITMQ_PASS=<strong-random-value>
REDIS_PASSWORD=<strong-random-value>
```

- `docker-compose.yml` maps `RABBITMQ_USER` / `RABBITMQ_PASS` to RabbitMQ's `RABBITMQ_DEFAULT_USER` / `RABBITMQ_DEFAULT_PASS` so the broker, management UI, and admin dashboard stay aligned.
- `docker-compose.yml` injects `REDIS_PASSWORD` into the Redis container and enables `redis-server --requirepass` automatically when the variable is non-empty.
- If you manage RabbitMQ credentials in `src/rabbitmq/rabbitmq.conf` instead, set `default_user` / `default_pass` there and keep `.env` in sync so `streamlit-admin`, `document-lister`, `document-indexer`, and `solr-search` still authenticate successfully.

After any credential rotation:

```bash
docker compose up -d --force-recreate redis rabbitmq redis-commander streamlit-admin document-lister document-indexer solr-search nginx
```

## Health Validation

### Check All Services

```bash
docker compose ps
# All services should show "healthy" or "running" status
```

### Individual Health Checks

```bash
# Redis
docker compose exec redis redis-cli ping
# Expected: PONG

# RabbitMQ
docker compose exec rabbitmq rabbitmqctl ping
# Expected: Ping succeeded

# ZooKeeper ensemble
for node in zoo1 zoo2 zoo3; do
  docker compose exec $node zkServer.sh status
done
# Expected: Mode: leader (1 node), Mode: follower (2 nodes)

# Solr nodes
for port in 8983 8984 8985; do
  curl -s http://localhost:$port/solr/admin/info/system | jq -r .status
done
# Expected: "OK" for all nodes

# Embeddings server
curl http://localhost:8085/health
# Expected: {"status":"healthy","model":"...","embedding_dim":512}

# Search API
curl http://localhost:8080/health
# Expected: {"status":"ok","service":"...","version":"..."}

# nginx
curl http://localhost/health
# Expected: healthy
```

### Verify Indexing Pipeline

```bash
# Check document lister discovered files
docker compose logs document-lister | grep "Found.*documents"

# Check RabbitMQ queue depth
docker compose exec rabbitmq rabbitmqctl list_queues name messages | grep shortembeddings

# Check indexing progress via Streamlit admin
open http://localhost/admin/streamlit/

# Query Solr for indexed count
curl "http://localhost:8983/solr/books/select?q=*:*&rows=0" | jq -r .response.numFound
```

## Graceful Shutdown

Services have `stop_grace_period` configured for clean shutdown:

```bash
# Graceful shutdown (recommended)
docker compose down

# Force immediate stop (data loss risk)
docker compose down -t 0
```

### Grace Periods

- **60 seconds**: Solr (flushes index segments), ZooKeeper (commits transactions)
- **30 seconds**: Redis (saves RDB snapshot), RabbitMQ (drains queue)
- **10 seconds**: Application services (finish current requests)

### Shutdown Order

Docker Compose stops services in reverse dependency order:
1. nginx → 2. UIs → 3. Workers → 4. Search services → 5. Infrastructure

## Monitoring & Logging

### Log Rotation

All services use JSON file logging with rotation:
- **Max file size**: 10MB per log file
- **Max files**: 3 (total 30MB per service)
- **Compression**: Automatic on rotation

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f solr-search

# Last 100 lines
docker compose logs --tail=100 document-indexer

# Follow errors only
docker compose logs -f | grep -i error
```

### Metrics

Access service metrics via admin interfaces:

- **Solr Admin**: http://localhost/admin/solr/ (JVM stats, query metrics, core stats)
- **RabbitMQ Management**: http://localhost/admin/rabbitmq/ (queue depth, message rates, connections; sign in with `RABBITMQ_USER` / `RABBITMQ_PASS` from `.env`)
- **Redis Commander**: http://localhost/admin/redis/ (keyspace, memory usage, commands/sec; uses `REDIS_PASSWORD` from `.env` when configured)
- **Streamlit Admin**: http://localhost/admin/streamlit/ (indexing pipeline stats, document counts)

### Resource Usage

```bash
# Per-container stats
docker stats

# Memory usage by service
docker compose ps --format json | jq -r '.[].Name' | xargs -I {} docker stats {} --no-stream

# Check if any service hit memory limit
docker compose ps -q | xargs docker inspect --format '{{.Name}}: {{.State.OOMKilled}}' | grep true
```

## Troubleshooting

### Service Won't Start

**Symptom**: Service stuck in "starting" state or crash loops

**Diagnosis**:
```bash
# Check logs for errors
docker compose logs <service_name>

# Check health check failures
docker inspect <container_id> | jq '.[].State.Health'
```

**Common Causes**:
- **Insufficient memory**: Check `docker stats`, increase host RAM or reduce limits
- **Port conflict**: Another process using the port (check with `netstat -tuln`)
- **Volume permission error**: Fix with `chown` as shown in Volume Initialization
- **Health check false positive**: Increase `start_period` in docker-compose.yml

### ZooKeeper Quorum Lost

**Symptom**: Solr reports "ZK connection lost", indexing stops

**Recovery**:
```bash
# Check ZooKeeper ensemble status
docker compose exec zoo1 zkServer.sh status
docker compose exec zoo2 zkServer.sh status
docker compose exec zoo3 zkServer.sh status

# If only 1 node up, restart the others
docker compose restart zoo2 zoo3

# If all down, restart in order
docker compose up -d zoo1 zoo2 zoo3
```

### RabbitMQ Cold-Start Failure

**Known Issue**: #166 — `timeout_waiting_for_khepri_projections` on first `docker compose up`

**Workaround**:
```bash
# First start may fail — this is expected
docker compose up -d rabbitmq

# Wait 30 seconds, then restart
sleep 30
docker compose restart rabbitmq
```

**Permanent Fix**: Increase health check retries in docker-compose.yml (already applied in v0.6.0)

### Embeddings Server OOM

**Symptom**: embeddings-server restarts frequently, logs show "Killed"

**Cause**: Model doesn't fit in 2GB memory limit

**Fix**:
```bash
# Increase memory limit in docker-compose.yml
# Change embeddings-server memory limit from 2g to 3g or 4g
nano docker-compose.yml

# Recreate container
docker compose up -d --force-recreate embeddings-server
```

### Solr Index Corruption

**Symptom**: Search returns errors, Solr logs show "CorruptIndexException"

**Recovery**:
```bash
# Stop Solr
docker compose stop solr solr2 solr3

# Delete corrupted index (WARNING: data loss)
sudo rm -rf /source/volumes/solr-data*/*

# Restart cluster and re-index
docker compose up -d solr solr2 solr3
docker compose restart document-lister  # Trigger re-scan
```

### Nginx 502 Bad Gateway

**Symptom**: http://localhost returns 502, "upstream not found"

**Diagnosis**:
```bash
# Check if upstream services are healthy
docker compose ps aithena-ui solr-search

# Check nginx logs
docker compose logs nginx | grep upstream
```

**Fix**:
```bash
# Restart unhealthy upstreams
docker compose restart aithena-ui solr-search

# If DNS resolution issue, restart nginx
docker compose restart nginx
```

## Backup & Restore

### Backup Strategy

**Critical Data** (backup daily):
- `/source/volumes/solr-data*` — Indexed documents + embeddings
- `/source/volumes/zoo-data*` — ZooKeeper cluster state
- `/source/volumes/rabbitmq-data` — Queue state (if important)
- `/source/volumes/redis` — Pipeline state (optional)
- `AUTH_DB_DIR` (from `.env`) — SQLite auth database containing user accounts

**Read-Only Data** (backup separately):
- Book library (`BOOKS_PATH`) — Source PDFs

### Backup Procedure

```bash
#!/bin/bash
# backup-aithena.sh

BACKUP_DIR=/backups/aithena/$(date +%Y%m%d-%H%M%S)
mkdir -p $BACKUP_DIR

# Stop services for consistent snapshot
docker compose stop solr solr2 solr3 zoo1 zoo2 zoo3

# Backup volumes
sudo tar -czf $BACKUP_DIR/solr-data.tar.gz -C /source/volumes solr-data solr-data2 solr-data3
sudo tar -czf $BACKUP_DIR/zoo-data.tar.gz -C /source/volumes zoo-data1 zoo-data2 zoo-data3
sudo tar -czf $BACKUP_DIR/rabbitmq-data.tar.gz -C /source/volumes rabbitmq-data
sudo tar -czf $BACKUP_DIR/redis.tar.gz -C /source/volumes redis

# Backup auth database (path from .env)
AUTH_DB_DIR=$(grep '^AUTH_DB_DIR=' .env | cut -d= -f2 | tr -d '"')
if [ -n "$AUTH_DB_DIR" ] && [ -d "$AUTH_DB_DIR" ]; then
  sudo cp -a "$AUTH_DB_DIR" "$BACKUP_DIR/auth-db"
fi

# Restart services
docker compose up -d

echo "Backup complete: $BACKUP_DIR"
```

### Restore Procedure

```bash
#!/bin/bash
# restore-aithena.sh <backup_dir>

BACKUP_DIR=$1

# Stop all services
docker compose down

# Restore volumes
sudo tar -xzf $BACKUP_DIR/solr-data.tar.gz -C /source/volumes
sudo tar -xzf $BACKUP_DIR/zoo-data.tar.gz -C /source/volumes
sudo tar -xzf $BACKUP_DIR/rabbitmq-data.tar.gz -C /source/volumes
sudo tar -xzf $BACKUP_DIR/redis.tar.gz -C /source/volumes

# Restore auth database
AUTH_DB_DIR=$(grep '^AUTH_DB_DIR=' .env | cut -d= -f2 | tr -d '"')
if [ -n "$AUTH_DB_DIR" ] && [ -d "$BACKUP_DIR/auth-db" ]; then
  mkdir -p "$AUTH_DB_DIR"
  sudo cp -a "$BACKUP_DIR/auth-db/." "$AUTH_DB_DIR/"
fi

# Fix permissions
sudo chown -R 8983:8983 /source/volumes/solr-data*
sudo chown -R 1000:1000 /source/volumes/zoo-data*

# Start services
docker compose up -d

echo "Restore complete from: $BACKUP_DIR"
```

### Disaster Recovery

If full system failure:
1. Restore book library PDFs to `BOOKS_PATH`
2. Restore Solr/ZooKeeper volumes from backup
3. Start infrastructure: `docker compose up -d`
4. If no backup exists, re-index from scratch:
   ```bash
   docker compose up -d
   # Wait for solr-init to complete
   docker compose restart document-lister  # Triggers full library scan
   ```

## Enable HTTPS

The base Compose files run HTTP-only on port 80. To add Let's Encrypt TLS via
certbot, use the `docker-compose.ssl.yml` overlay:

1. **Create certbot volume directories:**

   ```bash
   sudo mkdir -p /source/volumes/certbot-data/{conf,www}
   ```

2. **Start the stack with SSL:**

   ```bash
   # Development (local build)
   docker compose -f docker-compose.yml -f docker-compose.ssl.yml up -d

   # Production (GHCR images)
   docker compose -f docker-compose.prod.yml -f docker-compose.ssl.yml up -d
   ```

3. **Obtain the initial certificate:**

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.ssl.yml \
     run --rm certbot certonly --webroot -w /var/www/certbot \
     -d your.domain.com --agree-tos -m you@example.com
   ```

4. **Add an HTTPS server block** to `src/nginx/default.conf` that references
   `/etc/letsencrypt/live/your.domain.com/`. Restart nginx after editing.

The certbot sidecar renews certificates automatically every 12 hours, and
nginx reloads every 6 hours to pick up renewed certificates.

> **Migrating from older setups:** If your deployment previously had certbot
> in the base compose file, add `-f docker-compose.ssl.yml` to your
> `docker compose` commands to restore the same behavior.

## Production Hardening Checklist

Before going to production, verify:

- [ ] Memory overcommit configured (`vm.overcommit_memory = 1`)
- [ ] `python3 -m installer` completed successfully — `.env` written, auth DB created, and generated secrets reviewed
- [ ] Volume directories created with correct ownership
- [ ] Firewall configured (only 80/443 public, block all other ports)
- [ ] SSL certificates configured in nginx if public-facing (see [Enable HTTPS](#enable-https) below)
- [ ] RabbitMQ credentials rotated away from `guest/guest` via `.env` (`RABBITMQ_USER` / `RABBITMQ_PASS`) or matching `default_user` / `default_pass` settings in `src/rabbitmq/rabbitmq.conf`
- [ ] Redis password set in `.env` (`REDIS_PASSWORD`) so Compose enables `redis-server --requirepass`
- [ ] Rotated credentials applied with `docker compose up -d --force-recreate redis rabbitmq redis-commander streamlit-admin document-lister document-indexer solr-search nginx`
- [ ] Admin endpoints protected by the nginx auth gate and login tested via `/admin/streamlit/`, `/admin/rabbitmq/`, and `/admin/redis/`
- [ ] Auth DB directory (`AUTH_DB_DIR`) included in backup rotation
- [ ] Backup cron job scheduled (daily at 2am: `0 2 * * * /opt/aithena/backup-aithena.sh`)
- [ ] Monitoring alerts configured (disk space, memory usage, service health)
- [ ] Log aggregation enabled (ship logs to central syslog/ELK)

## Support

For issues not covered in this guide:
- **GitHub Issues**: https://github.com/jmservera/aithena/issues
- **Logs**: Always include `docker compose logs` output
- **System Info**: Include `docker version`, `uname -a`, available RAM/disk

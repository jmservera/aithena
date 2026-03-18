---
name: "docker-compose-operations"
description: "Container lifecycle management for multi-service apps: rebuilding, volume permissions, orchestration, troubleshooting"
domain: "docker, infrastructure, operations"
confidence: "high"
source: "earned — production troubleshooting, verified in full stack rebuild session"
---

## Context
aithena uses Docker Compose to orchestrate 17 containers (Solr cluster, Redis, RabbitMQ, Python services, nginx, Streamlit). Small mistakes in container management can cause:
- Stale containers (code changes not picked up)
- Cascading failures (one service health affects others)
- Silent failures (volumes with wrong permissions)
- Service discovery issues (hostname resolution, port mapping)

This skill documents the hard lessons learned from production troubleshooting.

## Patterns

### 1. **Always Rebuild After Code Changes, Not Just Restart**

❌ **WRONG** — doesn't pick up code changes:
```bash
docker compose restart solr-search
# ERROR: container still runs old code from old image!
```

✅ **RIGHT** — rebuild then restart:
```bash
docker compose build solr-search
docker compose up -d solr-search
```

**Why:** `docker compose up` without `--build` reuses existing images. Images are immutable; code changes only exist in the Dockerfile. You must rebuild the image.

**Verification:**
```bash
# Check if container is actually new
docker compose logs solr-search | grep "version:"  # should show new git commit
```

### 2. **Check Image vs. Container Versions**

```bash
# Image version (what's built on disk)
docker image ls | grep solr-search

# Running container version
docker compose logs solr-search | head -20 | grep -E "version|commit|built"

# They might NOT match!
```

### 3. **Host Volume Permissions Must Match Container User**

❌ **WRONG** — Solr fails with cryptic error:
```bash
# volumes owned by root:root, Solr runs as UID 8983
ls -la /volumes/solr-data/
# drwxr-xr-x root root 755 /volumes/solr-data/

# Inside solr container:
# ERROR: "Couldn't persist core properties to /var/solr/data/books_shard1_replica_n4/core.properties"
```

✅ **RIGHT** — volumes owned by container user:
```bash
# Find UID from Dockerfile (USER 8983 in solr image)
sudo chown -R 8983:8983 /volumes/solr-data*

# Verify
ls -la /volumes/solr-data/
# drwxr-xr-x 8983 8983 755 /volumes/solr-data/

# Now collection creation works
```

**Key IDs by Service:**
- **Solr:** UID 8983 (`USER solr` in image)
- **Redis:** UID 999 (`USER redis`)
- **RabbitMQ:** UID 100 (`USER rabbitmq`)
- **nginx:** UID 101 (`USER nginx`)
- **Python services:** UID 1000 or running as root (check Dockerfile)

**How to Find UID:**
```bash
docker image inspect solr:latest | grep User
# or run container and check
docker run -it solr:latest id
```

### 4. **Solr Collection Creation Failures — Check Node Logs**

❌ **WRONG** — only check solr1:
```bash
docker compose logs solr1 | grep -i error
# Nothing helpful; "Underlying core creation failed"
```

✅ **RIGHT** — check all nodes (solr2, solr3):
```bash
docker compose logs solr2 | grep -i "couldn't\|permission\|error"
# Found it: "Couldn't persist core properties..."
```

**Why:** SolrCloud distributes replicas across nodes. If replica N4 is on solr2, you need solr2's logs.

### 5. **Service Health Checks and Circuit Breakers**

Aithena services expose health endpoints:
```bash
curl http://localhost:8080/health
# {
#   "solr": "CLOSED",      # ✅ healthy
#   "redis": "OPEN",       # ❌ circuit breaker tripped
#   "rabbitmq": "UNKNOWN"
# }
```

**Interpret Circuit Breaker States:**
- **CLOSED:** Healthy, all requests succeeding
- **OPEN:** Failing, requests are failing, breaker is protecting against cascading failures
- **HALF_OPEN:** Recovering, testing if dependency is back
- **UNKNOWN:** Not yet tested or dependency not required

**Example:** If Redis OPEN but code passes, likely a stale container (old code that tries to auth but fails).

### 6. **Cascading Failures**

When one service is down, others that depend on it will report failures:

```
Scenario: Redis is down
├── solr-search /stats → 503 (uses Redis for state)
├── solr-search /search → may work (searches don't strictly need Redis)
├── document-indexer → stalled (can't update state)
└── Rate limiting → broken (relies on Redis)

When you fix Redis:
├── Restart solr-search (old connection in pool)
├── Restart document-indexer
└── Health checks show CLOSED again
```

**Lesson:** When you see cascading failures, fix the root service first, then restart dependent services.

### 7. **Container Startup Order and Dependencies**

In docker-compose.yml:
```yaml
services:
  solr1:
    depends_on:
      - zookeeper  # declared, but...
      - solr2      # solr cluster nodes
      - solr3

  solr-search:
    depends_on:
      - solr1      # solr-search waits for solr1
      - redis
      - rabbitmq
```

**Important:** `depends_on` means "start this first, but don't wait for health checks". Always add `condition: service_healthy` for critical dependencies:

```yaml
solr-search:
  depends_on:
    solr1:
      condition: service_healthy
    redis:
      condition: service_healthy
    rabbitmq:
      condition: service_healthy
```

### 8. **Volume Mounts and Permissions**

```yaml
services:
  solr1:
    volumes:
      - ./volumes/solr-data1:/var/solr/data  # host:container
      # host path must exist with correct permissions BEFORE container starts
```

**Setup:**
```bash
# Create volumes with correct permissions
mkdir -p volumes/solr-data{1,2,3}
sudo chown -R 8983:8983 volumes/solr-data*
chmod 755 volumes/solr-data*

# Verify before starting
ls -la volumes/ | grep solr
```

### 9. **Image Layer Caching**

Docker caches image layers. On rebuild:
```bash
docker compose build solr-search --no-cache  # rebuild everything
docker compose build solr-search              # reuse cached layers
```

**When to use `--no-cache`:**
- First build
- After major dependency changes
- If you suspect stale layer

**When to use cached build:**
- Regular development (fast)
- After code-only changes (Python files)

### 10. **Debugging: Interactive Shell in Container**

```bash
# Run bash in running container
docker compose exec solr-search bash

# Or start new container (doesn't require service running)
docker run -it python:3.12-slim bash
```

**Common debugging inside container:**
```bash
# Check Python version
python --version

# Check if module installed
python -c "import package; print(package.__version__)"

# Check file permissions
ls -la /app/

# Check network
curl http://redis:6379/  # check hostname resolution
```

### 11. **Docker Compose Validation**

Without Docker daemon (codespaces environment):
```bash
# Validate syntax
python3 -c "import yaml; yaml.safe_load(open('docker-compose.yml'))"

# Validate shell scripts
bash -n buildall.sh
```

## Examples

Reference scenarios from aithena:
- `src/solr/add-conf-overlay.sh` — configures Solr handlers after startup
- `docker-compose.yml` — health checks for all services
- `.github/workflows/ci.yml` — Docker image building in CI
- `buildall.sh` — orchestrates build and startup

## Anti-Patterns

- **Don't just restart containers after code changes** — rebuild first
- **Don't assume volume ownership is correct** — always set explicitly
- **Don't check solr1 logs for cluster issues** — check the replica's node
- **Don't stack multiple services under `depends_on` without health checks** — startup order becomes unpredictable
- **Don't reuse old volumes with permission issues** — recreate them
- **Don't rebuild all images when only one changed** — target rebuild by service
- **Don't run as root in Python containers unless necessary** — use non-root user for security
- **Don't mount volumes as read-only (`:ro`) for services that write** — causes silent failures

## Verification Checklist

After rebuilding services:
```bash
# 1. Images built with new code
docker image ls | grep -E "solr-search|document-indexer"

# 2. Containers running
docker compose ps

# 3. Health checks passing
curl http://localhost:8080/health

# 4. Logs show new version/commit
docker compose logs solr-search | head -5

# 5. Volumes have correct permissions (if applicable)
ls -la /volumes/

# 6. Services can reach each other
docker compose exec solr-search curl http://redis:6379/
```

## Scope & Enforcement

Applies to:
- Local development (buildall.sh, manual restarts)
- CI/CD (docker compose build in workflows)
- Production deployment (operators using docker-compose.yml)

Learned from:
- Full-stack rebuild session (March 2026)
- Security audit and patching
- Multi-service orchestration (Python + Solr + infrastructure)

# Post-Restore Verification Tests

Automated test suite that validates system integrity after a backup restore
operation. Implements the checks from
[PRD Section 5.3](../../docs/prd/bcdr-plan.md).

## Quick Start

### Shell script (standalone, all 9 checks)

```bash
# Basic run (requires running Docker stack)
./tests/verify-restore.sh

# With auth credentials
VERIFY_USERNAME=admin VERIFY_PASSWORD=secret ./tests/verify-restore.sh
```

### Python tests (unit + integration)

```bash
cd tests/restore

# Unit tests only (no Docker needed)
pip install -r requirements-restore.txt
pytest test_verify_checks.py -v

# Integration tests (requires running Docker stack)
pytest test_verify_restore.py -v -m docker

# All tests
pytest -v
```

## Verification Checks

| # | Check | Shell | Python Unit | Python Integration |
|---|-------|:-----:|:-----------:|:------------------:|
| 1 | All services healthy (`docker-compose ps`) | ✅ | ✅ | ✅ |
| 2 | Admin UI loads | ✅ | ✅ | ✅ |
| 3 | Auth login works | ✅ | ✅ | ✅ |
| 4 | Search returns results | ✅ | ✅ | ✅ |
| 5 | Redis PING → PONG | ✅ | ✅ | ✅ |
| 6 | RabbitMQ management accessible | ✅ | ✅ | ✅ |
| 7 | Solr cluster replicas healthy | ✅ | ✅ | ✅ |
| 8 | No errors in logs | ✅ | ✅ | ✅ |
| 9 | Disk usage reasonable | ✅ | ✅ | ✅ |

## Markers

- `@pytest.mark.docker` — requires Docker daemon and running stack
- `@pytest.mark.solr` — Solr-specific checks
- `@pytest.mark.redis` — Redis-specific checks
- `@pytest.mark.rabbitmq` — RabbitMQ-specific checks
- `@pytest.mark.auth` — Auth/collections DB checks
- `@pytest.mark.services` — Docker Compose service health checks

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SOLR_URL` | `http://localhost:8983/solr/books` | Solr collection URL |
| `SEARCH_API_URL` | `http://localhost:8080` | solr-search API URL |
| `ADMIN_URL` | `http://localhost/admin` | Admin UI URL |
| `RABBITMQ_API_URL` | `http://localhost:15672` | RabbitMQ management URL |
| `RABBITMQ_USER` | `guest` | RabbitMQ username |
| `RABBITMQ_PASSWORD` | `guest` | RabbitMQ password |
| `REDIS_HOST` | `localhost` | Redis host |
| `REDIS_PORT` | `6379` | Redis port |
| `VERIFY_USERNAME` | _(empty)_ | Test username for auth |
| `VERIFY_PASSWORD` | _(empty)_ | Test password for auth |
| `VERIFY_TIMEOUT` | `30` | Per-check timeout (seconds) |
| `DISK_MAX_PERCENT` | `90` | Max disk usage threshold |

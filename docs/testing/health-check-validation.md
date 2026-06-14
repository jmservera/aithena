# Health Check Validation for Shared Docker Base

Issue: `#1750`
Branch: `squad/1750-validate-health-checks`

## Scope

Validated the Python services that now inherit from `aithena:base`:

- `document-indexer`
- `document-lister`
- `solr-search`

`embeddings-server` was intentionally excluded because it keeps its own base image.

## Commands Run

```bash
docker compose --profile production config > /dev/null
docker build -f Dockerfile.base -t aithena:base .
docker compose build document-indexer document-lister solr-search
tests/test-compose-health.sh
```

## Health Check Behavior

All three images inherit the shared health check command:

```text
python /usr/local/bin/python-service-healthcheck.py
```

Mode by service:

| Service | Mode | Probe |
|---|---|---|
| `document-indexer` | `process` | `HEALTHCHECK_PROCESS=document_indexer` |
| `document-lister` | `process` | `HEALTHCHECK_PROCESS=document_lister` |
| `solr-search` | `http` | `HEALTHCHECK_URL=http://localhost:8080/health` |

Image timing settings were identical across services:

- `interval=30s`
- `timeout=10s`
- `retries=3`
- `start_period=30s`

## Test Results

`tests/test-compose-health.sh` starts only the three Python service images, waits up to 60 seconds for Docker health to turn `healthy`, checks startup logs for errors, and cleans up containers automatically.

Observed results:

| Service | Result | Time to healthy |
|---|---|---|
| `document-indexer` | healthy | 6s |
| `document-lister` | healthy | 5s |
| `solr-search` | healthy | 6s |

Startup log review found no `error`, `failed`, `exception`, `critical`, or `traceback` output for any of the three containers.

## Regression Check

No regression was observed versus the pre-shared-base Dockerfiles:

- `docker compose` production config still validates
- all three service images still build successfully
- entrypoint/command wiring still allows each image to become healthy under its configured probe mode
- the shared base adds health checks without introducing startup log noise

## Notes

- This validation intentionally did **not** start Solr, ZooKeeper, Redis, RabbitMQ, or the rest of the full stack.
- For the isolated `solr-search` health-check test, the script runs a minimal local HTTP server in the container and overrides `HEALTHCHECK_URL` to `/` so the shared HTTP probe can be validated without external dependencies.

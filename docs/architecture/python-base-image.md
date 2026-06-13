# Shared Python Docker base image

Issue #1748 extracts the common runtime used by Aithena's standard Python services into a single root-level `Dockerfile.base`.

## What lives in `Dockerfile.base`

- `python:3.12-slim-bookworm`
- `uv` copied from `ghcr.io/astral-sh/uv`
- shared system packages: `gosu`, `procps`, `sqlite3`, `libgomp1`, `libstdc++6`
- the `app` user/group (`uid/gid 1000`)
- a shared Docker `HEALTHCHECK` that runs `docker/python-service-healthcheck.py`

The healthcheck script uses environment variables so child images keep a common pattern:

- `HEALTHCHECK_MODE=http` + `HEALTHCHECK_URL=http://localhost:8080/health`
- `HEALTHCHECK_MODE=process` + `HEALTHCHECK_PROCESS=document_lister`

## Services using the shared base

These Dockerfiles now use `FROM aithena:base`:

1. `src/document-indexer/Dockerfile`
2. `src/document-lister/Dockerfile`
3. `src/solr-search/Dockerfile`

## Why `embeddings-server` is still separate

`src/embeddings-server/Dockerfile` intentionally stays on `ghcr.io/jmservera/embeddings-server-base:${BASE_TAG}`.

That image carries the heavyweight model/runtime layers and the OpenVINO validation flow introduced for issue #1662. Replacing it with `aithena:base` would force every rebuild to recreate those large layers locally and would discard the existing drift checks tied to the specialized base image.

## Admin service note

The repository no longer has a standalone Python `admin` container. Admin APIs now live inside `solr-search`, so there are three standard Python service Dockerfiles plus the specialized embeddings image.

## Build order

Build the base image first:

```bash
docker build -f Dockerfile.base -t aithena:base .
```

Then build services normally:

```bash
docker build -f src/document-lister/Dockerfile -t aithena:document-lister src/document-lister
docker build -f src/document-indexer/Dockerfile -t aithena:document-indexer src/document-indexer
docker build -f src/solr-search/Dockerfile -t aithena:solr-search .
```

`buildall.sh` now builds `aithena:base` before running `docker compose up --build -d`, so the repo's bulk-build path stays working.

## Compose behavior

`docker-compose.yml` keeps runtime env vars and dependencies, but the healthcheck definitions for `document-lister`, `document-indexer`, and `solr-search` now come from their images instead of Compose.

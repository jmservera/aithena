# New Python service bootstrap

Use this checklist when adding a standard Python service to Aithena. If the service needs a specialized runtime like `embeddings-server`, document the exception explicitly instead of forcing it onto `aithena:base`.

## 1. Create the service skeleton

Create a new directory at `src/<service>/` with:

- `Dockerfile`
- `pyproject.toml`
- `uv.lock`
- `<service_package>/`
- `tests/`
- `entrypoint.sh` if the service needs startup logic beyond `python -m ...`

The shared build tooling only auto-discovers Python services that have both a `Dockerfile` and `pyproject.toml`.

## 2. Start from `aithena:base`

Standard Python Dockerfiles should follow this pattern:

```Dockerfile
ARG BASE_IMAGE=aithena:base
ARG VERSION=dev
ARG GIT_COMMIT=unknown
ARG BUILD_DATE=unknown
FROM ${BASE_IMAGE}
ARG VERSION
ARG GIT_COMMIT
ARG BUILD_DATE
LABEL org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.source="https://github.com/jmservera/aithena" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${GIT_COMMIT}"
ENV VERSION=${VERSION} GIT_COMMIT=${GIT_COMMIT} BUILD_DATE=${BUILD_DATE} \
    HEALTHCHECK_MODE=http HEALTHCHECK_URL=http://localhost:8080/health
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --native-tls
COPY <service_package> /app/<service_package>
USER app
CMD ["python", "-m", "<service_package>"]
```

Use `HEALTHCHECK_MODE=http` for HTTP services and `HEALTHCHECK_MODE=process` plus `HEALTHCHECK_PROCESS=<process_name>` for worker-style services.

See [Shared Python Base Image](../architecture/python-base-image.md) for the full contract.

## 3. Register the service in Compose

Add the service to `docker-compose.yml` with:

- a `build:` section with `VERSION`, `GIT_COMMIT`, and `BUILD_DATE` args
- runtime `environment:` values
- `depends_on:` with `condition: service_healthy` where startup ordering matters
- `volumes:` for any required read/write paths
- `restart:` and resource limits consistent with the service type

Also update related overlays when needed:

- `docker/compose.prod.yml` if the service ships as a published production image
- `docker/compose.dev-ports.yml` if you need a host port during local development
- nginx or admin docs if the service becomes operator-facing

## 4. Let repo automation discover it

Once the files are in place:

- `./buildall.sh` will auto-discover the service through `scripts/lib/build-services.sh`
- `make lint-<service>` and `make format-<service>` will appear automatically from `pyproject.toml`
- `make test-<service>` will appear automatically when the service also has a `tests/` directory
- `.squad/scripts/verify.sh` will include the service when its files change

This is the preferred pattern; do not hard-code new service lists into shell scripts unless the service is intentionally exceptional.

## 5. Verify before opening the PR

Run the smallest useful checks first:

```bash
make lint-<service>
make test-<service>
docker build -f src/<service>/Dockerfile -t aithena:<service> src/<service>
```

If the service needs shared repo code outside `src/<service>/`, use the repository root as the build context and point `dockerfile:` at `src/<service>/Dockerfile`, following the `solr-search` pattern.

Then run the repo gate:

```bash
.squad/scripts/verify.sh
```

If the new service changes shared Docker behavior, finish with:

```bash
./buildall.sh
```

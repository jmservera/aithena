ARG VERSION=dev
ARG GIT_COMMIT=unknown
ARG BUILD_DATE=unknown

# ---------- build stage ----------
FROM python:3.12-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY src/aithena-common/ /aithena-common/
COPY src/solr-search/pyproject.toml src/solr-search/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --native-tls

COPY src/solr-search/ .

# ---------- runtime stage ----------
FROM python:3.12-slim-bookworm AS runtime

ARG VERSION
ARG GIT_COMMIT
ARG BUILD_DATE

LABEL org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.source="https://github.com/jmservera/aithena" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${GIT_COMMIT}"

ENV VERSION=${VERSION} \
    GIT_COMMIT=${GIT_COMMIT} \
    BUILD_DATE=${BUILD_DATE} \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends wget gosu sqlite3 && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 1000 app && useradd --system --uid 1000 --gid app --create-home app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/*.py /app/
COPY --from=builder /app/migrations /app/migrations
COPY --from=builder /app/scripts /app/scripts

ENV PATH="/app/.venv/bin:${PATH}"

ENV SOLR_URL="http://solr:8983/solr"
ENV SOLR_COLLECTION="books"
ENV BASE_PATH="/data/documents"
ENV CORS_ORIGINS="http://localhost:5173"

RUN mkdir -p /data/documents/uploads /data/auth /data/collections && chown -R app:app /data

COPY src/solr-search/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["sh","-c","python -m uvicorn --port=$PORT --host 0.0.0.0 main:app"]

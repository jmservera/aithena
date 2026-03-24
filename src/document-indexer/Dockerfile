ARG VERSION=dev
ARG GIT_COMMIT=unknown
ARG BUILD_DATE=unknown

# ---------- build stage ----------
FROM python:3.12-alpine AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --native-tls

COPY . .

# ---------- runtime stage ----------
FROM python:3.12-alpine AS runtime

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
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apk add --no-cache procps libstdc++ libgomp libgcc

RUN addgroup -S -g 1000 app && adduser -S -u 1000 -G app app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/document_indexer /app/document_indexer

RUN mkdir -p /data/thumbnails && chown app:app /data/thumbnails

RUN chown -R app:app /app

ENV PATH="/app/.venv/bin:${PATH}"

ENV RABBITMQ_HOST="localhost"
ENV RABBITMQ_PORT=5672
ENV REDIS_HOST="localhost"
ENV REDIS_PORT=6379
ENV QUEUE_NAME="new_documents"
ENV EXCHANGE_NAME="documents"
ENV BASE_PATH="/data/documents/"
ENV SOLR_HOST="solr"
ENV SOLR_PORT=8983
ENV SOLR_COLLECTION="books"

USER app

CMD ["python", "-m", "document_indexer"]

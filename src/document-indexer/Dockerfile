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

ENV VERSION=${VERSION} \
    GIT_COMMIT=${GIT_COMMIT} \
    BUILD_DATE=${BUILD_DATE} \
    RABBITMQ_HOST=localhost \
    RABBITMQ_PORT=5672 \
    REDIS_HOST=localhost \
    REDIS_PORT=6379 \
    QUEUE_NAME=new_documents \
    EXCHANGE_NAME=documents \
    BASE_PATH=/data/documents/ \
    SOLR_HOST=solr \
    SOLR_PORT=8983 \
    SOLR_COLLECTION=books \
    HEALTHCHECK_MODE=process \
    HEALTHCHECK_PROCESS=document_indexer

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --native-tls

COPY document_indexer /app/document_indexer
RUN mkdir -p /data/thumbnails \
    && chown -R app:app /app /data/thumbnails

USER app

CMD ["python", "-m", "document_indexer"]

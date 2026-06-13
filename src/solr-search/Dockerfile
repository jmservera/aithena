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
    PORT=8080 \
    SOLR_URL=http://solr:8983/solr \
    SOLR_COLLECTION=books \
    BASE_PATH=/data/documents \
    CORS_ORIGINS=http://localhost:5173 \
    HEALTHCHECK_MODE=http \
    HEALTHCHECK_URL=http://localhost:8080/health

COPY src/aithena-common/ /aithena-common/
COPY src/solr-search/pyproject.toml src/solr-search/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --native-tls

COPY src/solr-search/*.py /app/
COPY src/solr-search/migrations /app/migrations
COPY src/solr-search/scripts /app/scripts
COPY src/solr-search/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh \
    && mkdir -p /data/documents/uploads /data/auth /data/collections \
    && chown -R app:app /app /data

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["sh","-c","python -m uvicorn --port=$PORT --host 0.0.0.0 main:app"]

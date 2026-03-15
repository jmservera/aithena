ARG VERSION=dev
ARG GIT_COMMIT=unknown
ARG BUILD_DATE=unknown

FROM python:3.11-slim-bookworm

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

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends wget && rm -rf /var/lib/apt/lists/*

COPY solr-search/pyproject.toml solr-search/uv.lock ./

RUN uv pip install --system --no-cache -r pyproject.toml
COPY solr-search/ .

ENV SOLR_URL="http://solr:8983/solr"
ENV SOLR_COLLECTION="books"
ENV BASE_PATH="/data/documents"
ENV CORS_ORIGINS="http://localhost:5173"

CMD ["sh","-c","python -m uvicorn --port=$PORT --host 0.0.0.0 main:app"]

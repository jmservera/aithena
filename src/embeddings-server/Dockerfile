# syntax=docker/dockerfile:1

ARG VERSION=dev
ARG GIT_COMMIT=unknown
ARG BUILD_DATE=unknown
ARG BASE_TAG=3.12-slim-multilingual-e5-base
ARG INSTALL_OPENVINO=false

FROM ghcr.io/jmservera/embeddings-server-base:${BASE_TAG}

ARG VERSION
ARG GIT_COMMIT
ARG BUILD_DATE
ARG INSTALL_OPENVINO

LABEL org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.source="https://github.com/jmservera/aithena" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.revision="${GIT_COMMIT}"

ENV VERSION=${VERSION} \
    GIT_COMMIT=${GIT_COMMIT} \
    BUILD_DATE=${BUILD_DATE} \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    MODEL_NAME=intfloat/multilingual-e5-base \
    HF_HOME=/models/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/models/sentence_transformers \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    DEVICE=cpu \
    BACKEND=torch

WORKDIR /app

# Ensure root for package installation (openvino base image runs as non-root)
USER root

RUN apt-get update && apt-get install -y --no-install-recommends wget && rm -rf /var/lib/apt/lists/*

RUN if ! id -u app >/dev/null 2>&1; then \
      groupadd --system --gid 1000 app 2>/dev/null || groupadd --system app; \
      useradd --system --uid 1000 --gid app --create-home app 2>/dev/null || useradd --system --gid app --create-home app; \
    fi

# Copy lock files first for cache invalidation
COPY pyproject.toml uv.lock ./

# Install app-specific deps into the base image's .venv using --inexact
# (preserves heavy pre-installed packages, only adds the delta).
# uv is bind-mounted from its official image — never installed in the layer.
RUN --mount=from=ghcr.io/astral-sh/uv:latest,source=/uv,target=/usr/local/bin/uv \
    if [ "$INSTALL_OPENVINO" = "true" ]; then \
      uv sync --frozen --no-dev --no-install-project --extra openvino --inexact --native-tls; \
    else \
      uv sync --frozen --no-dev --no-install-project --inexact --native-tls; \
    fi

ENV PATH="/app/.venv/bin:${PATH}"

COPY --chown=app:app main.py model_utils.py /app/
COPY --chown=app:app config /app/config

# Only chown /app (tiny). Don't chown /models — it duplicates the entire
# ~5 GB model directory as a new layer. Models are read-only; just ensure
# world-readable permissions (small metadata-only layer).
RUN chown -R app:app /app && chmod -R a+rX /models

# Writable cache dir for OpenVINO compiled-model cache.
# OpenVINO tries to create model_cache inside /models/ which is read-only.
# Redirect via OPENVINO_CACHE_DIR to avoid permission errors (~4 KB layer).
RUN mkdir -p /app/ov_cache && chown app:app /app/ov_cache
ENV OPENVINO_CACHE_DIR=/app/ov_cache

EXPOSE 8080

USER app

CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT}"]

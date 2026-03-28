ARG VERSION=dev
ARG GIT_COMMIT=unknown
ARG BUILD_DATE=unknown
ARG BASE_TAG=3.12-slim-multilingual-e5-base
ARG INSTALL_OPENVINO=false

# ── Stage 1: dependencies (changes when pyproject.toml / uv.lock change) ──
FROM python:3.12-slim AS dependencies

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --native-tls

# Optionally install OpenVINO for Intel GPU support
ARG INSTALL_OPENVINO=false
RUN if [ "$INSTALL_OPENVINO" = "true" ]; then \
      uv sync --frozen --no-dev --no-install-project --extra openvino --native-tls; \
    fi

# ── Stage 2: runtime (base image already contains the cached model) ──
FROM ghcr.io/jmservera/embeddings-server-base:${BASE_TAG} AS runtime

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

COPY --from=dependencies /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:${PATH}"

COPY main.py model_utils.py /app/
COPY config /app/config

RUN chown -R app:app /app /models

EXPOSE 8080

USER app

CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT}"]

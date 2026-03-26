ARG VERSION=dev
ARG GIT_COMMIT=unknown
ARG BUILD_DATE=unknown
ARG MODEL_CACHE_IMAGE=ghcr.io/jmservera/embeddings-server-base:3.12-slim-multilingual-e5-base

# ── Stage 1: model-cache (pre-built base image with cached model) ──
# To use a different model, override MODEL_CACHE_IMAGE and MODEL_NAME together.
FROM ${MODEL_CACHE_IMAGE} AS model-cache

# ── Stage 2: dependencies (changes when pyproject.toml / uv.lock change) ──
FROM python:3.12-slim AS dependencies

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --native-tls

# ── Stage 3: app-builder (changes most frequently — every code edit) ──
FROM dependencies AS app-builder

COPY main.py model_utils.py ./
COPY config ./config

# ── Stage 4: runtime (slim final image) ──
FROM python:3.12-slim AS runtime

ARG VERSION
ARG GIT_COMMIT
ARG BUILD_DATE
# MODEL_NAME must match the model cached in MODEL_CACHE_IMAGE
ARG MODEL_NAME=intfloat/multilingual-e5-base

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
    MODEL_NAME=${MODEL_NAME} \
    HF_HOME=/models/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/models/sentence_transformers \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends wget && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 1000 app && useradd --system --uid 1000 --gid app --create-home app

COPY --from=app-builder /app/.venv /app/.venv
COPY --from=model-cache /models /models
COPY --from=app-builder /app/main.py /app/main.py
COPY --from=app-builder /app/model_utils.py /app/model_utils.py
COPY --from=app-builder /app/config /app/config

RUN chown -R app:app /app /models

ENV PATH="/app/.venv/bin:${PATH}"

EXPOSE 8080

USER app

CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT}"]

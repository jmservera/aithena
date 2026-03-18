ARG VERSION=dev
ARG GIT_COMMIT=unknown
ARG BUILD_DATE=unknown

FROM python:3.12-slim

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
    MODEL_NAME=sentence-transformers/distiluse-base-multilingual-cased-v2 \
    HF_HOME=/models/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/models/sentence_transformers

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends wget && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /models

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${MODEL_NAME}')"

COPY main.py ./
COPY config ./config

EXPOSE 8080

CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT}"]

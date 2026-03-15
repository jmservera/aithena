FROM python:3.11-alpine
ENV PYTHONUNBUFFERED=1

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

RUN apk add --no-cache procps

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev --no-install-project

COPY . .

ENV RABBITMQ_HOST="localhost"
ENV RABBITMQ_PORT=5672
ENV REDIS_HOST="localhost"
ENV REDIS_PORT=6379
ENV QUEUE_NAME="new_documents"
ENV BASE_PATH="/data/documents/"
ENV SOLR_HOST="solr"
ENV SOLR_PORT=8983
ENV SOLR_COLLECTION="books"

CMD ["uv", "run", "python", "-m", "document_indexer"]

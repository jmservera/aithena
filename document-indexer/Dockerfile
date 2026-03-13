FROM python:3.11-alpine
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .

RUN apk add --no-cache procps && pip install --no-cache-dir -r requirements.txt
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

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD pgrep -f document_indexer > /dev/null || exit 1

CMD ["python","-m","document_indexer"]

FROM python:3.11-alpine
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .

RUN pip install -r requirements.txt
COPY . .

ENV RABBITMQ_HOST="localhost"
ENV RABBITMQ_PORT=5672
ENV REDIS_HOST="localhost"
ENV REDIS_PORT=6379
ENV QUEUE_NAME="new_documents"
ENV EMBEDDINGS_HOST="localhost"
ENV EMBEDDINGS_PORT=8000
ENV EMBEDDINGS_TIMEOUT=1800
ENV EMBEDDIGNS_BATCH=-1
ENV QDRANT_HOST="localhost"
ENV QDRANT_PORT=6333
ENV STORAGE_ACCOUNT_NAME=""
ENV STORAGE_CONTAINER=""
ENV QDRANT_COLLECTION="aithena"
ENV QDRANT_VECTOR_DIM=4096

CMD ["python","-m","document_indexer"]


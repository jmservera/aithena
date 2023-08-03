FROM node:19 as builder

COPY aithena-ui/ .
RUN npm install && npm run build

FROM python:3.11-slim-bookworm
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

WORKDIR /app
COPY qdrant-search/requirements.txt .

RUN pip install -r requirements.txt
COPY qdrant-search/ .

COPY --from=builder /dist /app/static

ENV EMBEDDINGS_HOST="localhost"
ENV EMBEDDINGS_PORT=8000
ENV QDRANT_HOST="localhost"
ENV QDRANT_PORT=6333
ENV STORAGE_ACCOUNT_NAME=""
ENV STORAGE_CONTAINER=""
ENV EMBEDDINGS_TIMEOUT=3600
ENV CHAT_HOST="localhost"
ENV CHAT_PORT=8001

CMD ["sh","-c","python -m uvicorn --port=$PORT --host 0.0.0.0 main:app"]

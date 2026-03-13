FROM node:19 AS builder

COPY aithena-ui/ .
RUN npm install && npm run build

FROM python:3.11-slim-bookworm
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

WORKDIR /app
COPY solr-search/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt
COPY solr-search/ .

COPY --from=builder /dist /app/static

ENV SOLR_HOST="localhost"
ENV SOLR_PORT=8983
ENV SOLR_COLLECTION="books"
ENV DOCUMENTS_BASE_URL="/documents"

CMD ["sh", "-c", "python -m uvicorn --port=$PORT --host 0.0.0.0 main:app"]

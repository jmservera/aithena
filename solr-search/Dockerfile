FROM python:3.11-slim-bookworm
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

WORKDIR /app
COPY solr-search/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt
COPY solr-search/ .

ENV SOLR_URL="http://solr:8983/solr"
ENV SOLR_COLLECTION="books"
ENV BASE_PATH="/data/documents"
ENV CORS_ORIGINS="http://localhost:5173"

CMD ["sh","-c","python -m uvicorn --port=$PORT --host 0.0.0.0 main:app"]

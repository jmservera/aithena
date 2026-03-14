FROM python:3.11-slim-bookworm
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY solr-search/pyproject.toml solr-search/uv.lock ./

RUN uv pip install --system --no-cache -r pyproject.toml
COPY solr-search/ .

ENV SOLR_URL="http://solr:8983/solr"
ENV SOLR_COLLECTION="books"
ENV BASE_PATH="/data/documents"
ENV CORS_ORIGINS="http://localhost:5173"

CMD ["sh","-c","python -m uvicorn --port=$PORT --host 0.0.0.0 main:app"]

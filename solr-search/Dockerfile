FROM python:3.11-slim-bookworm
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV SOLR_HOST="localhost"
ENV SOLR_PORT=8983
ENV SOLR_COLLECTION="books"
ENV EMBEDDINGS_HOST="localhost"
ENV EMBEDDINGS_PORT=8085
ENV DEFAULT_SEARCH_MODE="keyword"

CMD ["python", "-m", "uvicorn", "--port", "8080", "--host", "0.0.0.0", "main:app"]

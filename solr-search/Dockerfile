FROM python:3.11-alpine
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV SOLR_HOST="solr1"
ENV SOLR_PORT=8983
ENV SOLR_COLLECTION="books"
ENV DOCUMENT_BASE_URL="/api/documents"
ENV PORT=8080

CMD ["python", "main.py"]

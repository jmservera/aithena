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
ENV STORAGE_ACCOUNT_NAME=""
ENV STORAGE_CONTAINER=""
ENV DOCUMENT_WILDCARD=".pdf"

CMD ["python","-m","document_lister"]


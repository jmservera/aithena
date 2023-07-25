FROM python:3.11-slim-bookworm
ENV PYTHONUNBUFFERED=1
ENV PORT=8083

WORKDIR /app
COPY requirements.txt .

RUN pip install -r requirements.txt
COPY . .

ENV QDRANT_HOST="localhost"
ENV QDRANT_PORT=6333

CMD ["sh","-c","python -m uvicorn --port=$PORT --host 0.0.0.0 main:app"]

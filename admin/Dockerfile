FROM python:3.11-slim-bookworm
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY src/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY src/ .

# Runtime defaults — override via docker-compose environment or .env
ENV REDIS_HOST="localhost"
ENV REDIS_PORT=6379
ENV QUEUE_NAME="shortembeddings"

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]

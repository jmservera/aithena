FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY src ./src

ENV PATH="/app/.venv/bin:${PATH}"

EXPOSE 8501

CMD ["streamlit", "run", "src/main.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.baseUrlPath=/admin/streamlit", "--server.headless=true", "--browser.gatherUsageStats=false"]

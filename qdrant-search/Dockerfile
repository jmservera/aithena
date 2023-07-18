FROM python:3.11-alpine
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

WORKDIR /app
COPY requirements.txt .

RUN pip install -r requirements.txt
COPY . .

CMD ["sh","-c","python -m waitress --port=$PORT main:app"]


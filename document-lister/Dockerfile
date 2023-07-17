FROM python:3.11-alpine
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .

RUN pip install -r requirements.txt
COPY . .

VOLUME ["/documents"]

CMD ["python","-m","document_lister"]


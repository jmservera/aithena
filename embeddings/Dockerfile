ARG TAG=latest
FROM aithena-llama-base:${TAG}

WORKDIR /embeddings
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .


CMD ["waitress-serve","--port","5000","main:app"]


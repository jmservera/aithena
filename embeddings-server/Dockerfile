FROM semitechnologies/transformers-inference:custom
RUN MODEL_NAME=sentence-transformers/distiluse-base-multilingual-cased-v2 ./download.py

HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=5 \
  CMD wget -q --spider http://localhost:8080/.well-known/ready || exit 1

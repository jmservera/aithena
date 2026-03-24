FROM solr:9.7

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-liberation fonts-dejavu-core && \
    rm -rf /var/lib/apt/lists/*
USER solr

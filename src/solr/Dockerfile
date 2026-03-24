ARG VERSION=dev
ARG GIT_COMMIT=unknown
ARG BUILD_DATE=unknown

FROM solr:9.7

USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-liberation fonts-dejavu-core && \
    rm -rf /var/lib/apt/lists/*
USER solr

LABEL org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${GIT_COMMIT}" \
      org.opencontainers.image.created="${BUILD_DATE}"

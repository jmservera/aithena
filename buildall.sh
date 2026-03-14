#!/bin/bash

TAG=cpu-v0.1

# Detect Python services with pyproject.toml and sync with uv
PYTHON_SERVICES=(admin/src document-indexer document-lister e2e qdrant-clean qdrant-search solr-search)

for service in "${PYTHON_SERVICES[@]}"; do
    if [ -f "$service/pyproject.toml" ]; then
        echo "Syncing $service with uv..."
        (cd "$service" && uv sync)
    fi
done

docker compose up --build -d

# convert openllama model
if [ "$1" = "-n" ]; then
    echo "Do not generate model"
else
    pushd ..
    docker exec -it aithena-llama-base-1 python3 convert.py models/7B
    popd
fi

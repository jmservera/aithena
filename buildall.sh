#/bin/bash

TAG=cpu-v0.1

docker compose up --build -d

# convert openllama model
if [ "$1" = "-n" ]; then
    echo "Do not generate model"
else
    pushd ..
    docker exec -it aithena-llama-base-1 python3 convert.py models/7B
    popd
fi

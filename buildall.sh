#/bin/bash

TAG=cpu-v0.1

pushd ..
git clone https://huggingface.co/openlm-research/open_llama_7b
popd

pushd docker && docker build . -f Dockerfile.llama -t llama-base:$TAG -t llama-base:latest
popd

# convert openllama model
if [ "$1" = "-n" ]; then
    echo "Do not build model"
else
    pushd ..
    docker run -v $(pwd)/open_llama_7b/:/llama/models/7B/ -it --rm llama-base:$TAG python3 convert.py models/7B
    popd
fi

pushd embeddings && docker build . --build-arg "TAG=${TAG}" -f Dockerfile.embeddings -t llama-embeddings:$TAG -t llama-embeddings:latest && popd

pushd .. && docker run -v $(pwd)/open_llama_7b/:/llama/models/7B/ -it -p 5000:5000 --rm llama-embeddings:$TAG && popd
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1
ENV MODEL_PATH="/llama/models/ggml-model-f16.bin"
VOLUME [ "/llama/models" ]

RUN apt update && apt install build-essential -y && \
    rm -rf /var/lib/apt/lists/*

RUN pip install llama-cpp-python[server]

CMD ["sh","-c","python -m llama_cpp.server --model \"${MODEL_PATH}\" --host \"0.0.0.0\""]

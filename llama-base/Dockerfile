# A docker file to build LLaMA and provide a CLI to convert and run files
FROM gcc:13.1.0 as builder
# Uncomment the following line to use the Intel GPU
# and use it with docker run --privileged --device="/dev/dri" --device=/dev/dxg -v /usr/lib/wsl:/usr/lib/wsl --net=host -e LIBVA_DRIVER_NAME=iHD -e DISPLAY=$DISPLAY -it -v $(pwd)/open_llama_7b/:/llama/models/7B/ llamabuild sh
# RUN apt install intel-opencl-icd clinfo -y
# ENV LLAMA_CLBLAST=1

WORKDIR /llama
RUN git clone https://github.com/ggerganov/llama.cpp

RUN apt update && apt install libclblast-dev -y
RUN cd llama.cpp && \
    make LLAMA_CLBLAST=${LLAMA_CLBLAST}

RUN apt install python3-pip python3-venv -y

RUN python3 -m venv /llama/llamavenv
RUN . /llama/llamavenv/bin/activate && cd /llama/llama.cpp && python3 -m pip install -r requirements.txt

COPY llamacpp.requirements.txt .
RUN . /llama/llamavenv/bin/activate && cd /llama && python3 -m pip install -r llamacpp.requirements.txt

FROM debian:bookworm

ENV USER=llamauser

ENV PYTHONUNBUFFERED=1
RUN apt update && apt install python3 python3-venv git git-lfs -y && \
    rm -rf /var/lib/apt/lists/*
    
COPY --from=builder /llama/llama.cpp/main /llama/main
COPY --from=builder /llama/llama.cpp/*.py /llama
COPY --from=builder /llama/llamavenv /llama/llamavenv

ENV PATH=/llama/llamavenv/bin:$PATH
WORKDIR /llama

CMD [ "sleep","infinity" ]
# Aithena

A system to extract knowledge from books in pdf format. It uses the LLaMA embeddings
to generate a vector database of the books in Qdrant. The system is built using
Docker Compose with the following services:

* [Qdrant](https://qdrant.tech/) - Vector database
* [LLaMA.cpp Server](https://llama-cpp-python.readthedocs.io/en/latest/) - Embeddings
* [LLaMA model](https://huggingface.co/openlm-research/open_llama_7b) - Embeddings model: 
you can download the model and then generate the bin file running the llama-base
container `docker exec -it aithena-llama-base-1 python3 convert.py models/7B`.
* A document lister and document indexer that will go through all the pdf files
stored in an Azure Storage account and index them in Qdrant.

## Usage

Configure the volumes folders in the `docker-compose.yml` file.

Run `docker-compose up` to start the system. The first time you run it, it will
fail because you won't have the LLaMA model downloaded. You can download it from
the [Hugging Face model hub](https://huggingface.co/openlm-research/open_llama_7b)
and then generate the bin file running the llama-base container `docker exec -it
aithena-llama-base-1 python3 convert.py models/7B`.


# Reference

* https://python.langchain.com/docs/ecosystem/integrations/llamacpp

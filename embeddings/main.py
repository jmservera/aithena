# https://python.langchain.com/docs/ecosystem/integrations/llamacpp

from langchain.embeddings import LlamaCppEmbeddings
llama = LlamaCppEmbeddings(model_path="/llama/models/7B/ggml-model-f16.bin")
text = "This is a test document."
query_result = llama.embed_query(text)
print(query_result)
import os

EMBEDDINGS_HOST = os.environ.get("EMBEDDINGS_HOST", "localhost")
EMBEDDINGS_PORT = os.environ.get("EMBEDDINGS_PORT", 8000)
QDRANT_HOST = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT = os.environ.get("QDRANT_PORT", 6333)
STORAGE_ACCOUNT_NAME = os.environ.get("STORAGE_ACCOUNT_NAME")
STORAGE_CONTAINER = os.environ.get("STORAGE_CONTAINER")
EMBEDDINGS_TIMEOUT = os.environ.get("EMBEDDINGS_TIMEOUT", 30*60) # 30 minutes
CHAT_HOST = os.environ.get("CHAT_HOST", "localhost")
CHAT_PORT = os.environ.get("CHAT_PORT", 8001)
PORT = os.environ.get("PORT", 8086) # DEBUG PORT, DEFAULT 8085

import os

TITLE="𐃆 Aithena Search API"
VERSION = "0.1.2"
EMBEDDINGS_HOST = os.environ.get("EMBEDDINGS_HOST", "localhost")
EMBEDDINGS_PORT = os.environ.get("EMBEDDINGS_PORT", 8000)
QDRANT_HOST = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT = os.environ.get("QDRANT_PORT", 6333)
QDRANT_COLLECTION = os.environ.get("QDRANT_COLLECTION", "aithena")
STORAGE_ACCOUNT_NAME = os.environ.get("STORAGE_ACCOUNT_NAME")
STORAGE_CONTAINER = os.environ.get("STORAGE_CONTAINER")
EMBEDDINGS_TIMEOUT = int(os.environ.get("EMBEDDINGS_TIMEOUT", 30*60)) # 30 minutes
CHAT_HOST = os.environ.get("CHAT_HOST", "localhost")
CHAT_PORT = os.environ.get("CHAT_PORT", 8001)
CONTEXT_LIMIT = int(os.environ.get("CONTEXT_LIMIT", 8))
PORT = os.environ.get("PORT", 8081) # DEBUG PORT, DEFAULT 8080

# Solr connection (keyword search backend)
SOLR_HOST = os.environ.get("SOLR_HOST", "localhost")
SOLR_PORT = int(os.environ.get("SOLR_PORT", 8983))
SOLR_COLLECTION = os.environ.get("SOLR_COLLECTION", "books")

# Default search mode: keyword | semantic | hybrid
DEFAULT_SEARCH_MODE = os.environ.get("DEFAULT_SEARCH_MODE", "keyword")

# Reciprocal Rank Fusion constant (standard default is 60)
RRF_K = int(os.environ.get("RRF_K", 60))

import os

TITLE = "𐃆 Aithena Search API"
VERSION = "0.2.0"

# Solr connection
SOLR_HOST = os.environ.get("SOLR_HOST", "localhost")
SOLR_PORT = int(os.environ.get("SOLR_PORT", 8983))
SOLR_COLLECTION = os.environ.get("SOLR_COLLECTION", "books")

# Embeddings service (for semantic / hybrid modes)
EMBEDDINGS_HOST = os.environ.get("EMBEDDINGS_HOST", "localhost")
EMBEDDINGS_PORT = int(os.environ.get("EMBEDDINGS_PORT", 8085))
EMBEDDINGS_TIMEOUT = int(os.environ.get("EMBEDDINGS_TIMEOUT", 30 * 60))  # 30 min

# Dense vector field name in Solr (added in Phase 3 schema)
SOLR_VECTOR_FIELD = os.environ.get("SOLR_VECTOR_FIELD", "embedding")
SOLR_VECTOR_DIM = int(os.environ.get("SOLR_VECTOR_DIM", 512))  # distiluse v2

# Default search mode: keyword | semantic | hybrid
DEFAULT_SEARCH_MODE = os.environ.get("DEFAULT_SEARCH_MODE", "keyword")

# Reciprocal Rank Fusion constant (standard default is 60)
RRF_K = int(os.environ.get("RRF_K", 60))

# Service port
PORT = int(os.environ.get("PORT", 8080))

# Base URL for document serving (exposed through nginx / the solr-search container)
DOCUMENT_BASE_URL = os.environ.get("DOCUMENT_BASE_URL", "")

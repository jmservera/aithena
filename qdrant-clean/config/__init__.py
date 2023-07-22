import os

QDRANT_HOST = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT = os.environ.get("QDRANT_PORT", 6333)
QDRANT_COLLECTION = os.environ.get("QDRANT_COLLECTION", "aithena")
PORT = os.environ.get("PORT", 8083) # DEBUG PORT, DEFAULT 8080

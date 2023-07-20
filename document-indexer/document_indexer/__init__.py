import os

RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = os.environ.get("RABBITMQ_PORT", 5672)
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = os.environ.get("REDIS_PORT", 6379)
EMBEDDINGS_HOST = os.environ.get("EMBEDDINGS_HOST", "localhost")
EMBEDDINGS_PORT = os.environ.get("EMBEDDINGS_PORT", 8000)
EMBEDDINGS_TIMEOUT = int(os.environ.get("EMBEDDINGS_TIMEOUT", 30 * 60))  # 30 minutes
EMBEDDINGS_BATCH = int(os.environ.get("EMBEDDINGS_BATCH", -1))
QDRANT_HOST = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT = os.environ.get("QDRANT_PORT", 6333)
QDRANT_COLLECTION = os.environ.get("QDRANT_COLLECTION", "aithena")
QDRANT_VECTOR_DIM = int(os.environ.get("QDRANT_VECTOR_DIM", 768))
STORAGE_ACCOUNT_NAME = os.environ.get("STORAGE_ACCOUNT_NAME")
STORAGE_CONTAINER = os.environ.get("STORAGE_CONTAINER")

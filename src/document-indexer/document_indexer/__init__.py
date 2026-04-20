import os

RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = int(os.environ.get("RABBITMQ_PORT", 5672))
RABBITMQ_USER = os.environ.get("RABBITMQ_USER", "")
RABBITMQ_PASS = os.environ.get("RABBITMQ_PASS", "")
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
QUEUE_NAME = os.environ.get("QUEUE_NAME", "new_documents")
EXCHANGE_NAME = os.environ.get("EXCHANGE_NAME", "documents")
BASE_PATH = os.environ.get("BASE_PATH", "/data/documents/")
SOLR_HOST = os.environ.get("SOLR_HOST", "solr")
SOLR_PORT = int(os.environ.get("SOLR_PORT", 8983))
SOLR_COLLECTION = os.environ.get("SOLR_COLLECTION", "books")
SOLR_AUTH_USER = os.environ.get("SOLR_AUTH_USER") or None
SOLR_AUTH_PASS = os.environ.get("SOLR_AUTH_PASS") or None
SOLR_AUTH: tuple[str, str] | None = (SOLR_AUTH_USER, SOLR_AUTH_PASS) if SOLR_AUTH_USER and SOLR_AUTH_PASS else None
VERSION = os.environ.get("VERSION", "dev")
GIT_COMMIT = os.environ.get("GIT_COMMIT", "unknown")
EMBEDDINGS_HOST = os.environ.get("EMBEDDINGS_HOST", "embeddings-server")
EMBEDDINGS_PORT = int(os.environ.get("EMBEDDINGS_PORT", 8080))
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", 90))
CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", 10))
MAX_PDF_PAGES = int(os.environ.get("MAX_PDF_PAGES", 2000))
EMBEDDING_BATCH_SIZE = int(os.environ.get("EMBEDDING_BATCH_SIZE", 50))
THUMBNAIL_DIR = os.environ.get("THUMBNAIL_DIR", "/data/thumbnails")
INDEXER_CONTROL_PORT = int(os.environ.get("INDEXER_CONTROL_PORT", 8081))

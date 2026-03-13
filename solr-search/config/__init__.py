import os

TITLE = "𐃆 Aithena Search API"
VERSION = "0.1.0"

SOLR_HOST = os.environ.get("SOLR_HOST", "localhost")
SOLR_PORT = os.environ.get("SOLR_PORT", 8983)
SOLR_COLLECTION = os.environ.get("SOLR_COLLECTION", "books")

# Dense vector field name — must match the field added to the Solr schema
# and populated by the Phase 3 indexing pipeline.
SOLR_VECTOR_FIELD = os.environ.get("SOLR_VECTOR_FIELD", "embedding_v")

SOLR_TIMEOUT = int(os.environ.get("SOLR_TIMEOUT", 30))
PORT = int(os.environ.get("PORT", 8080))
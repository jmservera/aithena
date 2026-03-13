import os

TITLE = "𐃆 Aithena Solr Search API"
VERSION = "0.1.0"

SOLR_HOST = os.environ.get("SOLR_HOST", "localhost")
SOLR_PORT = os.environ.get("SOLR_PORT", "8983")
SOLR_COLLECTION = os.environ.get("SOLR_COLLECTION", "books")

# Base URL used to construct client-safe document links.
# Should point to wherever PDFs are served (e.g. an nginx static endpoint).
DOCUMENTS_BASE_URL = os.environ.get("DOCUMENTS_BASE_URL", "/documents")

PORT = int(os.environ.get("PORT", 8080))

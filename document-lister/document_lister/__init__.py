""" Retrieves the environment variables used in the document lister. """

import os

RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = os.environ.get("RABBITMQ_PORT", 5672)
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = os.environ.get("REDIS_PORT", 6379)
QUEUE_NAME = os.environ.get("QUEUE_NAME", "new_documents")
DOCUMENT_WILDCARD = os.environ.get("DOCUMENT_WILDCARD", "*")
BASE_PATH = os.environ.get("BASE_PATH", "/data/documents/")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", 600))

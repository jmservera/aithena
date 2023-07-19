import os

RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = os.environ.get("RABBITMQ_PORT", 5672)
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = os.environ.get("REDIS_PORT", 6379)
STORAGE_ACCOUNT_NAME = os.environ.get("STORAGE_ACCOUNT_NAME")
STORAGE_CONTAINER = os.environ.get("STORAGE_CONTAINER")
DOCUMENT_WILDCARD = os.environ.get("DOCUMENT_WILDCARD", "")
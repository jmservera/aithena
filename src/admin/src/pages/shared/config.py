import os

from dotenv import load_dotenv

load_dotenv()  # take environment variables from .env.

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD") or None
QUEUE_NAME = os.environ.get("QUEUE_NAME", "shortembeddings")

RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "localhost")
RABBITMQ_MGMT_PORT = int(os.environ.get("RABBITMQ_MGMT_PORT", 15672))
RABBITMQ_MGMT_PATH_PREFIX = os.environ.get("RABBITMQ_MGMT_PATH_PREFIX", "").rstrip("/")
RABBITMQ_USER = os.environ.get("RABBITMQ_USER", "guest")
RABBITMQ_PASS = os.environ.get("RABBITMQ_PASS", "guest")

SOLR_SEARCH_URL = os.environ.get("SOLR_SEARCH_URL", "http://solr-search:8080").rstrip("/")

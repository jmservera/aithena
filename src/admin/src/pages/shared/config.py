import os
import sys

from dotenv import load_dotenv

load_dotenv()  # take environment variables from .env.

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", 6379))
QUEUE_NAME = os.environ.get("QUEUE_NAME", "shortembeddings")

RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "localhost")
RABBITMQ_MGMT_PORT = int(os.environ.get("RABBITMQ_MGMT_PORT", 15672))
RABBITMQ_MGMT_PATH_PREFIX = os.environ.get("RABBITMQ_MGMT_PATH_PREFIX", "").rstrip("/")
RABBITMQ_USER = os.environ.get("RABBITMQ_USER", "")
RABBITMQ_PASS = os.environ.get("RABBITMQ_PASS", "")

SOLR_SEARCH_URL = os.environ.get("SOLR_SEARCH_URL", "http://solr-search:8080").rstrip("/")
ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY") or None

# -- Auth --
_src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

AUTH_ENABLED = os.environ.get("AUTH_ENABLED", "true").lower() not in ("false", "0", "no")

from dotenv import load_dotenv
import os

load_dotenv()  # take environment variables from .env.

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = os.environ.get("REDIS_PORT", 6379)
QUEUE_NAME = os.environ.get("QUEUE_NAME", "new_documents")
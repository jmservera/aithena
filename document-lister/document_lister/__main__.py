"""
This module is responsible for listing all documents in the folder '/data' and pushing them to the
queue 'documents'
"""

from datetime import datetime
from pathlib import Path
import logging
import json
import pika
import redis
from retry import retry
from . import (
    QUEUE_NAME,
    REDIS_HOST,
    REDIS_PORT,
    RABBITMQ_HOST,
    RABBITMQ_PORT,
    BASE_PATH,
    DOCUMENT_WILDCARD,
    POLL_INTERVAL,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@retry(redis.exceptions.ConnectionError, delay=5, jitter=(1, 3))
@retry(redis.exceptions.TimeoutError, delay=5, jitter=(1, 3))
def process_path(path: str, redis_client: redis.Redis, channel: pika.channel.Channel):
    """
    Recursively processes the given path and its subdirectories to find and handle documents.

    Args:
        path (str): The path to the directory to be processed.
        redis_client (redis.Redis): The Redis client used for caching.
        channel (pika.channel.Channel): The RabbitMQ channel used for message queueing.
    """

    for blob in Path(path).rglob(DOCUMENT_WILDCARD):
        if blob.is_dir():
            process_path(blob, redis_client, channel)
        else:
            if blob.suffix in [".pdf", ".docx", ".txt"]:
                handle_document(blob, redis_client, channel)
            else:
                logger.info("Skipping non-document file: %s", blob)


def handle_document(path: Path, redis_client: redis.Redis, channel: pika.channel.Channel):
    """
    Handles a document by checking its status and pushing it to the queue if necessary.

    Args:
        path (Path): The path to the document file.
        redis_client (redis.Redis): The Redis client used for caching.
        channel (pika.channel.Channel): The RabbitMQ channel used for message queueing.
    """

    value = redis_client.get(f"/{QUEUE_NAME}/{path}")
    if value is None:
        logger.info("Found new document: %s", path)
        push_file_to_queue(channel, path)
        redis_client.set(
            f"/{QUEUE_NAME}/{path}",
            json.dumps(
                {
                    "path": f"{path}",
                    "last_modified": path.stat().st_mtime,
                    "processed": False,
                    "timestamp": datetime.now().isoformat(),
                }
            ),
        )
    else:
        value = json.loads(value)
        if value.get("last_modified", 0) != path.stat().st_mtime:
            logger.info("Found modified document: %s", path)
            value["last_modified"] = path.stat().st_mtime
            value["timestamp"] = datetime.now().isoformat()
            if value.get("processed", False) is True:
                logger.info("Document marked as unprocessed: %s", path)
                value["processed"] = False
                push_file_to_queue(channel, path)
            redis_client.set(f"/{QUEUE_NAME}/{path}", json.dumps(value))
        else:
            if value.get("processed", False) is False:
                logger.info("Document already in queue: %s", path)
            else:
                logger.info("Document already processed: %s", path)


def push_file_to_queue(channel, file):
    """
    Pushes a file path to the queue.

    Args:
        channel: The channel to use for publishing the blob.
        file: The file path to be pushed to the queue.

    Returns:
        None
    """
    channel.basic_publish(
        exchange="",
        routing_key=QUEUE_NAME,
        body=f"{file}",
        properties=pika.BasicProperties(delivery_mode=2),
    )


@retry(pika.exceptions.AMQPConnectionError, delay=5, jitter=(1, 3))
def produce():
    """
    Produces messages to a RabbitMQ queue by recursively listing all files in a folder and sending
    them to the queue.

    This function connects to a Redis server and a RabbitMQ server, declares a queue, and then
    continuously lists all files in a specified folder.
    The file paths are sent as messages to the RabbitMQ queue.

    Raises:
        pika.exceptions.ConnectionClosedByBroker: If the connection to the RabbitMQ server is closed
        by the broker.
    """
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST, RABBITMQ_PORT))
    channel = connection.channel()
    logger.info("Declaring queue %s", QUEUE_NAME)
    channel.queue_declare(queue=QUEUE_NAME, durable=True, auto_delete=False)

    try:
        # recursively list all files in folder '/data'
        while True:
            process_path(BASE_PATH, redis_client, channel)
            # sleep for 10 minutes
            connection.sleep(POLL_INTERVAL)

    # Don't recover connections closed by server
    except pika.exceptions.ConnectionClosedByBroker:
        pass


if __name__ == "__main__":
    logger.info("Starting document-lister")
    produce()

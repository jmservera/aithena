import json
import pika
import os
import io
import redis
from retry import retry
from datetime import datetime
from pathlib import Path

from .blob_storage import BlobStorage

RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "localhost")
RABBITMQ_PORT = os.environ.get("RABBITMQ_PORT", 5672)
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = os.environ.get("REDIS_PORT", 6379)
STORAGE_ACCOUNT_NAME = os.environ.get("STORAGE_ACCOUNT_NAME")
STORAGE_CONTAINER = os.environ.get("STORAGE_CONTAINER")


@retry(pika.exceptions.AMQPConnectionError, delay=5, jitter=(1, 3))
def produce():
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    connection = pika.BlockingConnection(
        pika.ConnectionParameters(RABBITMQ_HOST, RABBITMQ_PORT)
    )
    channel = connection.channel()
    channel.queue_declare(queue="new_documents", durable=True, auto_delete=False)

    try:
        storage = BlobStorage(STORAGE_ACCOUNT_NAME)
        while True:
            blobs=storage.list_blobs_flat(STORAGE_CONTAINER)
            for blob in blobs:                
                value = redis_client.get(f"/new_document/{blob.name}")
                if value is None:
                    print(f"Found new document: {blob.name}")
                    redis_client.set(
                        f"/new_document/{blob.name}",
                        json.dumps(
                            {
                                "path": f"{blob.name}",
                                "processed": False,
                                "timestamp": datetime.now().isoformat(),
                            }
                        ),
                    )
                    channel.basic_publish(
                        exchange="",
                        routing_key="new_documents",
                        body=f"{blob.name}",
                        properties=pika.BasicProperties(delivery_mode=2),
                    )
                else:
                    print(f"Document already processed: {blob.name}")

            connection.sleep(360000)

    # Don't recover connections closed by server
    except pika.exceptions.ConnectionClosedByBroker:
        pass


if __name__ == "__main__":
    print("Starting document-lister")
    produce()
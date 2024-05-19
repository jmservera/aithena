import json
import pika
import os
import redis
from retry import retry
from datetime import datetime
from pathlib import Path

from . import *

def process_path(path:str, redis_client:redis.Redis, channel:pika.channel.Channel):
    for blob in Path(path).rglob(DOCUMENT_WILDCARD):
        if blob.is_dir():
            process_path(blob, redis_client, channel)
        else:
            if blob.suffix in [".pdf", ".docx", ".txt"]:
                value = redis_client.get(f"/{QUEUE_NAME}/{blob}")
                if value is None:
                    print(f"Found new document: {blob}")
                    redis_client.set(
                        f"/{QUEUE_NAME}/{blob}",
                        json.dumps(
                            {
                                "path": f"{blob}",
                                "processed": False,
                                "timestamp": datetime.now().isoformat(),
                            }
                        ),
                    )
                    channel.basic_publish(
                        exchange="",
                        routing_key=QUEUE_NAME,
                        body=f"{blob}",
                        properties=pika.BasicProperties(delivery_mode=2),
                    )
                else:
                    value = json.loads(value)
                    if(value.get("processed", False) == False):
                        print(f"Document already in queue: {blob}")
                    else:
                        print(f"Document already processed: {blob}")
            else:
                print(f"Skipping non-document file: {blob}")
                

@retry(pika.exceptions.AMQPConnectionError, delay=5, jitter=(1, 3))
def produce():
    redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    connection = pika.BlockingConnection(
        pika.ConnectionParameters(RABBITMQ_HOST, RABBITMQ_PORT)
    )
    channel = connection.channel()
    print(f"***** Declaring queue {QUEUE_NAME} *****")
    channel.queue_declare(queue=QUEUE_NAME, durable=True, auto_delete=False)

    try:
        # recursively list all files in folder '/data'
        while True:
            process_path(BASE_PATH, redis_client, channel)
            # sleep for 10 minutes
            connection.sleep(600)

    # Don't recover connections closed by server
    except pika.exceptions.ConnectionClosedByBroker:
        pass


if __name__ == "__main__":
    print("Starting document-lister")
    produce()

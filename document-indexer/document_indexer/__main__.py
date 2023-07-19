import pika
from pika.adapters.blocking_connection import BlockingChannel
import uuid
import redis
from retry import retry
import pdfplumber
import aiohttp
import asyncio
from qdrant_client import models, QdrantClient
import re

from .blob_storage import BlobStorage

from . import *


async def heartbeat(channel: BlockingChannel):
    """Send heartbeat to RabbitMQ every 10 seconds
    channel: BlockingChannel
    """
    count = 0
    while True:
        count += 1
        print(f"Waiting for embeddings {count}")
        channel.connection.process_data_events()
        await asyncio.sleep(10)


async def get_embeddings_async(text, channel):
    """Get embeddings for a text from embeddings service"""
    client_timeout = aiohttp.ClientTimeout(total=EMBEDDINGS_TIMEOUT)  # 30 minutes
    async with aiohttp.ClientSession(timeout=client_timeout) as session:
        hearbeat_task = asyncio.create_task(heartbeat(channel))
        try:
            async with session.post(
                f"http://{EMBEDDINGS_HOST}:{EMBEDDINGS_PORT}/v1/embeddings",
                json={"input": text},
            ) as resp:
                return await resp.json()
        finally:
            hearbeat_task.cancel()


def get_embeddings(text, channel):
    return loop.run_until_complete(get_embeddings_async(text, channel))

def cleanup(text:str):
    if(text is None):
        return ""
    else:
        # remove newlines, tabs and carriage returns
        text = re.sub(r'[\n\t\r]', ' ', text)
        # remove spaces before phrase marks, commas, colons, semicolons, question marks, exclamation marks, and dashes
        text = re.sub(r'\s([,:;?!-\)\]])', r'\1', text)
        # remove multiple spaces after opening brackets
        text = re.sub(r'(\(|\[])\s+', r'\1', text)
        # remove multiple sequential marks
        text = re.sub(r'([\s.,:;?!-_\(\[\)\])])(\1+)', r'\1', text)
        return text.strip()

def callback(
    channel: BlockingChannel,
    method: pika.spec.Basic.Deliver,
    properties: pika.spec.BasicProperties,
    body: bytes,
):
    """Callback function for RabbitMQ consumer"""
    msg_count = channel.get_waiting_message_count()

    count = get_queue(channel)
    print(f"Received new document: {body}. Remaining messages: {count}")

    filename = body.decode("utf-8")
    if filename.endswith(".pdf"):
        stream = storage_client.download_blob_to_stream(STORAGE_CONTAINER, filename)
        fulltext = ""
        with pdfplumber.open(stream) as pdf:
            for page in pdf.pages:
                print(
                    f"Processing page {page.page_number}/{len(pdf.pages)} of {filename}"
                )
                fulltext = cleanup(page.extract_text())
                if fulltext == "":
                    print(f"Skipping empty page {filename} {page.page_number}")
                else:
                    chunks = []
                    print(f"Splitting {filename} page {page.page_number} into chunks. Length: {len(fulltext)}")
                    while len(fulltext) > 500:
                        last_period_index = fulltext[:500].rfind(".")
                        if last_period_index == -1:
                            last_period_index = 500
                        chunks.append(fulltext[:last_period_index])
                        fulltext = fulltext[last_period_index + 1 :].strip()
                    if len(fulltext)<100:
                        chunks[-1] = chunks[-1] + " " + fulltext
                    else:
                        chunks.append(fulltext)
                    points = []
                    for chunk in chunks:
                        embedding = get_embeddings(chunk, channel)
                        points.append(
                            models.PointStruct(
                                id=str(uuid.uuid4()),  # TODO: generate id
                                vector=embedding["data"][0]["embedding"],
                                payload={
                                    "path": filename,
                                    "page": page.page_number,
                                    "text": chunk,
                                    "usage": embedding["usage"]
                                },
                            )
                        )

                    operation_info = qdrant.upsert(
                        collection_name="documents", points=points, wait=True
                    )
                    print(f"Upserted {operation_info} for {filename}")
    else:
        print(f"Unsupported file type: {filename}")

    channel.basic_ack(delivery_tag=method.delivery_tag)


queue = None


def get_queue(channel: BlockingChannel):
    """Get queue from channel"""
    global queue
    channel.basic_qos(prefetch_count=1)
    if queue is None:
        queue = channel.queue_declare(
            queue="new_documents", durable=True, auto_delete=False
        )
    else:
        queue = channel.queue_declare(
            queue="new_documents", durable=True, auto_delete=False, passive=True
        )

    return queue.method.message_count


@retry(pika.exceptions.AMQPConnectionError, delay=5, jitter=(1, 3))
def consume():
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(RABBITMQ_HOST, RABBITMQ_PORT)
    )
    channel = connection.channel()
    get_queue(channel)

    channel.basic_consume(queue="new_documents", on_message_callback=callback)

    try:
        channel.start_consuming()
    # Don't recover connections closed by server
    except pika.exceptions.ConnectionClosedByBroker:
        pass


# https://stackoverflow.com/questions/73361664/asyncio-get-event-loop-deprecationwarning-there-is-no-current-event-loop
loop = asyncio.new_event_loop()
storage_client = BlobStorage(STORAGE_ACCOUNT_NAME)
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
print(f"Connection to Redis established {REDIS_HOST}:{REDIS_PORT}")

qdrant = QdrantClient(url=f"http://{QDRANT_HOST}:{QDRANT_PORT}")
if "documents" not in [n.name for n in qdrant.get_collections().collections]:
    qdrant.create_collection(
        collection_name="documents",
        vectors_config=models.VectorParams(
            size=4096,  # todo: get from service... encoder.get_sentence_embedding_dimension(), # Vector size is defined by used model
            distance=models.Distance.COSINE,
        ),
    )


if __name__ == "__main__":
    consume()

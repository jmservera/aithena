import pika
from pika.adapters.blocking_connection import BlockingChannel
import os
import redis
from retry import retry
import pdfplumber
import aiohttp
import asyncio
from qdrant_client import models, QdrantClient

from .blob_storage import BlobStorage

RABBITMQ_HOST = os.environ.get('RABBITMQ_HOST', 'localhost')
RABBITMQ_PORT = os.environ.get('RABBITMQ_PORT', 5672)
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
REDIS_PORT = os.environ.get('REDIS_PORT', 6379)
EMBEDDINGS_HOST= os.environ.get('EMBEDDINGS_HOST', 'localhost')
EMBEDDINGS_PORT= os.environ.get('EMBEDDINGS_PORT', 5000)
QDRANT_HOST= os.environ.get('QDRANT_HOST', 'localhost')
QDRANT_PORT= os.environ.get('QDRANT_PORT', 6333)
STORAGE_ACCOUNT_NAME = os.environ.get('STORAGE_ACCOUNT_NAME')
STORAGE_CONTAINER = os.environ.get('STORAGE_CONTAINER')

async def heartbeat(channel: BlockingChannel):
    count=0
    while True:
        count+=1
        print(f"Waiting for embeddings {count}")
        channel.connection.process_data_events()
        await asyncio.sleep(10)

async def get_embeddings_async(text,channel):
    async with aiohttp.ClientSession() as session:
        hearbeat_task=asyncio.create_task(heartbeat(channel))
        async with session.get(f'http://{EMBEDDINGS_HOST}:{EMBEDDINGS_PORT}/?text={text}') as resp:
            result = await resp.json()
            hearbeat_task.cancel()
            return result['result']
        
def get_embeddings(text,channel):
    return loop.run_until_complete(get_embeddings_async(text,channel))

def callback(channel: BlockingChannel, method, properties, body):
    print(f"Received new document: {body}")

    qdrant = QdrantClient(url=f"http://{QDRANT_HOST}:{QDRANT_PORT}")
    qdrant.recreate_collection(
        collection_name="documents",
        vectors_config=models.VectorParams(
            size=4096,# todo: get from service... encoder.get_sentence_embedding_dimension(), # Vector size is defined by used model
            distance=models.Distance.COSINE
        )
    )


    filename = body.decode('utf-8')
    if(filename.endswith('.pdf')):
        stream = storage_client.download_blob_to_stream(STORAGE_CONTAINER, filename)
        with pdfplumber.open(stream) as pdf:
            for page in pdf.pages:
                print(f"Processing page {page.page_number}/{len(pdf.pages)} of {filename}")          
                text = page.extract_text()
                text = text.split('.')
                lineNumber = 0
                for line in text:               
                    lineNumber += 1

                    embedding = get_embeddings(line.strip()+".",channel)

                    qdrant.upsert(collection_name="documents",
                                points=[models.PointStruct(
                                    id=page.page_number*10000+lineNumber, #TODO: generate id
                                    vector=embedding,
                                    payload={"path": filename, "page": page.page_number, "line": lineNumber, "text": line}
                                )]
                    )
                    channel.connection.process_data_events()
    else:
        print(f"Unsupported file type: {filename}")
    
    channel.basic_ack(delivery_tag=method.delivery_tag)

@retry(pika.exceptions.AMQPConnectionError, delay=5, jitter=(1, 3))
def consume():
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST, RABBITMQ_PORT))
    channel = connection.channel()
    channel.queue_declare(queue='new_documents', durable=True, auto_delete=False)
    
    channel.basic_consume(queue='new_documents', on_message_callback=callback)

    try:
        channel.start_consuming()
    # Don't recover connections closed by server
    except pika.exceptions.ConnectionClosedByBroker:
        pass

loop = asyncio.get_event_loop()
storage_client = BlobStorage(STORAGE_ACCOUNT_NAME)

if __name__ == '__main__':
    consume()
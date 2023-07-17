import pika
import os
from retry import retry

# Get the HOST from the environment variable RABBITMQ_HOST or use localhost as default
HOST = os.environ.get('RABBITMQ_HOST', 'localhost')

def callback(channel, method, properties, body):
    print(f"Received new document: {body}")
    channel.basic_ack(delivery_tag=method.delivery_tag)

@retry(pika.exceptions.AMQPConnectionError, delay=5, jitter=(1, 3))
def consume():
    connection = pika.BlockingConnection(pika.ConnectionParameters(HOST))
    channel = connection.channel()
    channel.queue_declare(queue='new_documents')
    
    channel.basic_consume(queue='new_documents', on_message_callback=callback)

    try:
        channel.start_consuming()
    # Don't recover connections closed by server
    except pika.exceptions.ConnectionClosedByBroker:
        pass


consume()
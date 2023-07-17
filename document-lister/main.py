import pika
import os
from retry import retry
from datetime import datetime

# Get the HOST from the environment variable RABBITMQ_HOST or use localhost as default
HOST = os.environ.get('RABBITMQ_HOST', 'localhost')


@retry(pika.exceptions.AMQPConnectionError, delay=5, jitter=(1, 3))
def produce():
    connection = pika.BlockingConnection(pika.ConnectionParameters(HOST))
    channel = connection.channel()
    channel.queue_declare(queue='new_documents')

    try:
        while True:
            print("Sending 'Hello World!'")
            channel.basic_publish(exchange='', routing_key='new_documents', body=f'Hello World! {datetime.now()}')
            print("Sent 'Hello World!'")
            # Wait 5 seconds before sending the next message
            connection.sleep(5)

    # Don't recover connections closed by server
    except pika.exceptions.ConnectionClosedByBroker:
        pass


produce()
from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable
import json
import time

print("Starting Notification Service...")

max_retries = 10
retry_count = 0
consumer = None

while retry_count < max_retries:
    try:
        consumer = KafkaConsumer(
            'alerts',
            bootstrap_servers=['kafka:9092'],
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            group_id='notification-dispatchers'
        )
        print("Connected to Kafka!")
        break
    except NoBrokersAvailable:
        retry_count += 1
        print(f"Retry {retry_count}/{max_retries}")
        time.sleep(5)

if consumer is None:
    print("Failed to connect to Kafka")
    exit(1)

print("Listening for alerts")
print("=" * 70)

for message in consumer:
    alert = message.value
    
    print("\n" + "=" * 70)
    print("SENDING NOTIFICATION")
    print("=" * 70)
    print(f"To: User (user@example.com)")
    print(f"Subject: Stock Alert - {alert['ticker']}")
    print(f"Message: {alert['message']}")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(alert['timestamp']))}")
    print("=" * 70 + "\n")
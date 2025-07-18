from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import NoBrokersAvailable
import redis
import json
import time

print("Starting alert evaluator consumer...")

# Connect to Redis
print("Connecting to redis...")
try:
    redis_client = redis.Redis(host='redis', port=6379, decode_responses=True)
    redis_client.ping()
    print("Connected to redis")
except Exception as e:
    print(f"Redis connection failed: {e}")
    exit(1)

# Connect to Kafka Consumer
print("Connecting to kafka consumer...")
max_retries = 10
retry_count = 0
consumer = None

while retry_count < max_retries:
    try:
        consumer = KafkaConsumer(
            'stock-prices',
            bootstrap_servers=['kafka:9092'],
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            group_id='alert-evaluators'
        )
        print("Connected to kafka consumer!")
        break
    except NoBrokersAvailable:
        retry_count += 1
        print(f"Retrying {retry_count}/{max_retries}")
        time.sleep(5)

if consumer is None:
    print("Failed to connect to kafka consumer")
    exit(1)

# Connect to Kafka Producer
print("Connecting to kafka producer...")
producer = None
retry_count = 0

while retry_count < max_retries:
    try:
        producer = KafkaProducer(
            bootstrap_servers=['kafka:9092'],
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        print("Connected to kafka producer!")
        break
    except:
        retry_count += 1
        print(f"Retrying {retry_count}/{max_retries}")
        time.sleep(5)

if producer is None:
    print("Failed to connect to kafka producer")
    exit(1)

print("Monitoring stock prices for alerts...")
print("=" * 70)

# Tracking last alert time per alert_id for cooldown
last_alert_time = {}
ALERT_COOLDOWN = 10

def check_alerts_for_ticker(ticker, price):
    """Check all alerts for a specific ticker and return triggered ones"""
    triggered_alerts = []
    
    # Get all alert IDs for this ticker
    alert_ids = redis_client.smembers(f"ticker_alerts:{ticker}")
    
    if not alert_ids:
        return triggered_alerts
    
    current_time = time.time()
    
    for alert_id in alert_ids:
        # Check cooldown for this specific alert
        if alert_id in last_alert_time:
            time_since_last = current_time - last_alert_time[alert_id]
            if time_since_last < ALERT_COOLDOWN:
                continue
        
        # Get alert configuration
        alert_data = redis_client.hgetall(f"alert:{alert_id}")
        
        if not alert_data:
            # Alert was deleted, clean up
            redis_client.srem(f"ticker_alerts:{ticker}", alert_id)
            continue
        
        threshold = float(alert_data['threshold'])
        alert_type = alert_data['type']
        user_id = alert_data['user_id']
        
        # Check if triggered
        triggered = False
        if alert_type == 'above' and price > threshold:
            triggered = True
        elif alert_type == 'below' and price < threshold:
            triggered = True
        
        if triggered:
            last_alert_time[alert_id] = current_time
            
            alert_message = {
                "alert_id": alert_id,
                "user_id": user_id,
                "ticker": ticker,
                "price": price,
                "threshold": threshold,
                "type": alert_type,
                "timestamp": current_time,
                "message": f"{ticker} is {alert_type} ${threshold:.2f} (Current: ${price:.2f})"
            }
            
            triggered_alerts.append(alert_message)
            
            # Delete the alert after triggering
            redis_client.srem(f"user_alerts:{user_id}", alert_id)
            redis_client.srem(f"ticker_alerts:{ticker}", alert_id)
            redis_client.delete(f"alert:{alert_id}")
            
            print(f"[ALERT TRIGGERED] User {user_id[:8]}... | {ticker} {alert_type} ${threshold:.2f} | Current: ${price:.2f}")
            print(f"[CLEANUP] Alert {alert_id[:8]}... deleted")
    
    return triggered_alerts

# Process messages
for message in consumer:
    try:
        data = message.value
        ticker = data['ticker']
        price = data['price']
        
        # Check all alerts for this ticker
        triggered_alerts = check_alerts_for_ticker(ticker, price)
        
        # Send each triggered alert to Kafka
        for alert in triggered_alerts:
            producer.send('alerts', value=alert)
            producer.flush()
            print("=" * 70)
            
    except Exception as e:
        print(f"Error processing message: {e}")
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import NoBrokersAvailable
import redis
import json
import time

print("ctarting alert evaluator consumer...")

# Connect to Redis
print("connecting to redis...")
try:
    redis_client = redis.Redis(host='redis', port=6379, decode_responses=True)
    redis_client.ping()
    print("connected to redis")
except Exception as e:
    print(f"redis connection failed: {e}")
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
        print("connected to kafka consumer!")
        break
    except NoBrokersAvailable:
        retry_count += 1
        print(f"Retrying {retry_count}/{max_retries}")
        time.sleep(5)

if consumer is None:
    print("Failed to connect to kafka consumer")
    exit(1)

# Connect to Kafka Producer
print("connecting to kafka producer...")
producer = None
retry_count = 0

while retry_count < max_retries:
    try:
        producer = KafkaProducer(
            bootstrap_servers=['kafka:9092'],
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        print("connected to kafka producer :-)) ")
        break
    except:
        retry_count += 1
        print(f"retring {retry_count}/{max_retries}")
        time.sleep(5)

if producer is None:
    print("failed to connect tp kafka")
    exit(1)

#above connection done now just checking the messages
print(" monitoring stock prices for alerts...")
print("=" * 70)

# trakcing last alert time to cooldown
last_alert_time = {}
# ALERT_COOLDOWN = 0

def check_alert(ticker, price):
    """Check if price triggers an alert"""
    alert_key = f"alerts:{ticker}"
    
    # alert there ?

    if not redis_client.exists(alert_key):
        return None
    
    # cooldonw checking 
    current_time = time.time()
    if ticker in last_alert_time:
        time_since_last = current_time - last_alert_time[ticker]
        if time_since_last < ALERT_COOLDOWN:
            return None  
    
    # getting the alert config
    alert_config = redis_client.hgetall(alert_key)
    threshold = float(alert_config['threshold'])
    alert_type = alert_config['type']
    
    # Check if triggered
    triggered = False
    if alert_type == 'above' and price > threshold:
        triggered = True
    elif alert_type == 'below' and price < threshold:
        triggered = True
    
    if triggered:
        last_alert_time[ticker] = current_time
        return {
            "ticker": ticker,
            "price": price,
            "threshold": threshold,
            "type": alert_type,
            "timestamp": time.time(),
            "message": f"{ticker} is {alert_type} ${threshold:.2f} (Current: ${price:.2f})"
        }
    
    return None

# Process messages
for message in consumer:
    try:
        data = message.value
        ticker = data['ticker']
        price = data['price']
        
        # Check if triggered
        alert = check_alert(ticker, price)
        
        if alert:
            # Send alert
            producer.send('alerts', value=alert)
            producer.flush()
            
            print(f"ALERT: {alert['message']}")
            print("=" * 70)
            
    except Exception as e:
        print(f"Error: {e}")

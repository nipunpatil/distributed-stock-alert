import os, time, json, psycopg2, redis
from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable
KAFKA_BROKER_URL = os.environ.get("KAFKA_BROKER_URL")
POSTGRES_HOST = os.environ.get("POSTGRES_HOST")
POSTGRES_DB = os.environ.get("POSTGRES_DB")
POSTGRES_USER = os.environ.get("POSTGRES_USER")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD")
REDIS_HOST = os.environ.get("REDIS_HOST")
REDIS_NOTIFICATION_CHANNEL = "alert-notifications"
def connect_to_postgres():
    while True:
        try:
            conn = psycopg2.connect(host=POSTGRES_HOST, database=POSTGRES_DB, user=POSTGRES_USER, password=POSTGRES_PASSWORD)
            print("[Processor] Successfully connected to PostgreSQL.")
            return conn
        except psycopg2.OperationalError as e:
            print(f"[Processor] Could not connect to PostgreSQL, retrying... Error: {e}")
            time.sleep(5)
def create_table(conn):
    with conn.cursor() as cur:
        cur.execute("CREATE TABLE IF NOT EXISTS stock_prices (id SERIAL PRIMARY KEY, ticker VARCHAR(20) NOT NULL, price NUMERIC(20, 4) NOT NULL, timestamp TIMESTAMPTZ NOT NULL);")
        conn.commit()
def check_alerts_and_notify(redis_client, ticker, price):
    alert_key = f"alert:{ticker}"
    alert_data = redis_client.hgetall(alert_key)
    if not alert_data: return
    try:
        threshold = float(alert_data['threshold'])
        direction = alert_data['direction']
        triggered = (direction == 'above' and price > threshold) or (direction == 'below' and price < threshold)
        if triggered:
            print(f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n!!! ALERT TRIGGERED: {ticker} @ ${price} is {direction} ${threshold} !!!\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            notification_message = json.dumps({"ticker": ticker, "price": price, "direction": direction, "threshold": threshold})
            redis_client.publish(REDIS_NOTIFICATION_CHANNEL, notification_message)
            redis_client.delete(alert_key)
            print(f"[Processor] Alert for {ticker} triggered and removed.")
    except Exception as e:
        print(f"[Processor] Could not process alert for {ticker}. Data: {alert_data}. Error: {e}")
def main():
    pg_conn = connect_to_postgres()
    create_table(pg_conn)
    redis_client = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)
    while True:
        try:
            consumer = KafkaConsumer("stock-prices", bootstrap_servers=KAFKA_BROKER_URL, value_deserializer=lambda v: json.loads(v.decode('utf-8')), auto_offset_reset='earliest')
            print("[Processor] Kafka consumer connected.")
            for message in consumer:
                data = message.value
                with pg_conn.cursor() as cur:
                    cur.execute("INSERT INTO stock_prices (ticker, price, timestamp) VALUES (%s, %s, to_timestamp(%s))", (data['ticker'], data['price'], data['timestamp']))
                    pg_conn.commit()
                check_alerts_and_notify(redis_client, data['ticker'], data['price'])
        except Exception as e:
            print(f"[Processor] An unexpected error occurred: {e}. Retrying...")
            time.sleep(5)
if __name__ == "__main__":
    main()

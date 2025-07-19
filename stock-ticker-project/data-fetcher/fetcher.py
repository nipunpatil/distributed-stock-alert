import os, time, json, asyncio, yfinance as yf
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError

KAFKA_BROKER_URL = os.environ.get("KAFKA_BROKER_URL", "localhost:9092")
TICKERS = ["BTC-USD", "ETH-USD", "DOGE-USD"]
FETCH_INTERVAL_SECONDS = 2

def get_crypto_price_blocking(ticker):
    try:
        stock = yf.Ticker(ticker)
        price = stock.info.get('regularMarketPrice')
        if price is None: price = stock.history(period="1d")['Close'].iloc[-1]
        return round(price, 4)
    except Exception as e:
        print(f"[Fetcher] Error fetching for {ticker}: {e}")
        return None

async def fetch_and_produce(ticker, producer):
    price = await asyncio.to_thread(get_crypto_price_blocking, ticker)
    if price is not None:
        message = {"ticker": ticker, "price": price, "timestamp": time.time()}
        try:
            await producer.send_and_wait("stock-prices", value=message)
        except KafkaConnectionError as e:
            print(f"[Fetcher] Send failed for {ticker}: {e}")

async def main():
    producer = None
    while producer is None:
        try:
            producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BROKER_URL, value_serializer=lambda v: json.dumps(v).encode('utf-8'))
            await producer.start()
            print("[Fetcher] Kafka Producer started.")
        except KafkaConnectionError:
            print("[Fetcher] Kafka connection failed. Retrying...")
            await asyncio.sleep(5)
    try:
        while True:
            tasks = [fetch_and_produce(ticker, producer) for ticker in TICKERS]
            await asyncio.gather(*tasks)
            print(f"--- Fetched all tickers concurrently. Waiting {FETCH_INTERVAL_SECONDS}s ---")
            await asyncio.sleep(FETCH_INTERVAL_SECONDS)
    finally:
        await producer.stop()

if __name__ == "__main__":
    asyncio.run(main())

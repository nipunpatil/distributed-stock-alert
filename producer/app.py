from kafka import KafkaProducer
from kafka.errors import NoBrokersAvailable
import json
import time
import yfinance as yf

print("starting producer...")

max_retries = 10
retry_count = 0
producer = None

while retry_count < max_retries:
    try:
        producer = KafkaProducer(
            bootstrap_servers=['kafka:9092'],
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        print("connected to kafka!")
        break
    except NoBrokersAvailable:
        retry_count += 1
        print(f"retry {retry_count}/{max_retries}")
        time.sleep(5)

if producer is None:
    print("failed to connect to kafka")
    exit(1)

tickers = [
    'AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA',
    'GC=F', 'SI=F', 'CL=F', 'NG=F', 'HG=F',
    'BTC-USD', 'ETH-USD', 'BNB-USD', 'SOL-USD', 'XRP-USD'
]

display_names = {
    'GC=F': 'gold',
    'SI=F': 'silver',
    'CL=F': 'crude oil',
    'NG=F': 'natural gas',
    'HG=F': 'copper',
    'BTC-USD': 'bitcoin',
    'ETH-USD': 'ethereum',
    'BNB-USD': 'binance coin',
    'SOL-USD': 'solana',
    'XRP-USD': 'ripple'
}

print(f"monitoring {len(tickers)} assets")
print("-" * 70)

while True:
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            current_price = (
                info.get('currentPrice') or 
                info.get('regularMarketPrice') or 
                info.get('previousClose', 0)
            )
            
            if current_price > 0:
                display_name = display_names.get(ticker, ticker)
                company_name = info.get('shortName', display_name)
                
                message = {
                    "ticker": ticker,
                    "price": float(current_price),
                    "timestamp": time.time(),
                    "company": company_name,
                    "display_name": display_name
                }
                
                producer.send('stock-prices', value=message)
                producer.flush()
                
                print(f"{ticker:10} | ${current_price:12,.2f} | {display_name}")
            
        except Exception as e:
            print(f"error fetching {ticker}: {str(e)[:60]}")
    
    print("-" * 70)
    time.sleep(1)

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from kafka import KafkaConsumer
import redis
import json
import asyncio

app = FastAPI(title="Stock Alert Dashboard")

# Redis connection
redis_client = redis.Redis(host='redis', port=6379, decode_responses=True)

@app.get("/", response_class=HTMLResponse)
async def home():
    with open("index.html", "r") as f:
        return HTMLResponse(content=f.read())

@app.get("/api/stream-prices")
async def stream_prices():
    """SSE stream for live stock prices"""
    async def event_generator():
        consumer = KafkaConsumer(
            'stock-prices',
            bootstrap_servers=['kafka:9092'],
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='latest',
            group_id=f'webapp-prices-{id(event_generator)}'
        )
        
        try:
            while True:
                msg = consumer.poll(timeout_ms=100)
                for topic_partition, messages in msg.items():
                    for message in messages:
                        yield f"data: {json.dumps(message.value)}\n\n"
                await asyncio.sleep(0.1)
        finally:
            consumer.close()
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )

@app.get("/api/stream-alerts")
async def stream_alerts():
    """SSE stream for triggered alerts"""
    async def event_generator():
        consumer = KafkaConsumer(
            'alerts',
            bootstrap_servers=['kafka:9092'],
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            auto_offset_reset='latest',
            group_id=f'webapp-alerts-{id(event_generator)}'
        )
        
        try:
            while True:
                msg = consumer.poll(timeout_ms=100)
                for topic_partition, messages in msg.items():
                    for message in messages:
                        yield f"data: {json.dumps(message.value)}\n\n"
                await asyncio.sleep(0.1)
        finally:
            consumer.close()
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream"
    )

@app.post("/api/set-alert")
async def set_alert(alert: dict):
    """Set alert threshold"""
    ticker = alert['ticker']
    threshold = float(alert['threshold'])
    alert_type = alert['type']
    
    redis_client.hset(
        f"alerts:{ticker}",
        mapping={"threshold": str(threshold), "type": alert_type}
    )
    
    return {"message": f"Alert set for {ticker}"}

@app.get("/health")
def health():
    return {"status": "healthy"}

import os, json, asyncio
from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict

import redis.asyncio as redis
from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaConnectionError

from sqlalchemy.orm import Session
from sqlalchemy import create_engine, Column, Integer, String, Numeric, DateTime, desc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# --- Config ---
KAFKA_BROKER_URL = os.environ.get("KAFKA_BROKER_URL")
REDIS_HOST = os.environ.get("REDIS_HOST")
DATABASE_URL = f"postgresql://{os.environ.get('POSTGRES_USER')}:{os.environ.get('POSTGRES_PASSWORD')}@{os.environ.get('POSTGRES_HOST')}/{os.environ.get('POSTGRES_DB')}"
KAFKA_TOPIC = "stock-prices"
REDIS_NOTIFICATION_CHANNEL = "alert-notifications"

# --- Database Setup (NEW) ---
Base = declarative_base()
class StockPrice(Base):
    __tablename__ = "stock_prices"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True)
    price = Column(Numeric(20, 4))
    timestamp = Column(DateTime, index=True)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- FastAPI App ---
app = FastAPI(title="Stock Alert API")
app.mount("/static", StaticFiles(directory="static"), name="static")

class ConnectionManager:
    def __init__(self): self.active_connections: List[WebSocket] = []
    async def connect(self, ws: WebSocket): await ws.accept(); self.active_connections.append(ws)
    def disconnect(self, ws: WebSocket): self.active_connections.remove(ws)
    async def broadcast(self, msg: str): 
        for conn in self.active_connections: await conn.send_text(msg)
manager = ConnectionManager()

# --- Background Tasks ---
async def consume_prices_and_broadcast():
    
    while True:
        try:
            consumer = AIOKafkaConsumer(KAFKA_TOPIC, bootstrap_servers=KAFKA_BROKER_URL, value_deserializer=lambda v: json.loads(v.decode('utf-8')), auto_offset_reset='latest')
            await consumer.start()
            print("[API] Price consumer started.")
            async for msg in consumer:
                await manager.broadcast(json.dumps({"type": "price_update", "data": msg.value}))
        except Exception as e:
            print(f"[API] Price consumer error: {e}. Retrying...")
            await asyncio.sleep(5)

async def listen_for_alerts_and_broadcast():
    
    while True:
        try:
            pubsub = app.state.redis.pubsub()
            await pubsub.subscribe(REDIS_NOTIFICATION_CHANNEL)
            print("[API] Alert listener started.")
            async for message in pubsub.listen():
                if message["type"] == "message":
                    alert_data = json.loads(message["data"])
                    await manager.broadcast(json.dumps({"type": "alert_triggered", "data": alert_data}))
        except Exception as e:
            print(f"[API] Redis Pub/Sub error: {e}. Retrying...")
            await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    app.state.redis = redis.from_url(f"redis://{REDIS_HOST}", decode_responses=True)
    asyncio.create_task(consume_prices_and_broadcast())
    asyncio.create_task(listen_for_alerts_and_broadcast())

# --- API Endpoints ---
@app.get("/", response_class=HTMLResponse)
async def get_root():
    with open("static/index.html") as f: return HTMLResponse(content=f.read())

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True: await ws.receive_text()
    except WebSocketDisconnect: manager.disconnect(ws)

class Alert(BaseModel):
    ticker: str
    threshold: float
    direction: str = 'above'

@app.post("/alerts")
async def set_alert(alert: Alert):
    key = f"alert:{alert.ticker.upper()}"
    await app.state.redis.hset(key, mapping={"threshold": alert.threshold, "direction": alert.direction})
    return {"status": "success"}

@app.get("/alerts", response_model=List[Dict])
async def get_alerts():
    alerts = []
    for key in await app.state.redis.keys("alert:*"):
        data = await app.state.redis.hgetall(key)
        data['ticker'] = key.split(":")[1]
        alerts.append(data)
    return alerts

# NEW: Endpoint for historical chart data
@app.get("/history/{ticker}")
def get_history(ticker: str, db: Session = Depends(get_db)):
    # Query the last 100 data points for the given ticker, ordered by most recent first
    results = db.query(StockPrice.timestamp, StockPrice.price)\
                .filter(StockPrice.ticker == ticker.upper())\
                .order_by(desc(StockPrice.timestamp))\
                .limit(100)\
                .all()
    
    # Reverse the results to have them in chronological order for the chart
    results.reverse()

    # Chart.js
    timestamps = [r.timestamp.strftime("%H:%M:%S") for r in results]
    prices = [float(r.price) for r in results]
    
    return {"timestamps": timestamps, "prices": prices}

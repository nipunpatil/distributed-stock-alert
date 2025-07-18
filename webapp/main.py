import asyncio
import json
import threading
import time
import uuid
from typing import Set

from fastapi import FastAPI, Request, Response, Cookie
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
import redis
from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable

app = FastAPI(title="Stock Alert Dashboard (User-Specific)")

redis_client = redis.Redis(host="redis", port=6379, decode_responses=True)

# Broadcaster
class Broadcaster:
    def __init__(self):
        self._clients: Set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()

    async def register(self, max_queue_size: int = 100) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        async with self._lock:
            self._clients.add(q)
        return q

    async def unregister(self, q: asyncio.Queue):
        async with self._lock:
            self._clients.discard(q)

    async def broadcast(self, message):
        """send to all clients; non-blocking."""
        async with self._lock:
            clients = list(self._clients)
        for q in clients:
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                pass

price_broadcaster = Broadcaster()
alert_broadcaster = Broadcaster()


def kafka_consumer_runner(topic: str, loop: asyncio.AbstractEventLoop, broadcaster: Broadcaster, stop_event: threading.Event):
    """run a blocking Kafka consumer in a thread and forward messages to the asyncio loop."""
    max_retries = 10
    retry = 0
    consumer = None

    while not stop_event.is_set() and retry < max_retries:
        try:
            consumer = KafkaConsumer(
                topic,
                bootstrap_servers=["kafka:9092"],
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                auto_offset_reset="latest",
                group_id=f"shared-{topic}-consumer"
            )
            print(f"[kafka_consumer_runner] Connected to Kafka topic: {topic}")
            break
        except NoBrokersAvailable:
            retry += 1
            print(f"[kafka_consumer_runner] No brokers yet for {topic}. Retry {retry}/{max_retries}")
            time.sleep(5)

    if consumer is None:
        print(f"[kafka_consumer_runner] Failed to connect to Kafka for topic {topic}")
        return

    try:
        for message in consumer:
            if stop_event.is_set():
                break
            value = message.value
            asyncio.run_coroutine_threadsafe(broadcaster.broadcast(value), loop)
    except Exception as e:
        print(f"[kafka_consumer_runner] Error for {topic}: {e}")
    finally:
        try:
            consumer.close()
        except Exception:
            pass
        print(f"[kafka_consumer_runner] Exiting consumer thread for {topic}")

_consumer_threads = []
_stop_events = []

@app.on_event("startup")
async def startup_event():
    loop = asyncio.get_event_loop()

    for topic, broadcaster in (("stock-prices", price_broadcaster), ("alerts", alert_broadcaster)):
        stop_event = threading.Event()
        t = threading.Thread(
            target=kafka_consumer_runner,
            args=(topic, loop, broadcaster, stop_event),
            daemon=True
        )
        t.start()
        _consumer_threads.append(t)
        _stop_events.append(stop_event)
        print(f"[startup] started consumer thread for {topic}")

@app.on_event("shutdown")
async def shutdown_event():
    for ev in _stop_events:
        ev.set()
    for t in _consumer_threads:
        t.join(timeout=5)
    print("[shutdown] consumer threads stopped")

async def sse_event_generator(client_queue: asyncio.Queue, heartbeat_interval: float = 15.0):
    """yield SSE messages and periodic heartbeats."""
    last_heartbeat = time.time()
    try:
        while True:
            try:
                timeout = max(0, last_heartbeat + heartbeat_interval - time.time())
                message = await asyncio.wait_for(client_queue.get(), timeout=timeout)
                yield f"data: {json.dumps(message)}\n\n"
            except asyncio.TimeoutError:
                last_heartbeat = time.time()
                yield ": heartbeat\n\n"
    finally:
        return

def get_or_create_user_id(user_id: str = None) -> tuple[str, bool]:
    """Get existing user_id or create new one. Returns (user_id, is_new)"""
    if user_id:
        return user_id, False
    new_user_id = str(uuid.uuid4())
    return new_user_id, True

@app.get("/", response_class=HTMLResponse)
async def home(response: Response, user_id: str = Cookie(None)):
    user_id, is_new = get_or_create_user_id(user_id)
    
    if is_new:
        response.set_cookie(
            key="user_id",
            value=user_id,
            max_age=31536000,  # 1 year
            httponly=True,
            samesite="lax"
        )
    
    with open("index.html", "r") as f:
        html_content = f.read()
        # Inject user_id into HTML
        html_content = html_content.replace("<!-- USER_ID_PLACEHOLDER -->", 
                                           f'<script>window.USER_ID = "{user_id}";</script>')
    
    return HTMLResponse(content=html_content)

@app.get("/api/stream-prices")
async def stream_prices(request: Request):
    client_q = await price_broadcaster.register(max_queue_size=200)

    async def event_gen():
        try:
            async for chunk in sse_event_generator(client_q):
                yield chunk
                if await request.is_disconnected():
                    break
        finally:
            await price_broadcaster.unregister(client_q)

    return StreamingResponse(event_gen(), media_type="text/event-stream")

@app.get("/api/stream-alerts")
async def stream_alerts(request: Request, user_id: str = Cookie(None)):
    """Stream only alerts for this specific user"""
    if not user_id:
        return JSONResponse({"error": "No user_id"}, status_code=400)
    
    client_q = await alert_broadcaster.register(max_queue_size=200)

    async def event_gen():
        try:
            async for chunk in sse_event_generator(client_q):
                # Parse the data to filter by user_id
                if chunk.startswith("data: "):
                    try:
                        data = json.loads(chunk[6:])
                        if data.get("user_id") == user_id:
                            yield chunk
                    except:
                        pass
                else:
                    yield chunk  # heartbeat
                
                if await request.is_disconnected():
                    break
        finally:
            await alert_broadcaster.unregister(client_q)

    return StreamingResponse(event_gen(), media_type="text/event-stream")

@app.post("/api/set-alert")
async def set_alert(alert: dict, user_id: str = Cookie(None)):
    if not user_id:
        return JSONResponse({"error": "No user_id"}, status_code=400)
    
    ticker = alert["ticker"]
    threshold = float(alert["threshold"])
    alert_type = alert["type"]
    
    # Generate unique alert ID
    alert_id = str(uuid.uuid4())
    
    # Store alert with user_id in Redis
    alert_key = f"alert:{alert_id}"
    redis_client.hset(
        alert_key,
        mapping={
            "user_id": user_id,
            "ticker": ticker,
            "threshold": str(threshold),
            "type": alert_type,
            "created_at": str(time.time())
        }
    )
    
    # Add to user's alert list
    redis_client.sadd(f"user_alerts:{user_id}", alert_id)
    
    # Add to ticker's alert list for quick lookup
    redis_client.sadd(f"ticker_alerts:{ticker}", alert_id)
    
    print(f"[SET_ALERT] User {user_id[:8]} set alert {alert_id[:8]} for {ticker} {alert_type} ${threshold}")
    
    return {
        "message": f"Alert set for {ticker}",
        "alert_id": alert_id
    }

@app.get("/api/get-alerts")
async def get_alerts(user_id: str = Cookie(None)):
    """Get all active alerts for a user"""
    if not user_id:
        return JSONResponse({"error": "No user_id"}, status_code=400)
    
    alert_ids = redis_client.smembers(f"user_alerts:{user_id}")
    alerts = []
    
    for alert_id in alert_ids:
        alert_data = redis_client.hgetall(f"alert:{alert_id}")
        if alert_data:
            alerts.append({
                "alert_id": alert_id,
                "ticker": alert_data.get("ticker"),
                "threshold": float(alert_data.get("threshold", 0)),
                "type": alert_data.get("type"),
                "created_at": float(alert_data.get("created_at", 0))
            })
    
    # Sort by creation time
    alerts.sort(key=lambda x: x["created_at"], reverse=True)
    
    return {"alerts": alerts}

@app.delete("/api/delete-alert/{alert_id}")
async def delete_alert(alert_id: str, user_id: str = Cookie(None)):
    """Delete a specific alert"""
    if not user_id:
        return JSONResponse({"error": "No user_id"}, status_code=400)
    
    # Verify alert belongs to user
    alert_data = redis_client.hgetall(f"alert:{alert_id}")
    if not alert_data or alert_data.get("user_id") != user_id:
        return JSONResponse({"error": "Alert not found or unauthorized"}, status_code=404)
    
    ticker = alert_data.get("ticker")
    
    # Remove from all sets
    redis_client.srem(f"user_alerts:{user_id}", alert_id)
    redis_client.srem(f"ticker_alerts:{ticker}", alert_id)
    redis_client.delete(f"alert:{alert_id}")
    
    print(f"[DELETE_ALERT] User {user_id[:8]} deleted alert {alert_id[:8]}")
    
    return {"message": "Alert deleted"}

@app.get("/health")
def health():
    return {"status": "healthy"}
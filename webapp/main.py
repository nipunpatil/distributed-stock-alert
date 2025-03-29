import asyncio
import json
import threading
import time
from typing import Set

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
import redis
from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable

app = FastAPI(title="Stock Alert Dashboard (Scalable SSE)")

redis_client = redis.Redis(host="redis", port=6379, decode_responses=True)

# Broadcaster
class Broadcaster:
    def __init__(self):
        self._clients: Set[asyncio.Queue] = set()
        # lock for async-safe client changes
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
            # put without blocking; drop if full
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                # dropped for this client
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
            # schedule broadcast on the main asyncio loop
            asyncio.run_coroutine_threadsafe(broadcaster.broadcast(value), loop)
    except Exception as e:
        print(f"[kafka_consumer_runner] Error for {topic}: {e}")
    finally:
        try:
            consumer.close()
        except Exception:
            pass
        print(f"[kafka_consumer_runner] Exiting consumer thread for {topic}")

# keep refs to stop threads on shutdown
_consumer_threads = []
_stop_events = []

# Startup/shutdown
@app.on_event("startup")
async def startup_event():
    loop = asyncio.get_event_loop()

    # start a consumer thread per topic
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
    # signal threads to stop and join them
    for ev in _stop_events:
        ev.set()
    for t in _consumer_threads:
        t.join(timeout=5)
    print("[shutdown] consumer threads stopped")

# SSE helper (heartbeats too)
async def sse_event_generator(client_queue: asyncio.Queue, heartbeat_interval: float = 15.0):
    """yield SSE messages and periodic heartbeats."""
    last_heartbeat = time.time()
    try:
        while True:
            # wait for a message or heartbeat timeout
            try:
                timeout = max(0, last_heartbeat + heartbeat_interval - time.time())
                message = await asyncio.wait_for(client_queue.get(), timeout=timeout)
                # regular SSE data
                yield f"data: {json.dumps(message)}\n\n"
            except asyncio.TimeoutError:
                # send a comment heartbeat to keep the connection alive
                last_heartbeat = time.time()
                yield ": heartbeat\n\n"
    finally:
        # generator consumer is disconnecting
        return

@app.get("/", response_class=HTMLResponse)
async def home():
    with open("index.html", "r") as f:
        return HTMLResponse(content=f.read())

@app.get("/api/stream-prices")
async def stream_prices(request: Request):
    """
    SSE stream for live stock prices.
    Each client gets its own asyncio.Queue and the shared price_broadcaster dispatches messages into it.
    """
    client_q = await price_broadcaster.register(max_queue_size=200)

    async def event_gen():
        try:
            async for chunk in sse_event_generator(client_q):
                # if client disconnects, FastAPI will cancel and we break
                yield chunk
                if await request.is_disconnected():
                    break
        finally:
            await price_broadcaster.unregister(client_q)

    return StreamingResponse(event_gen(), media_type="text/event-stream")

@app.get("/api/stream-alerts")
async def stream_alerts(request: Request):
    client_q = await alert_broadcaster.register(max_queue_size=200)

    async def event_gen():
        try:
            async for chunk in sse_event_generator(client_q):
                yield chunk
                if await request.is_disconnected():
                    break
        finally:
            await alert_broadcaster.unregister(client_q)

    return StreamingResponse(event_gen(), media_type="text/event-stream")

@app.post("/api/set-alert")
async def set_alert(alert: dict):
    ticker = alert["ticker"]
    threshold = float(alert["threshold"])
    alert_type = alert["type"]

    redis_client.hset(
        f"alerts:{ticker}",
        mapping={"threshold": str(threshold), "type": alert_type}
    )
    return {"message": f"Alert set for {ticker}"}

@app.get("/health")
def health():
    return {"status": "healthy"}

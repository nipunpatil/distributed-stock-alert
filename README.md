# 📈 Real-Time Stock Alert System

A highly scalable, event-driven microservices platform for real-time stock price monitoring and user-specific alerting.

## 🎯 Overview

This system monitors 15+ assets (stocks, commodities, crypto) in real-time and triggers personalized alerts when prices cross user-defined thresholds. Built with Kafka, Redis, FastAPI, and Docker.

### Key Features
- 🚀 Real-time price updates via Server-Sent Events (SSE)
- 👤 User-specific alerts with automatic ID generation (no login required)
- ⚡ Event-driven architecture with Apache Kafka
- 🔔 Multiple alerts per stock per user
- 🎯 Auto-deletion of triggered alerts
- 📊 Scalable to 10,000+ concurrent users
- 🔄 Zero-downtime deployments

---

## 🏗️ Architecture

### High-Level System Design

```
┌──────────────────────────────────────────────────────────────┐
│                     CLIENT LAYER (10k+ Users)                 │
│  Browser → SSE Connections → Real-time Updates               │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ↓
┌────────────────────────────────────────────────────────────┐
│                   NGINX LOAD BALANCER                       │
│  - Round-robin distribution                                │
│  - Sticky sessions for SSE                                 │
└────────────────────┬───────────────────────────────────────┘
                     │
                     ↓
┌────────────────────────────────────────────────────────────┐
│              WEBAPP LAYER (FastAPI + Uvicorn)              │
│  Multiple Instances (Horizontal Scaling)                   │
│  ├─ REST API endpoints                                     │
│  ├─ SSE streaming (prices + alerts)                        │
│  ├─ User session management (cookies)                      │
│  └─ Alert CRUD operations                                  │
└───────────┬────────────────────┬───────────────────────────┘
            │                    │
            ↓                    ↓
┌──────────────────────┐  ┌──────────────────────────────────┐
│   REDIS CLUSTER      │  │    KAFKA MESSAGE BROKER          │
│   (State Store)      │  │    (Event Streaming)             │
│   ├─ User sessions   │  │    Topics:                       │
│   ├─ Alert configs   │  │    ├─ stock-prices               │
│   └─ Fast lookups    │  │    └─ alerts                     │
└──────────────────────┘  └──────────┬───────────────────────┘
                                     │
               ┌─────────────────────┼─────────────────────┐
               ↓                     ↓                     ↓
       ┌──────────────┐      ┌──────────────┐     ┌──────────────┐
       │  PRODUCER    │      │  CONSUMER    │     │  NOTIFIER    │
       │  (Stock Data)│      │  (Alert Eval)│     │  (Delivery)  │
       └──────────────┘      └──────────────┘     └──────────────┘
```

---

## 🔧 Components

### 1. Producer Service (Stock Price Fetcher)
**Tech:** Python + yfinance + Kafka Producer  
**Function:** Fetches real-time prices every 1 second, publishes to stock-prices topic  
**Assets:** SBI, GOOGL, MSFT, TSLA, BTC-USD, ETH-USD, Gold, Silver, etc.  
**Scalability:** Stateless, can run multiple instances with ticker distribution

### 2. Kafka Broker (Message Bus)
**Tech:** Apache Kafka (KRaft mode)  
**Topics:**  
- stock-prices: Real-time price updates (15 msg/s)  
- alerts: Triggered alerts (variable)

**Current:** Single broker (dev), **Production:** 3+ broker cluster  
**Throughput:** 100k+ messages/second per broker

### 3. Consumer Service (Alert Evaluator)
**Tech:** Python + Kafka Consumer + Redis  
**Function:**
- Consumes price updates
- Checks user alerts from Redis
- Triggers matching alerts
- Publishes to alerts topic
- Auto-deletes triggered alerts

**Scalability:** Multiple instances in same consumer group (parallel processing)  
**Performance:** 1000+ alert evaluations/second per instance

### 4. Redis Cache Layer (State Management)
**Tech:** Redis 7 with AOF persistence  
**Data Structures:**
```
alert:{alert_id}        → Hash {user_id, ticker, threshold, type}
user_alerts:{user_id}   → Set [alert_id_1, alert_id_2, ...]
ticker_alerts:{ticker}  → Set [alert_id_1, alert_id_2, ...]
```
**Scalability:** Single instance → Redis Cluster (6 nodes) for 300k+ ops/sec

### 5. WebApp Service (API + SSE Gateway)
**Tech:** FastAPI + Uvicorn + AsyncIO  
**Features:**
- REST API for alert management
- SSE streams for real-time updates
- Cookie-based user identification
- Broadcaster pattern for efficient fanout

**Endpoints:**
```
GET / - Dashboard UI
GET /api/stream-prices - SSE price feed
GET /api/stream-alerts - SSE user-specific alerts
POST /api/set-alert - Create alert
GET /api/get-alerts - List user alerts
DELETE /api/delete-alert/{id} - Remove alert
```
**Scalability:** 10k SSE connections per instance

### 6. Notifier Service (Alert Delivery)
**Tech:** Python + Kafka Consumer  
**Function:** Consumes alerts topic, logs notifications (extensible for email/SMS)  
**Future:** Integration with SendGrid, Twilio, Firebase Cloud Messaging

### 7. Nginx Load Balancer
**Function:** Distributes traffic across webapp instances  
**Config:** Sticky sessions for SSE connections  
**Scalability:** 10k+ requests/second

---

## 📊 Data Flow

### Flow 1: Stock Price Update
1. Producer fetches SBI: ₹178.52 from Yahoo Finance  
2. Producer → Kafka (stock-prices topic)  
3. Kafka → Consumer (alert-evaluators group)  
4. Consumer checks Redis: ticker_alerts:SBI → [alert_1, alert_2]  
5. Consumer evaluates: price > threshold?  
6. If triggered: Publishes to Kafka (alerts topic) + Deletes alert from Redis  
7. Kafka → WebApp (SSE stream) → Filters by user_id  
8. WebApp → User's browser (SSE) → Shows alert banner + beep

### Flow 2: User Sets Alert
1. User clicks "Set Alert": SBI above ₹180  
2. Browser POST /api/set-alert (with user_id cookie)  
3. WebApp generates alert_id = uuid-456  
4. WebApp writes to Redis (3 ops: HSET + SADD + SADD)  
5. WebApp responds: `{message: "Alert set"}`  
6. Browser refreshes alerts panel (GET /api/get-alerts)

### Flow 3: Alert Triggered
1. SBI price crosses ₹180.50 (threshold: ₹180)  
2. Consumer publishes to Kafka alerts topic  
3. Redis cleanup (SREM + DEL)  
4. WebApp receives → Filters by user_id  
5. SSE stream sends to user  
6. Browser plays beep + refreshes alert list  

**End-to-End Latency:** 20–50ms (local network)

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- 8GB RAM minimum
- Ports: 80, 6379, 9000, 9092, 8089

### 1. Clone & Start
```bash
git clone https://github.com/your-repo/stock-alerts.git
cd stock-alerts

# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f webapp
docker-compose logs -f consumer
```

### 2. Access Services
- Dashboard: [http://localhost](http://localhost)
- Kafdrop (Kafka UI): [http://localhost:9000](http://localhost:9000)
- Locust (Load Testing): [http://localhost:8089](http://localhost:8089)

### 3. Set Your First Alert
- Open dashboard → Wait for prices to load  
- Enter threshold (e.g., 200.00)  
- Select "Above" or "Below"  
- Click **Set Alert**  
- Watch "Active Alerts" panel

### 4. Stop Services
```bash
docker-compose down
# Or with volume cleanup:
docker-compose down -v
```

---

## 📁 Project Structure
```
stock-alerts/
├── producer/
│   ├── app.py              # Stock price fetcher
│   ├── requirements.txt
│   └── Dockerfile
├── consumer/
│   ├── app.py              # Alert evaluator
│   ├── requirements.txt
│   └── Dockerfile
├── notifier/
│   ├── app.py              # Notification service
│   ├── requirements.txt
│   └── Dockerfile
├── webapp/
│   ├── main.py             # FastAPI server
│   ├── index.html          # Dashboard UI
│   ├── requirements.txt
│   └── Dockerfile
├── locust/
│   └── locustfile.py       # Load testing script
├── docker-compose.yml      # Service orchestration
├── nginx.conf              # Load balancer config
└── README.md
```

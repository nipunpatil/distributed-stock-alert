Stock Ticker Project
A real-time, containerized cryptocurrency price tracker with alerting and interactive charting—built using Python, FastAPI, PostgreSQL, Kafka, Redis, and Chart.js. Easily monitor live prices for top cryptocurrencies, set one-time alerts, and view historical price charts in an intuitive web dashboard.

Features
Live Price Updates: See real-time prices for Bitcoin (BTC), Ethereum (ETH), and Dogecoin (DOGE), streamed with zero page refresh.

One-Time Price Alerts: Set automatic notifications for price movements (above/below a threshold)—get notified the moment your target is hit.

Rich Visual Charts: Click any ticker to instantly open a modal with a 100-point historical line chart, powered by Chart.js.

Persistent History: Prices are stored in a PostgreSQL database, ensuring you can always view recent trends.

Responsive UI: Clean, flexible and modern interface for desktops and mobile browsers alike.

Quickstart
Prerequisites
Docker & Docker Compose

Run Locally
bash
git clone <your_repo_url>
cd stock-ticker-project
docker-compose up --build
Access the App
Open your browser at: http://localhost:8000

Architecture
Service	Description
Zookeeper, Kafka	Message brokering for all streaming tick data
PostgreSQL	Persistent storage for price history
Redis	Real-time pub/sub for alert notifications
data-fetcher	Python microservice: fetches latest crypto prices and publishes to Kafka
data-processor	Python microservice: consumes prices, persists to DB, and handles alerts
api-server	FastAPI backend: serves REST endpoints, WebSocket events, and static frontend
UI (static)	HTML, CSS, Chart.js, and vanilla JS—single-page app
All services run in Docker containers and wire together seamlessly.

How It Works
Fetching: data-fetcher polls yfinance every 2 seconds for the latest prices.

Processing: data-processor listens to Kafka, pushes updates to PostgreSQL, checks alert thresholds, and triggers Redis notifications.

API & WebSockets: api-server distributes real-time updates/alerts and serves chart data through REST and WebSockets.

Frontend: Click any ticker in the UI to bring up a historical price chart—with all interactions handled live.

Using the App
Set Alerts: Define alerts for specific price conditions using the provided form. When your alert triggers, you’ll get a notification at the top of the dashboard.

Price Charts: Click on any price card (BTC, ETH, DOGE) to instantly see its recent price movement chart in a modal popup.

See Active Alerts: Manage your active one-time alerts in the “Current Alerts” section.

File Structure
text
stock-ticker-project/
│
├── docker-compose.yml
├── data-fetcher/
│   ├── Dockerfile
│   ├── fetcher.py
│   └── requirements.txt
├── data-processor/
│   ├── Dockerfile
│   ├── processor.py
│   └── requirements.txt
├── api-server/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py
│       ├── __init__.py
│       └── static/
│           ├── index.html
│           ├── style.css
│           └── script.js
Customization
Add More Tickers: Edit TICKERS in data-fetcher/fetcher.py and update frontend dropdowns to track more coins.

Chart Size/Points: Change the data points returned in the /history/{ticker} API.

Alert Logic: Extend data-processor/processor.py for more advanced alerting features (recurring, email, etc.).

Troubleshooting
If you see connection or dependency errors, try:

Restarting containers (docker-compose down && docker-compose up --build)

Ensuring Docker has enough resources (memory/CPU)

Waiting a few moments for all services to become healthy

License
MIT License. See LICENSE for details.

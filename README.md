# Stock Ticker Project

This project delivers a real-time, fully containerized cryptocurrency dashboard. Watch live price updates, set one-time price alerts, and explore historical price charts in a simple, elegant web interface. Everything runs locally in Docker—no manual setup or server wrangling required.

**Repository:** [https://github.com/nipunpatil/distributed-stock-alert/](https://github.com/nipunpatil/distributed-stock-alert/)

_Last updated: Saturday, July 19, 2025, 4:53 PM IST_

---

## What’s Included

- **Instant price updates:** See live prices for Bitcoin (BTC), Ethereum (ETH), and Dogecoin (DOGE) update automatically—no refresh needed.
- **One-time custom alerts:** Get notified in your browser as soon as your chosen price target is crossed.
- **Interactive charts:** Click any ticker to bring up a clear, scrollable price history, displayed as a real-time line chart.
- **Persistent price history:** All price data is saved to PostgreSQL, so you can review recent trends at any time.
- **Responsive web app:** The interface looks sharp and works smoothly on desktop and mobile browsers alike.

---

## How to Get Started

### Prerequisites

- [Docker](https://www.docker.com/get-started)
- [Docker Compose](https://docs.docker.com/compose/)

### Launch the Project

1. Clone the repository:
    ```
    git clone https://github.com/nipunpatil/distributed-stock-alert/
    cd distributed-stock-alert
    ```
2. Start everything:
    ```
    docker-compose up --build
    ```

3. Visit [http://localhost:8000](http://localhost:8000) in your browser.

---

## Architecture Overview

The project is broken up into self-contained services for maximum reliability and testability:

| Service         | Role                                                                  |
|-----------------|-----------------------------------------------------------------------|
| Zookeeper, Kafka| Real-time data streaming backbone                                     |
| PostgreSQL      | Persistent database for price history                                 |
| Redis           | Immediate notifications for alerts                                    |
| data-fetcher    | Scrapes latest crypto prices and publishes to Kafka                   |
| data-processor  | Stores price updates in the database, checks, and triggers alerts     |
| api-server      | FastAPI REST and WebSocket API, hosts the frontend app                |
| UI (static)     | Single page app: HTML, CSS, Chart.js, JS                             |

All services are Dockerized; dependencies and startup sequence are handled by Docker Compose.

---

## How It Works

1. `data-fetcher` collects fresh prices for BTC, ETH, and DOGE every two seconds and streams them via Kafka.
2. `data-processor` consumes price messages, stores them in PostgreSQL, tracks user-defined alerts, and sends alert notifications through Redis.
3. `api-server` serves data and events through both REST and WebSocket—driving the UI and push notifications.
4. The web UI shows live prices, lets you set one-time alerts, displays a feed of your alerts, and presents price history with a click.

---

## Using the App

- **Live Ticker Cards:** Watch the prices of your favorite coins update instantly. Card highlights show the price direction.
- **Set Custom Alerts:** Use the simple form to set a threshold (above or below) for each coin—alerts are one-time and easy to manage.
- **Interactive Charts:** Click any coin’s card to instantly view recent price history in a line chart modal.
- **Alerts Feed:** Quickly review which alerts are active and get notified right away at the top of the dashboard when a condition is met.

---

## File Structure

distributed-stock-alert/
├── docker-compose.yml
├── data-fetcher/
│ ├── Dockerfile
│ ├── fetcher.py
│ └── requirements.txt
├── data-processor/
│ ├── Dockerfile
│ ├── processor.py
│ └── requirements.txt
├── api-server/
│ ├── Dockerfile
│ ├── requirements.txt
│ └── app/
│ ├── main.py
│ ├── init.py
│ └── static/
│ ├── index.html
│ ├── style.css
│ └── script.js



---

## Customization

- **Add your own tickers:** Add or change coins in `data-fetcher/fetcher.py` and update the frontend dropdown menu.
- **Chart detail:** To change the number of points shown on charts, adjust the `/history/{ticker}` endpoint in `api-server/app/main.py`.
- **Advanced notifications:** Expand `data-processor/processor.py` to support more alerting features, such as recurring alerts, email, or SMS.

---

## Troubleshooting

- If the UI loads but prices or alerts don’t update right away, allow a minute for all containers to fully initialize.
- If you see connection or missing dependency errors:
    - Restart everything with:  
      `docker-compose down && docker-compose up --build`
    - Make sure Docker has enough RAM and CPU allocated.
    - Check individual container logs for more details.

---

## License

MIT License. See LICENSE for full details.

**Questions, improvements, or ideas? Pull requests and feedback are always welcome. Happy trading!**

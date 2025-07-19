document.addEventListener("DOMContentLoaded", () => {
    const tickers = ["BTC-USD", "ETH-USD", "DOGE-USD"];
    const tickersContainer = document.getElementById("tickers-container");
    const alertForm = document.getElementById("alert-form");
    const alertsList = document.getElementById("alerts-list");
    const notificationsList = document.getElementById("notifications-list");
    const tickerState = {};

    // NEW Chart variables
    const chartModal = document.getElementById("chartModal");
    const closeButton = document.querySelector(".close-button");
    const chartTickerTitle = document.getElementById("chart-ticker-title");
    const priceChartCanvas = document.getElementById("priceChart");
    let priceChart = null; // To hold the chart instance

    tickers.forEach(ticker => {
        const card = document.createElement("div");
        card.className = "ticker-card";
        card.id = `ticker-${ticker}`;
        card.innerHTML = `<div class="name">${ticker}</div><div class="price">Connecting...</div>`;
        
        // NEW: Add click listener to each card
        card.addEventListener("click", () => showChart(ticker));

        tickersContainer.appendChild(card);
        tickerState[ticker] = { lastPrice: 0 };
    });

    function connectWebSocket() {
        const ws = new WebSocket(`ws://${window.location.host}/ws`);
        ws.onopen = () => console.log("WebSocket connected.");
        ws.onerror = (error) => console.error("WebSocket Error:", error);
        ws.onclose = () => { console.log("WebSocket disconnected. Reconnecting..."); setTimeout(connectWebSocket, 3000); };
        ws.onmessage = (event) => {
            const message = JSON.parse(event.data);
            if (message.type === 'price_update') handlePriceUpdate(message.data);
            else if (message.type === 'alert_triggered') handleAlertTriggered(message.data);
        };
    }

    function handlePriceUpdate(data) {
        const { ticker, price } = data;
        const card = document.getElementById(`ticker-${ticker}`);
        if (card) {
            const priceElement = card.querySelector(".price");
            priceElement.textContent = `$${price.toFixed(4)}`;
            if (price > tickerState[ticker].lastPrice && tickerState[ticker].lastPrice !== 0) {
                card.classList.add("price-up"); card.classList.remove("price-down");
            } else if (price < tickerState[ticker].lastPrice) {
                card.classList.add("price-down"); card.classList.remove("price-up");
            }
            tickerState[ticker].lastPrice = price;
            setTimeout(() => card.classList.remove("price-up", "price-down"), 500);
        }
    }

    function handleAlertTriggered(data) {
        const { ticker, price, direction, threshold } = data;
        const notificationDiv = document.createElement('div');
        notificationDiv.className = 'notification success';
        notificationDiv.innerHTML = `<strong>ALERT!</strong> ${ticker} at <strong>$${price.toFixed(4)}</strong> has gone ${direction} your threshold of $${parseFloat(threshold).toFixed(4)}.`;
        notificationsList.prepend(notificationDiv);
        fetchAndDisplayAlerts();
    }

    alertForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const formData = new FormData(alertForm);
        const alertData = { ticker: formData.get("ticker"), threshold: parseFloat(formData.get("threshold")), direction: formData.get("direction") };
        try {
            const response = await fetch("/alerts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(alertData) });
            if (response.ok) {
                alert("One-time alert has been set!");
                alertForm.reset();
                fetchAndDisplayAlerts();
            } else { alert("Failed to set alert."); }
        } catch (error) { console.error("Error setting alert:", error); }
    });

    async function fetchAndDisplayAlerts() {
        try {
            const response = await fetch("/alerts");
            const alerts = await response.json();
            alertsList.innerHTML = alerts.length === 0 ? "<li>No active alerts.</li>" : alerts.map(alert => `<li>${alert.ticker} - Alert when price is ${alert.direction} $${parseFloat(alert.threshold).toFixed(4)}</li>`).join('');
        } catch (error) { console.error("Error fetching alerts:", error); }
    }

    // NEW: Chart functions
    async function showChart(ticker) {
        try {
            const response = await fetch(`/history/${ticker}`);
            if (!response.ok) {
                alert("Could not fetch historical data.");
                return;
            }
            const data = await response.json();
            
            if (data.timestamps.length === 0) {
                alert("No historical data available yet for this ticker. Please wait a bit.");
                return;
            }

            chartTickerTitle.textContent = `${ticker} Price History (Last 100 points)`;
            
            // Destroy previous chart instance if it exists
            if (priceChart) {
                priceChart.destroy();
            }

            priceChart = new Chart(priceChartCanvas, {
                type: 'line',
                data: {
                    labels: data.timestamps,
                    datasets: [{
                        label: 'Price (USD)',
                        data: data.prices,
                        borderColor: 'rgb(75, 192, 192)',
                        backgroundColor: 'rgba(75, 192, 192, 0.2)',
                        borderWidth: 2,
                        tension: 0.1,
                        fill: true
                    }]
                },
                options: {
                    scales: { y: { beginAtZero: false } },
                    responsive: true
                }
            });

            chartModal.style.display = "flex";

        } catch (error) {
            console.error("Error showing chart:", error);
        }
    }

    closeButton.onclick = () => chartModal.style.display = "none";
    window.onclick = (event) => {
        if (event.target == chartModal) {
            chartModal.style.display = "none";
        }
    };

    connectWebSocket();
    fetchAndDisplayAlerts();
});

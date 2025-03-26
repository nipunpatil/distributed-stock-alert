from locust import HttpUser, task, between
import json

class StockDashboardUser(HttpUser):
    wait_time = between(1, 3)
    
    @task(3)
    def view_dashboard(self):
        self.client.get("/")
    
    @task(1)
    def set_alert(self):
        self.client.post("/api/set-alert", json={
            "ticker": "AAPL",
            "threshold": 200.0,
            "type": "above"
        })
    
    @task(2)
    def health_check(self):
        self.client.get("/health")

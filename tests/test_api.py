from fastapi.testclient import TestClient
from agent_hemo.api.main import app

client = TestClient(app)

def test_health():
    assert client.get("/health").json() == {"status": "ok"}

def test_alerts():
    r = client.post("/alerts", json={"csv_path": "data/bag_info.csv", "date": "2026-06-18"})
    assert r.status_code == 200
    assert "alerts" in r.json()
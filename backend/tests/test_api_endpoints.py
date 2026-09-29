import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine

Base.metadata.create_all(bind=engine)
client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_create_report_and_list():
    payload = {
        "text": "Severe wildfire burning near forest perimeter",
        "latitude": 37.7749,
        "longitude": -122.4194,
        "source": "citizen"
    }
    response = client.post("/reports", json=payload)
    assert response.status_code == 200, response.text
    data = response.json()
    assert "id" in data
    assert data["text"] == payload["text"]

    # Check list reports
    list_res = client.get("/reports")
    assert list_res.status_code == 200
    reports = list_res.json()
    assert any(r["id"] == data["id"] for r in reports)

def test_list_incidents():
    response = client.get("/incidents")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

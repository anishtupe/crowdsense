import uuid

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

def _register_and_login():
    email = f"{uuid.uuid4()}@example.com"
    password = "professor-demo-password"
    register_response = client.post(
        "/auth/register",
        json={"email": email, "password": password},
    )
    assert register_response.status_code == 200, register_response.text

    login_response = client.post(
        "/auth/login",
        data={"username": email, "password": password},
    )
    assert login_response.status_code == 200, login_response.text
    token = login_response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_authentication_endpoints():
    headers = _register_and_login()
    response = client.get("/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["role"] == "citizen"

def test_create_report_requires_authentication():
    response = client.post(
        "/reports",
        json={
            "text": "Flooding near the river",
            "latitude": 37.7749,
            "longitude": -122.4194,
        },
    )
    assert response.status_code == 401

def test_create_report_and_list():
    headers = _register_and_login()
    payload = {
        "text": "Severe wildfire burning near forest perimeter",
        "latitude": 37.7749,
        "longitude": -122.4194,
        "source": "citizen"
    }
    response = client.post("/reports", json=payload, headers=headers)
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

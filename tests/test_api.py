import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client

def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    if "text/html" in response.headers.get("content-type", ""):
        assert "<!doctype html>" in response.text.lower() or "<html" in response.text.lower()
    else:
        data = response.json()
        assert "status" in data
        assert data["status"] == "online"

def test_list_facilities(client):
    response = client.get("/api/facilities")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 5
    facility_ids = [f["facility_id"] for f in data]
    assert "FAC_01" in facility_ids
    assert "FAC_02" in facility_ids

def test_facility_status(client):
    response = client.get("/api/facilities/FAC_02/status")
    assert response.status_code == 200
    data = response.json()
    assert data["facility_id"] == "FAC_02"
    assert "current_queue_length" in data
    assert "estimated_wait_time_min" in data
    assert "crowd_level" in data
    assert data["current_queue_length"] >= 0
    assert data["estimated_wait_time_min"] >= 0.0

def test_facility_forecast(client):
    response = client.get("/api/facilities/FAC_02/forecast?hours=3&interval_minutes=15")
    assert response.status_code == 200
    data = response.json()
    assert data["facility_id"] == "FAC_02"
    assert "intervals" in data
    assert len(data["intervals"]) > 0
    first_step = data["intervals"][0]
    assert "waiting_time_min" in first_step
    assert "queue_length" in first_step
    assert "prediction_method" in first_step

def test_custom_predict(client):
    payload = {
        "facility_id": "FAC_02",
        "datetime": "2026-10-15T12:30:00",
        "counters_open": 4
    }
    response = client.post("/api/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["facility_id"] == "FAC_02"
    assert data["predicted_wait_time_min"] >= 0.0
    assert data["predicted_queue_length"] >= 0
    assert "prediction_method" in data
    assert "explanation" in data

def test_best_time_slots(client):
    response = client.get("/api/facilities/FAC_01/best-time")
    assert response.status_code == 200
    data = response.json()
    assert "best_slots" in data
    assert len(data["best_slots"]) <= 3
    for slot in data["best_slots"]:
        assert "time_slot" in slot
        assert "waiting_time_min" in slot

def test_hourly_pattern(client):
    response = client.get("/api/facilities/FAC_02/hourly-pattern")
    assert response.status_code == 200
    data = response.json()
    assert "patterns" in data
    assert len(data["patterns"]) == 84 # 7 days * 12 hours

def test_peak_periods(client):
    response = client.get("/api/peaks")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    for peak in data:
        assert "facility_id" in peak
        assert "period_name" in peak
        assert "expected_wait_min" in peak

def test_recommendations(client):
    response = client.get("/api/recommendations")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    for rec in data:
        assert "facility_id" in rec
        assert "tip_text" in rec

def test_analytics_trends(client):
    response = client.get("/api/analytics/trends")
    assert response.status_code == 200
    data = response.json()
    assert "daily_trends" in data
    assert "weekly_trends" in data

def test_model_metrics(client):
    response = client.get("/api/model/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "best_models" in data
    assert "waiting_time_models" in data
    assert "queue_length_models" in data
    assert "peak_classifier_models" in data
    assert "baselines" in data
    assert "horizons" in data

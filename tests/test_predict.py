import pytest
from datetime import datetime
from ml.predict import (
    predict_queue_metrics,
    get_facility_forecast,
    get_best_time_slots,
    get_hourly_pattern,
    FACILITY_METADATA
)

def test_predict_queue_metrics_open_facility():
    # Thursday 12:30 PM (Cafeteria open)
    dt = datetime(2026, 10, 15, 12, 30, 0)
    pred = predict_queue_metrics("FAC_02", dt, horizon="15m")
    
    assert pred["facility_id"] == "FAC_02"
    assert pred["waiting_time_min"] >= 0.5
    assert pred["queue_length"] >= 0
    assert isinstance(pred["is_peak"], bool)
    assert pred["crowd_level"] in ["Low", "Medium", "High"]
    assert pred["counters_open"] > 0
    assert pred["prediction_method"] == "model_horizon_15m"

def test_predict_queue_metrics_closed_facility():
    # Sunday at midnight (Admin office closed)
    dt = datetime(2026, 10, 18, 2, 0, 0)
    pred = predict_queue_metrics("FAC_01", dt)
    
    assert pred["crowd_level"] == "Closed"
    assert pred["waiting_time_min"] == 0.0
    assert pred["queue_length"] == 0
    assert pred["counters_open"] == 0
    assert pred["prediction_method"] == "facility_closed"

def test_multi_horizon_forecasting():
    dt = datetime(2026, 10, 15, 12, 0, 0)
    forecast = get_facility_forecast("FAC_02", start_dt=dt, hours=3, interval_minutes=15)
    
    assert len(forecast) == 12 # 3 hours / 15m intervals
    methods = [step["prediction_method"] for step in forecast]
    
    assert "model_horizon_15m" in methods
    assert "model_horizon_1h" in methods
    assert "model_horizon_2h" in methods
    assert "model_horizon_3h" in methods

def test_best_time_slots():
    dt = datetime(2026, 10, 15, 8, 0, 0)
    slots = get_best_time_slots("FAC_01", target_date=dt, top_k=3)
    
    assert len(slots) <= 3
    for s in slots:
        assert s["waiting_time_min"] >= 0.0
        assert s["crowd_level"] in ["Low", "Medium", "High"]

def test_hourly_pattern():
    matrix = get_hourly_pattern("FAC_04")
    assert len(matrix) == 84
    for cell in matrix:
        assert 0 <= cell["day_of_week"] <= 6
        assert 8 <= cell["hour"] <= 19
        assert cell["avg_wait_time_min"] >= 0.0

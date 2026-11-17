import os
import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from ml.train import (
    build_temporal_features,
    get_feature_columns_for_horizon,
    fit_historical_lookups,
    apply_historical_lookups
)

@pytest.fixture
def sample_raw_dataframe():
    """Generates synthetic sequential raw rows for test verification."""
    rows = []
    base_time = datetime(2026, 5, 1, 8, 0, 0)
    for i in range(50):
        t = base_time + timedelta(minutes=10 * i)
        rows.append({
            "record_id": f"REC_{i:04d}",
            "timestamp": t.strftime("%Y-%m-%d %H:%M:%S"),
            "date": t.strftime("%Y-%m-%d"),
            "hour": t.hour,
            "minute": t.minute,
            "day_of_week": t.weekday(),
            "week_of_year": 18,
            "month": 5,
            "is_weekend": 0,
            "is_holiday": 0,
            "facility_id": "FAC_01",
            "facility_type": "Administrative",
            "service_type": "Verification",
            "counter_id": "FAC_01_C1",
            "num_counters_open": 2,
            "num_staff_on_duty": 3,
            "avg_service_time_min": 6.0,
            "arrival_rate": 15.0 + i,
            "departure_rate": 14.0 + i, # Simultaneous service outcome
            "queue_length_at_arrival": i,
            "group_size": 1.2,
            "academic_period": "Normal",
            "is_exam_week": 0,
            "class_schedule_density": 0.8,
            "event_flag": 0,
            "deadline_proximity_days": 15,
            "weather": "Sunny",
            "meal_period": "Non-Meal",
            "waiting_time_min": float(10 + i * 2),
            "queue_length": 5 + i,
            "is_peak": 1 if i > 10 else 0
        })
    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df

def test_departure_rate_excluded_from_all_horizons():
    """Verifies departure_rate is NEVER present in any model feature column list."""
    horizons = ["15m", "1h", "2h", "3h", "no_lag"]
    for h in horizons:
        cat_cols, num_cols = get_feature_columns_for_horizon(h)
        all_cols = cat_cols + num_cols
        assert "departure_rate" not in all_cols, f"Leakage: departure_rate found in horizon '{h}'"

def test_rolling_features_strictly_shifted(sample_raw_dataframe):
    """
    Verifies that rolling target features (e.g., waiting_time_rolling_30min)
    are strictly backward-looking (.shift(1)) and do NOT include the current row target.
    """
    df = build_temporal_features(sample_raw_dataframe)
    
    # For row index 1:
    # waiting_time_min at idx 1 is 12.0, idx 0 is 10.0.
    # Because of shift(1), rolling mean of window 3 at idx 1 must ONLY contain idx 0 (10.0), NOT idx 1 (12.0)
    val_idx_0 = sample_raw_dataframe.loc[0, "waiting_time_min"]
    val_idx_1 = sample_raw_dataframe.loc[1, "waiting_time_min"]
    rolling_at_1 = df.loc[1, "waiting_time_rolling_30min"]
    
    assert rolling_at_1 == val_idx_0, (
        f"Rolling average includes current row target! Got {rolling_at_1}, expected {val_idx_0}"
    )
    assert rolling_at_1 != (val_idx_0 + val_idx_1) / 2.0, (
        "Rolling average contains current target y_t!"
    )

def test_lag_features_use_strictly_past_timestamps(sample_raw_dataframe):
    """Verifies that for any row t, lag_1 corresponds to row t-1."""
    df = build_temporal_features(sample_raw_dataframe)
    for i in range(1, len(df)):
        assert df.loc[i, "queue_length_lag_1"] == sample_raw_dataframe.loc[i - 1, "queue_length"]
        assert df.loc[i, "waiting_time_lag_1"] == sample_raw_dataframe.loc[i - 1, "waiting_time_min"]

def test_lookups_fitted_on_train_only(sample_raw_dataframe):
    """Verifies that lookup tables fitted on train split do not leak test split target values."""
    train_split = sample_raw_dataframe.iloc[:25].copy()
    test_split = sample_raw_dataframe.iloc[25:].copy()
    
    # Fit lookup strictly on train
    lookup_table, g_wait, g_queue, g_peak = fit_historical_lookups(train_split)
    
    # Compute expected mean solely from train split
    train_expected_wait = train_split["waiting_time_min"].mean()
    assert abs(g_wait - train_expected_wait) < 1e-5
    
    # Check that applying lookup does not alter based on test data
    test_transformed = apply_historical_lookups(test_split, lookup_table, g_wait, g_queue, g_peak)
    assert "hist_wait_mean" in test_transformed.columns
    # The applied historical mean must match train mean, not test mean
    assert test_transformed["hist_wait_mean"].iloc[0] <= train_split["waiting_time_min"].max() + 1.0

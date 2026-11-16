import os
import json
import math
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
import joblib

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

# Artifact cache
_CACHED_MODELS: Dict[str, Any] = {}
_CACHED_PREPS: Dict[str, Any] = {}
_LOOKUP_DF: Optional[pd.DataFrame] = None
_GLOBAL_LOOKUP_STATS = {"wait": 7.8, "queue": 3.4, "peak": 0.24}

FACILITY_METADATA = {
    "FAC_01": {
        "id": "FAC_01",
        "name": "Admin Office",
        "type": "Administrative",
        "services": ["Document Verification", "Transcript Request", "Student ID Issuance"],
        "base_service_mean": 6.0,
        "default_counters": 2,
        "max_counters": 4,
        "closed_on_weekend": True,
        "location": "Administration Hall, Room 102",
        "operating_hours": "08:00 - 18:00 (Mon-Fri)"
    },
    "FAC_02": {
        "id": "FAC_02",
        "name": "Main Cafeteria",
        "type": "Dining",
        "services": ["Meal Purchase", "Snack & Beverage", "Express Counter"],
        "base_service_mean": 2.0,
        "default_counters": 4,
        "max_counters": 6,
        "closed_on_weekend": False,
        "location": "Student Center, Ground Floor",
        "operating_hours": "08:00 - 20:00 (Daily)"
    },
    "FAC_03": {
        "id": "FAC_03",
        "name": "Student Services Counter",
        "type": "Student Services",
        "services": ["Academic Advising", "Financial Aid Inquiry", "Housing Assistance"],
        "base_service_mean": 6.5,
        "default_counters": 2,
        "max_counters": 4,
        "closed_on_weekend": True,
        "location": "Student Union, 2nd Floor",
        "operating_hours": "08:30 - 17:30 (Mon-Fri)"
    },
    "FAC_04": {
        "id": "FAC_04",
        "name": "Library Desk",
        "type": "Library",
        "services": ["Book Checkout & Return", "Study Room Booking", "Reference Assistance"],
        "base_service_mean": 3.0,
        "default_counters": 2,
        "max_counters": 3,
        "closed_on_weekend": False,
        "location": "Central Library, 1st Floor Atrium",
        "operating_hours": "08:00 - 22:00 (Daily)"
    },
    "FAC_05": {
        "id": "FAC_05",
        "name": "Fee Payment Counter",
        "type": "Financial",
        "services": ["Tuition Fee Payment", "Fine Payment", "Scholarship Check-in"],
        "base_service_mean": 5.0,
        "default_counters": 2,
        "max_counters": 4,
        "closed_on_weekend": True,
        "location": "Finance Building, Counter 1-4",
        "operating_hours": "09:00 - 16:30 (Mon-Fri)"
    }
}

def load_lookup_table() -> pd.DataFrame:
    global _LOOKUP_DF
    if _LOOKUP_DF is None:
        lookup_path = os.path.join(MODELS_DIR, "historical_hourly_lookup.csv")
        if os.path.exists(lookup_path):
            _LOOKUP_DF = pd.read_csv(lookup_path)
        else:
            _LOOKUP_DF = pd.DataFrame()
    return _LOOKUP_DF

def normalize_horizon(horizon: Optional[str]) -> str:
    if horizon in [None, "no_lag", "nolag", "calendar"]:
        return "nolag"
    return horizon

def load_horizon_artifacts(horizon: str):
    """
    Loads preprocessor and XGBoost models for a given horizon:
    '15m', '1h', '2h', '3h', or 'nolag'
    """
    global _CACHED_MODELS, _CACHED_PREPS
    norm_h = normalize_horizon(horizon)
    
    prep_key = f"prep_{norm_h}"
    wait_key = f"wait_{norm_h}"
    queue_key = f"queue_{norm_h}"
    peak_key = f"peak_{norm_h}"
    
    if prep_key not in _CACHED_PREPS:
        prep_path = os.path.join(MODELS_DIR, f"preprocessor_{norm_h}.joblib")
        wait_path = os.path.join(MODELS_DIR, f"model_wait_{norm_h}.joblib")
        queue_path = os.path.join(MODELS_DIR, f"model_queue_{norm_h}.joblib")
        peak_path = os.path.join(MODELS_DIR, f"model_peak_{norm_h}.joblib")
        
        _CACHED_PREPS[prep_key] = joblib.load(prep_path) if os.path.exists(prep_path) else None
        _CACHED_MODELS[wait_key] = joblib.load(wait_path) if os.path.exists(wait_path) else None
        _CACHED_MODELS[queue_key] = joblib.load(queue_path) if os.path.exists(queue_path) else None
        _CACHED_MODELS[peak_key] = joblib.load(peak_path) if os.path.exists(peak_path) else None
        
    return (
        _CACHED_PREPS.get(prep_key),
        _CACHED_MODELS.get(wait_key),
        _CACHED_MODELS.get(queue_key),
        _CACHED_MODELS.get(peak_key)
    )

def load_ml_artifacts():
    """Backward compatibility alias for loading default 15m artifacts."""
    return load_horizon_artifacts("15m")

def get_context_for_dt(dt: datetime, fac_id: str) -> Dict[str, Any]:
    """Computes realistic contextual covariates given datetime and facility."""
    meta = FACILITY_METADATA.get(fac_id, FACILITY_METADATA["FAC_01"])
    hour = dt.hour
    dow = dt.weekday()
    month = dt.month
    day = dt.day
    
    is_weekend = 1 if dow >= 5 else 0
    is_holiday = 1 if (month, day) in [(5, 25), (7, 4), (9, 7), (10, 12)] else 0
    
    if 8 <= hour < 10:
        meal = "Breakfast"
    elif 11 <= hour < 14:
        meal = "Lunch"
    elif 17 <= hour < 20:
        meal = "Dinner"
    else:
        meal = "Non-Meal"
        
    if month in [5, 6]:
        academic_period = "Registration" if (month == 5 and day <= 15) else "Normal"
        is_exam = 0
        deadline_prox = 14 if month == 5 else 25
    elif month in [7, 8]:
        academic_period = "Summer Break" if (month == 7 and day <= 20) else "Normal"
        is_exam = 0
        deadline_prox = 30
    elif month in [9, 10]:
        if month == 9 and 15 <= day <= 25:
            academic_period = "Midterms"
            is_exam = 1
            deadline_prox = 5
        elif month == 10 and 10 <= day <= 22:
            academic_period = "Fee Payment Due"
            is_exam = 0
            deadline_prox = 3
        else:
            academic_period = "Normal"
            is_exam = 0
            deadline_prox = 20
    else:
        academic_period = "Normal"
        is_exam = 0
        deadline_prox = 15
        
    class_density = 0.85 if (not is_weekend and not is_holiday and 9 <= hour <= 16) else 0.20
    weather = "Sunny"
    event_flag = 0
    
    if (meta["closed_on_weekend"] and is_weekend) or is_holiday or hour < 8 or hour >= 20:
        counters = 0
        staff = 0
    else:
        if fac_id == "FAC_02" and 12 <= hour < 14:
            counters = 5
        elif fac_id == "FAC_01" and 10 <= hour <= 15:
            counters = 3
        else:
            counters = meta["default_counters"]
        staff = counters + 1
        
    return {
        "facility_type": meta["type"],
        "num_counters_open": counters,
        "num_staff_on_duty": staff,
        "avg_service_time_min": meta["base_service_mean"],
        "academic_period": academic_period,
        "is_exam_week": is_exam,
        "class_schedule_density": class_density,
        "weather": weather,
        "meal_period": meal,
        "is_weekend": is_weekend,
        "is_holiday": is_holiday,
        "event_flag": event_flag,
        "deadline_proximity_days": deadline_prox
    }

def construct_feature_frame(
    fac_id: str,
    dt: datetime,
    horizon: str = "nolag",
    overrides: Optional[Dict[str, Any]] = None,
    current_state: Optional[Dict[str, float]] = None
) -> pd.DataFrame:
    """
    Constructs a feature row matching the exact features expected by the horizon preprocessor.
    Uses strictly train-fitted historical lookups and horizon-safe lags.
    """
    norm_h = normalize_horizon(horizon)
    ctx = get_context_for_dt(dt, fac_id)
    if overrides:
        ctx.update(overrides)
        
    hour = dt.hour
    minute = dt.minute
    dow = dt.weekday()
    
    # Train-fitted lookup
    lookup_df = load_lookup_table()
    hist_wait = _GLOBAL_LOOKUP_STATS["wait"]
    hist_queue = _GLOBAL_LOOKUP_STATS["queue"]
    hist_peak = _GLOBAL_LOOKUP_STATS["peak"]
    
    if not lookup_df.empty:
        match = lookup_df[
            (lookup_df["facility_id"] == fac_id) &
            (lookup_df["day_of_week"] == dow) &
            (lookup_df["hour"] == hour)
        ]
        if not match.empty:
            hist_wait = float(match["hist_wait_mean"].values[0])
            hist_queue = float(match["hist_queue_mean"].values[0])
            hist_peak = float(match["hist_peak_rate"].values[0])
            
    group_size = 2.2 if fac_id == "FAC_02" else 1.2
    
    row_data = {
        # Categoricals
        "facility_id": fac_id,
        "facility_type": ctx["facility_type"],
        "academic_period": ctx["academic_period"],
        "weather": ctx["weather"],
        "meal_period": ctx["meal_period"],
        # Base numericals
        "hour_sin": np.sin(2 * np.pi * hour / 24.0),
        "hour_cos": np.cos(2 * np.pi * hour / 24.0),
        "minute_sin": np.sin(2 * np.pi * minute / 60.0),
        "minute_cos": np.cos(2 * np.pi * minute / 60.0),
        "dow_sin": np.sin(2 * np.pi * dow / 7.0),
        "dow_cos": np.cos(2 * np.pi * dow / 7.0),
        "num_counters_open": ctx["num_counters_open"],
        "num_staff_on_duty": ctx["num_staff_on_duty"],
        "avg_service_time_min": ctx["avg_service_time_min"],
        "group_size": group_size,
        "class_schedule_density": ctx["class_schedule_density"],
        "is_weekend": ctx["is_weekend"],
        "is_holiday": ctx["is_holiday"],
        "is_exam_week": ctx["is_exam_week"],
        "event_flag": ctx["event_flag"],
        "deadline_proximity_days": ctx["deadline_proximity_days"],
        "hist_wait_mean": hist_wait,
        "hist_queue_mean": hist_queue,
        "hist_peak_rate": hist_peak
    }
    
    # State lags depending on horizon
    state = current_state or {}
    is_closed = (ctx["num_counters_open"] == 0)
    
    if norm_h == "15m":
        row_data["queue_length_lag_1"] = 0.0 if is_closed else state.get("queue_length_lag_1", hist_queue)
        row_data["queue_length_lag_2"] = 0.0 if is_closed else state.get("queue_length_lag_2", hist_queue * 0.95)
        row_data["queue_length_lag_3"] = 0.0 if is_closed else state.get("queue_length_lag_3", hist_queue * 0.90)
        row_data["waiting_time_lag_1"] = 0.0 if is_closed else state.get("waiting_time_lag_1", hist_wait)
        row_data["waiting_time_rolling_30min"] = 0.0 if is_closed else state.get("waiting_time_rolling_30min", hist_wait)
        row_data["arrivals_rolling_1h"] = 0.0 if is_closed else state.get("arrivals_rolling_1h", 12.0)
    elif norm_h == "1h":
        row_data["queue_length_lag_1h"] = 0.0 if is_closed else state.get("queue_length_lag_1h", hist_queue)
        row_data["waiting_time_lag_1h"] = 0.0 if is_closed else state.get("waiting_time_lag_1h", hist_wait)
    elif norm_h == "2h":
        row_data["queue_length_lag_2h"] = 0.0 if is_closed else state.get("queue_length_lag_2h", hist_queue)
        row_data["waiting_time_lag_2h"] = 0.0 if is_closed else state.get("waiting_time_lag_2h", hist_wait)
    elif norm_h == "3h":
        row_data["queue_length_lag_3h"] = 0.0 if is_closed else state.get("queue_length_lag_3h", hist_queue)
        row_data["waiting_time_lag_3h"] = 0.0 if is_closed else state.get("waiting_time_lag_3h", hist_wait)
        
    return pd.DataFrame([row_data]), ctx

def determine_crowd_level(wait_time: float, is_peak: bool) -> str:
    if wait_time < 5.0 and not is_peak:
        return "Low"
    elif wait_time < 14.0 and not is_peak:
        return "Medium"
    else:
        return "High"

def predict_queue_metrics(
    facility_id: str,
    dt: datetime,
    overrides: Optional[Dict[str, Any]] = None,
    horizon: Optional[str] = None,
    current_state: Optional[Dict[str, float]] = None
) -> Dict[str, Any]:
    """
    Horizon-aware inference engine.
    Uses multi-horizon models when lead time is known, or calendar models for arbitrary future dates.
    Returns prediction_method tag for transparent attribution.
    """
    meta = FACILITY_METADATA.get(facility_id, FACILITY_METADATA["FAC_01"])
    dow = dt.weekday()
    hour = dt.hour
    is_weekend = 1 if dow >= 5 else 0
    
    # Facility closure check
    if (meta["closed_on_weekend"] and is_weekend) or hour < 8 or hour >= 20:
        return {
            "facility_id": facility_id,
            "facility_name": meta["name"],
            "timestamp": dt.strftime("%Y-%m-%d %H:%M:%S"),
            "waiting_time_min": 0.0,
            "queue_length": 0,
            "is_peak": False,
            "crowd_level": "Closed",
            "counters_open": 0,
            "status_message": "Facility is currently closed",
            "prediction_method": "facility_closed"
        }
        
    # Determine appropriate horizon if not explicitly passed
    norm_h = normalize_horizon(horizon)
    method_label = f"model_horizon_{norm_h}" if norm_h != "nolag" else "model_calendar_nolag"
        
    prep, wait_m, queue_m, peak_m = load_horizon_artifacts(norm_h)
    X_df, ctx = construct_feature_frame(facility_id, dt, horizon=norm_h, overrides=overrides, current_state=current_state)
    
    # Check if artifacts are available
    if prep is None or wait_m is None or queue_m is None or peak_m is None:
        # Graceful fallback to historical train baseline lookup
        lookup_df = load_lookup_table()
        hist_wait = _GLOBAL_LOOKUP_STATS["wait"]
        hist_queue = _GLOBAL_LOOKUP_STATS["queue"]
        if not lookup_df.empty:
            match = lookup_df[
                (lookup_df["facility_id"] == facility_id) &
                (lookup_df["day_of_week"] == dow) &
                (lookup_df["hour"] == hour)
            ]
            if not match.empty:
                hist_wait = float(match["hist_wait_mean"].values[0])
                hist_queue = float(match["hist_queue_mean"].values[0])
                
        wait_time = round(hist_wait, 1)
        queue_len = int(round(hist_queue))
        is_peak = bool(wait_time >= 15.0)
        crowd = determine_crowd_level(wait_time, is_peak)
        return {
            "facility_id": facility_id,
            "facility_name": meta["name"],
            "timestamp": dt.strftime("%Y-%m-%d %H:%M:%S"),
            "waiting_time_min": wait_time,
            "queue_length": queue_len,
            "is_peak": is_peak,
            "crowd_level": crowd,
            "counters_open": ctx["num_counters_open"],
            "status_message": f"{crowd} crowd with ~{wait_time} min wait",
            "prediction_method": "historical_lookup"
        }
        
    # Model inference via preprocessor pipeline
    try:
        X_proc = prep.transform(X_df)
        raw_wait = float(wait_m.predict(X_proc)[0])
        raw_queue = float(queue_m.predict(X_proc)[0])
        raw_peak = int(peak_m.predict(X_proc)[0])
    except Exception as e:
        # Graceful non-recursive fallback to historical lookup
        lookup_df = load_lookup_table()
        hist_wait = _GLOBAL_LOOKUP_STATS["wait"]
        hist_queue = _GLOBAL_LOOKUP_STATS["queue"]
        if not lookup_df.empty:
            match = lookup_df[
                (lookup_df["facility_id"] == facility_id) &
                (lookup_df["day_of_week"] == dow) &
                (lookup_df["hour"] == hour)
            ]
            if not match.empty:
                hist_wait = float(match["hist_wait_mean"].values[0])
                hist_queue = float(match["hist_queue_mean"].values[0])
        wait_time = round(hist_wait, 1)
        queue_len = int(round(hist_queue))
        is_peak = bool(wait_time >= 15.0)
        crowd = determine_crowd_level(wait_time, is_peak)
        return {
            "facility_id": facility_id,
            "facility_name": meta["name"],
            "timestamp": dt.strftime("%Y-%m-%d %H:%M:%S"),
            "waiting_time_min": wait_time,
            "queue_length": queue_len,
            "is_peak": is_peak,
            "crowd_level": crowd,
            "counters_open": ctx["num_counters_open"],
            "status_message": f"{crowd} crowd with ~{wait_time} min wait",
            "prediction_method": "historical_lookup"
        }
        
    wait_time = max(0.5, round(raw_wait, 1))
    queue_len = max(0, int(round(raw_queue)))
    is_peak_bool = bool(raw_peak == 1 or wait_time >= 15.0)
    crowd_level = determine_crowd_level(wait_time, is_peak_bool)
    
    return {
        "facility_id": facility_id,
        "facility_name": meta["name"],
        "timestamp": dt.strftime("%Y-%m-%d %H:%M:%S"),
        "waiting_time_min": wait_time,
        "queue_length": queue_len,
        "is_peak": is_peak_bool,
        "crowd_level": crowd_level,
        "counters_open": ctx["num_counters_open"],
        "status_message": f"{crowd_level} crowd with ~{wait_time} min wait",
        "prediction_method": method_label
    }

def get_facility_forecast(
    facility_id: str,
    start_dt: Optional[datetime] = None,
    hours: int = 3,
    interval_minutes: int = 15
) -> List[Dict[str, Any]]:
    """
    Generates multi-horizon forecast.
    Selects the horizon model matched to the forecasting lead time:
    - <= 15 min: model_horizon_15m
    - 16 - 60 min: model_horizon_1h
    - 61 - 120 min: model_horizon_2h
    - 121 - 180 min: model_horizon_3h
    - > 180 min: model_calendar_nolag
    """
    if start_dt is None:
        start_dt = datetime.now()
        
    results = []
    total_steps = int((hours * 60) / interval_minutes)
    
    for i in range(total_steps):
        lead_min = i * interval_minutes
        slot_dt = start_dt + timedelta(minutes=lead_min)
        
        if lead_min <= 15:
            horizon = "15m"
        elif lead_min <= 60:
            horizon = "1h"
        elif lead_min <= 120:
            horizon = "2h"
        elif lead_min <= 180:
            horizon = "3h"
        else:
            horizon = "no_lag"
            
        pred = predict_queue_metrics(facility_id, slot_dt, horizon=horizon)
        results.append({
            "timestamp": slot_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "time_label": slot_dt.strftime("%H:%M"),
            "waiting_time_min": pred["waiting_time_min"],
            "queue_length": pred["queue_length"],
            "is_peak": pred["is_peak"],
            "crowd_level": pred["crowd_level"],
            "counters_open": pred["counters_open"],
            "prediction_method": pred.get("prediction_method", f"model_horizon_{horizon}")
        })
        
    return results

def get_best_time_slots(
    facility_id: str,
    target_date: Optional[datetime] = None,
    top_k: int = 3
) -> List[Dict[str, Any]]:
    """Identifies the 3 best time slots today with the lowest predicted wait time."""
    if target_date is None:
        target_date = datetime.now()
        
    slots = []
    base_date = target_date.date()
    for h in range(8, 19):
        for m in [0, 30]:
            slot_dt = datetime(base_date.year, base_date.month, base_date.day, h, m, 0)
            pred = predict_queue_metrics(facility_id, slot_dt, horizon="no_lag")
            if pred["crowd_level"] != "Closed":
                slots.append({
                    "time_slot": f"{h:02d}:{m:02d} - {h if m == 0 else h+1:02d}:{(m+30)%60:02d}",
                    "start_time": f"{h:02d}:{m:02d}",
                    "waiting_time_min": pred["waiting_time_min"],
                    "queue_length": pred["queue_length"],
                    "crowd_level": pred["crowd_level"],
                    "is_peak": pred["is_peak"]
                })
                
    slots.sort(key=lambda s: s["waiting_time_min"])
    return slots[:top_k]

def get_hourly_pattern(facility_id: str) -> List[Dict[str, Any]]:
    """Returns average wait per hour for each weekday (heatmap data) based on train baseline."""
    lookup_df = load_lookup_table()
    weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    
    if not lookup_df.empty:
        sub = lookup_df[lookup_df["facility_id"] == facility_id]
    else:
        sub = pd.DataFrame()
        
    heatmap_matrix = []
    for dow_idx, day_name in enumerate(weekdays):
        for h in range(8, 20):
            if not sub.empty:
                val = sub[(sub["day_of_week"] == dow_idx) & (sub["hour"] == h)]
                if not val.empty:
                    avg_wait = round(float(val["hist_wait_mean"].values[0]), 1)
                else:
                    avg_wait = 0.0 if (dow_idx >= 5 and FACILITY_METADATA.get(facility_id, {}).get("closed_on_weekend")) else 4.0
            else:
                avg_wait = 4.0
                
            heatmap_matrix.append({
                "day_of_week": dow_idx,
                "day_name": day_name,
                "hour": h,
                "hour_label": f"{h:02d}:00",
                "avg_wait_time_min": avg_wait
            })
            
    return heatmap_matrix

if __name__ == "__main__":
    now = datetime(2026, 10, 15, 12, 30, 0)
    print("Testing multi-horizon prediction for Main Cafeteria at 12:30 PM:")
    p = predict_queue_metrics("FAC_02", now, horizon="15m")
    print("15m horizon prediction:", p)
    print("\nForecast 3 hours (multi-horizon):")
    fc = get_facility_forecast("FAC_02", now, hours=3, interval_minutes=30)
    for f in fc:
        print(f"{f['time_label']} | wait: {f['waiting_time_min']:4.1f}m | queue: {f['queue_length']:2d} | method: {f['prediction_method']}")

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

# Global cached artifacts
_WAIT_MODEL = None
_QUEUE_MODEL = None
_PEAK_MODEL = None
_FEATURE_NAMES = None
_LOOKUP_DF = None
_DATASET_CACHE = None

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

def load_ml_artifacts():
    global _WAIT_MODEL, _QUEUE_MODEL, _PEAK_MODEL, _FEATURE_NAMES, _LOOKUP_DF
    if _WAIT_MODEL is None:
        wait_path = os.path.join(MODELS_DIR, "best_wait_time_model.joblib")
        queue_path = os.path.join(MODELS_DIR, "best_queue_length_model.joblib")
        peak_path = os.path.join(MODELS_DIR, "best_peak_classifier.joblib")
        feats_path = os.path.join(MODELS_DIR, "feature_names.json")
        lookup_path = os.path.join(MODELS_DIR, "historical_hourly_lookup.csv")
        
        _WAIT_MODEL = joblib.load(wait_path)
        _QUEUE_MODEL = joblib.load(queue_path)
        _PEAK_MODEL = joblib.load(peak_path)
        
        with open(feats_path, "r") as f:
            _FEATURE_NAMES = json.load(f)
            
        if os.path.exists(lookup_path):
            _LOOKUP_DF = pd.read_csv(lookup_path)
            
    return _WAIT_MODEL, _QUEUE_MODEL, _PEAK_MODEL, _FEATURE_NAMES, _LOOKUP_DF

def get_context_for_dt(dt: datetime, fac_id: str):
    """Computes realistic contextual covariates given datetime and facility"""
    meta = FACILITY_METADATA.get(fac_id, FACILITY_METADATA["FAC_01"])
    hour = dt.hour
    minute = dt.minute
    dow = dt.weekday()
    month = dt.month
    day = dt.day
    
    is_weekend = 1 if dow >= 5 else 0
    is_holiday = 1 if (month, day) in [(5, 25), (7, 4), (9, 7), (10, 12)] else 0
    
    # Meal period
    if 8 <= hour < 10:
        meal = "Breakfast"
    elif 11 <= hour < 14:
        meal = "Lunch"
    elif 17 <= hour < 20:
        meal = "Dinner"
    else:
        meal = "Non-Meal"
        
    # Academic period estimation
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
    weather = "Sunny" # Default sunny context
    event_flag = 0
    
    # Expected counters open
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

def construct_feature_vector(fac_id: str, dt: datetime, overrides: Optional[Dict[str, Any]] = None):
    _, _, _, feature_names, lookup_df = load_ml_artifacts()
    ctx = get_context_for_dt(dt, fac_id)
    if overrides:
        ctx.update(overrides)
        
    hour = dt.hour
    minute = dt.minute
    dow = dt.weekday()
    
    # Historical baseline lookup
    avg_wait_hist = 8.0
    if lookup_df is not None:
        match = lookup_df[(lookup_df["facility_id"] == fac_id) & 
                          (lookup_df["day_of_week"] == dow) & 
                          (lookup_df["hour"] == hour)]
        if not match.empty:
            avg_wait_hist = float(match["avg_wait_same_hour_last_week"].values[0])
            
    # Approximated dynamic state based on context
    is_closed = (ctx["num_counters_open"] == 0)
    if is_closed:
        est_arrival_rate = 0.0
        est_dep_rate = 0.0
        lag1 = lag2 = lag3 = 0.0
        rolling_wait = 0.0
        rolling_arr = 0.0
    else:
        est_arrival_rate = 18.0 if (fac_id == "FAC_02" and 11 <= hour <= 14) else 12.0
        est_dep_rate = est_arrival_rate * 0.95
        lag1 = max(0.0, avg_wait_hist * 0.6)
        lag2 = max(0.0, avg_wait_hist * 0.55)
        lag3 = max(0.0, avg_wait_hist * 0.5)
        rolling_wait = avg_wait_hist
        rolling_arr = est_arrival_rate
        
    feat_dict = {
        "hour_sin": np.sin(2 * np.pi * hour / 24.0),
        "hour_cos": np.cos(2 * np.pi * hour / 24.0),
        "minute_sin": np.sin(2 * np.pi * minute / 60.0),
        "minute_cos": np.cos(2 * np.pi * minute / 60.0),
        "dow_sin": np.sin(2 * np.pi * dow / 7.0),
        "dow_cos": np.cos(2 * np.pi * dow / 7.0),
        "num_counters_open": ctx["num_counters_open"],
        "num_staff_on_duty": ctx["num_staff_on_duty"],
        "avg_service_time_min": ctx["avg_service_time_min"],
        "arrival_rate": est_arrival_rate,
        "departure_rate": est_dep_rate,
        "group_size": 2.2 if fac_id == "FAC_02" else 1.2,
        "class_schedule_density": ctx["class_schedule_density"],
        "is_weekend": ctx["is_weekend"],
        "is_holiday": ctx["is_holiday"],
        "is_exam_week": ctx["is_exam_week"],
        "event_flag": ctx["event_flag"],
        "deadline_proximity_days": ctx["deadline_proximity_days"],
        "queue_length_lag_1": lag1,
        "queue_length_lag_2": lag2,
        "queue_length_lag_3": lag3,
        "waiting_time_rolling_30min": rolling_wait,
        "arrivals_rolling_1h": rolling_arr,
        "avg_wait_same_hour_last_week": avg_wait_hist
    }
    
    # Categorical dummy columns
    row_df = pd.DataFrame([feat_dict])
    
    # Add dummy variables present in feature_names
    for col in feature_names:
        if col.startswith("facility_id_"):
            target_val = col.replace("facility_id_", "")
            row_df[col] = 1.0 if fac_id == target_val else 0.0
        elif col.startswith("facility_type_"):
            target_val = col.replace("facility_type_", "")
            row_df[col] = 1.0 if ctx["facility_type"] == target_val else 0.0
        elif col.startswith("academic_period_"):
            target_val = col.replace("academic_period_", "")
            row_df[col] = 1.0 if ctx["academic_period"] == target_val else 0.0
        elif col.startswith("weather_"):
            target_val = col.replace("weather_", "")
            row_df[col] = 1.0 if ctx["weather"] == target_val else 0.0
        elif col.startswith("meal_period_"):
            target_val = col.replace("meal_period_", "")
            row_df[col] = 1.0 if ctx["meal_period"] == target_val else 0.0
            
    # Align exact column order
    for col in feature_names:
        if col not in row_df.columns:
            row_df[col] = 0.0
            
    X_vec = row_df[feature_names]
    return X_vec, ctx

def determine_crowd_level(wait_time: float, is_peak: bool, fac_id: str) -> str:
    if wait_time < 5.0 and not is_peak:
        return "Low"
    elif wait_time < 14.0 and not is_peak:
        return "Medium"
    else:
        return "High"

def predict_queue_metrics(facility_id: str, dt: datetime, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Reusable prediction function for waiting time, queue length and peak status."""
    wait_model, queue_model, peak_model, _, _ = load_ml_artifacts()
    X_vec, ctx = construct_feature_vector(facility_id, dt, overrides)
    
    meta = FACILITY_METADATA.get(facility_id, FACILITY_METADATA["FAC_01"])
    dow = dt.weekday()
    hour = dt.hour
    is_weekend = 1 if dow >= 5 else 0
    
    # Closed check
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
            "status_message": "Facility is currently closed"
        }
        
    raw_wait = float(wait_model.predict(X_vec)[0])
    raw_queue = float(queue_model.predict(X_vec)[0])
    raw_peak = int(peak_model.predict(X_vec)[0])
    
    # Post-process bounds
    wait_time = max(0.5, round(raw_wait, 1))
    queue_len = max(0, int(round(raw_queue)))
    is_peak_bool = bool(raw_peak == 1 or wait_time >= 15.0)
    crowd_level = determine_crowd_level(wait_time, is_peak_bool, facility_id)
    
    return {
        "facility_id": facility_id,
        "facility_name": meta["name"],
        "timestamp": dt.strftime("%Y-%m-%d %H:%M:%S"),
        "waiting_time_min": wait_time,
        "queue_length": queue_len,
        "is_peak": is_peak_bool,
        "crowd_level": crowd_level,
        "counters_open": ctx["num_counters_open"],
        "status_message": f"{crowd_level} crowd with ~{wait_time} min wait"
    }

def get_facility_forecast(facility_id: str, start_dt: Optional[datetime] = None, hours: int = 3, interval_minutes: int = 15) -> List[Dict[str, Any]]:
    """Generates predicted wait time and queue length at intervals."""
    if start_dt is None:
        start_dt = datetime.now()
        
    results = []
    total_steps = int((hours * 60) / interval_minutes)
    
    for i in range(total_steps):
        slot_dt = start_dt + timedelta(minutes=i * interval_minutes)
        pred = predict_queue_metrics(facility_id, slot_dt)
        results.append({
            "timestamp": slot_dt.strftime("%Y-%m-%d %H:%M:%S"),
            "time_label": slot_dt.strftime("%H:%M"),
            "waiting_time_min": pred["waiting_time_min"],
            "queue_length": pred["queue_length"],
            "is_peak": pred["is_peak"],
            "crowd_level": pred["crowd_level"],
            "counters_open": pred["counters_open"]
        })
    return results

def get_best_time_slots(facility_id: str, target_date: Optional[datetime] = None, top_k: int = 3) -> List[Dict[str, Any]]:
    """Identifies the 3 best time slots today with the lowest predicted wait time."""
    if target_date is None:
        target_date = datetime.now()
        
    slots = []
    # Test slots from 08:30 to 18:30 every 30 minutes
    base_date = target_date.date()
    for h in range(8, 19):
        for m in [0, 30]:
            slot_dt = datetime(base_date.year, base_date.month, base_date.day, h, m, 0)
            pred = predict_queue_metrics(facility_id, slot_dt)
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
    """Returns average wait per hour for each weekday (heatmap data)."""
    _, _, _, _, lookup_df = load_ml_artifacts()
    weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    
    if lookup_df is not None:
        sub = lookup_df[lookup_df["facility_id"] == facility_id]
    else:
        sub = pd.DataFrame()
        
    heatmap_matrix = []
    for dow_idx, day_name in enumerate(weekdays):
        for h in range(8, 20):
            if not sub.empty:
                val = sub[(sub["day_of_week"] == dow_idx) & (sub["hour"] == h)]
                if not val.empty:
                    avg_wait = round(float(val["avg_wait_same_hour_last_week"].values[0]), 1)
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
    print("Testing prediction for Main Cafeteria at 12:30 PM:")
    p = predict_queue_metrics("FAC_02", now)
    print(p)
    print("\nForecast 3 hours:")
    fc = get_facility_forecast("FAC_02", now, hours=3, interval_minutes=30)
    for f in fc:
        print(f["time_label"], f["waiting_time_min"], "min wait,", f["queue_length"], "in queue")
    print("\nBest time slots today:")
    best = get_best_time_slots("FAC_02", now)
    for b in best:
        print(b)

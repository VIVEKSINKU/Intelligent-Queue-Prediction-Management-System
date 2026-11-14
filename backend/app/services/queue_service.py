import os
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import pandas as pd
from sqlalchemy.orm import Session

from backend.app.database import SessionLocal, Base, engine
from backend.app.models.db_models import FacilityDB, QueueSnapshotDB, RecommendationDB
from ml.predict import (
    FACILITY_METADATA,
    predict_queue_metrics,
    get_facility_forecast,
    get_best_time_slots,
    get_hourly_pattern,
    load_ml_artifacts
)

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "queue_data.csv")
MODELS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "ml", "models")
PLOTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "ml", "plots")

# In-memory sensor cache (simulating edge device readings)
_SENSOR_READINGS_CACHE = {}
_TRENDS_CACHE = None

def init_db_seeds():
    """Seeds database with facilities and default recommendations if not yet created."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Check if facilities exist
        if db.query(FacilityDB).count() == 0:
            for fac_id, meta in FACILITY_METADATA.items():
                db_fac = FacilityDB(
                    facility_id=fac_id,
                    name=meta["name"],
                    facility_type=meta["type"],
                    location=meta["location"],
                    operating_hours=meta["operating_hours"],
                    default_counters=meta["default_counters"],
                    max_counters=meta["max_counters"],
                    closed_on_weekend=meta["closed_on_weekend"]
                )
                db.add(db_fac)
            db.commit()
            
        # Check recommendations
        if db.query(RecommendationDB).count() == 0:
            seeds = [
                {
                    "facility_id": "FAC_02",
                    "title": "Cafeteria Lunch Peak Advisory",
                    "tip_text": "Main Cafeteria is heavily congested between 12:15 and 13:45 (wait ~18-25 min). Visit between 11:00-11:45 or after 14:15 for under 4 min wait.",
                    "category": "Timing"
                },
                {
                    "facility_id": "FAC_02",
                    "title": "Express Food Counter Tip",
                    "tip_text": "Counter 3 (Grab-and-Go & Pre-packed Salads) moves 2.5x faster than hot buffet Counter 1 & 2 during peak meal hours.",
                    "category": "Counter Speed"
                },
                {
                    "facility_id": "FAC_01",
                    "title": "Admin Document Submission Timing",
                    "tip_text": "Admin Office experiences rush between 10:30 and 12:00. Tuesday and Thursday mornings before 10:00 have the fastest turnaround (~5 min).",
                    "category": "Timing"
                },
                {
                    "facility_id": "FAC_05",
                    "title": "Fee Deadline Queue Notice",
                    "tip_text": "Tuition deadline surge detected. Counter 4 handles card-only express payments and operates with ~6 min shorter lines.",
                    "category": "Counter Speed"
                },
                {
                    "facility_id": "FAC_04",
                    "title": "Library Group Study Reservations",
                    "tip_text": "Library front desk has zero queue between 09:00 - 11:30. Evening checkout queue peaks at 16:30 - 18:00.",
                    "category": "General Advice"
                },
                {
                    "facility_id": "FAC_03",
                    "title": "Student Services Advising",
                    "tip_text": "Student Services wait time peaks around 13:00 - 15:00. Morning drop-ins at 08:45 have immediate service availability.",
                    "category": "Timing"
                }
            ]
            for s in seeds:
                db_rec = RecommendationDB(
                    facility_id=s["facility_id"],
                    title=s["title"],
                    tip_text=s["tip_text"],
                    category=s["category"],
                    is_active=True
                )
                db.add(db_rec)
            db.commit()
    finally:
        db.close()

# =========================================================================
# SENSOR & TICKET SYSTEM INTEGRATION HOOK:
# In a real campus setup, physical devices post real-time counts:
# - Overhead stereo cameras / LiDAR sensors publish headcount at the turnstile.
# - Ticket kiosk (e.g. Qmatic/FastTrack) pushes /ticket-dispensed /ticket-completed.
# This function demonstrates how live hardware ingest seamlessly updates the queue state.
# =========================================================================
def record_realtime_sensor_event(facility_id: str, queue_count: int, counters_open: int, source: str = "CV Sensor"):
    """
    Called by external webhook or MQTT listener when real sensor captures queue changes.
    """
    _SENSOR_READINGS_CACHE[facility_id] = {
        "queue_length": queue_count,
        "counters_open": counters_open,
        "timestamp": datetime.now(),
        "source": source
    }
    db = SessionLocal()
    try:
        snapshot = QueueSnapshotDB(
            facility_id=facility_id,
            timestamp=datetime.now(),
            queue_length=queue_count,
            waiting_time_min=round(queue_count * 2.5 / max(1, counters_open), 1),
            crowd_level="High" if queue_count > 15 else ("Medium" if queue_count > 6 else "Low"),
            counters_open=counters_open,
            is_peak=queue_count > 12,
            data_source=source
        )
        db.add(snapshot)
        db.commit()
    finally:
        db.close()

def get_current_facility_status(facility_id: str, db: Session, simulated_time: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Retrieves current facility queue status.
    If physical sensor data exists in `_SENSOR_READINGS_CACHE`, it takes precedence.
    Otherwise, replays the trained ML model for the current time-of-day.
    """
    meta = FACILITY_METADATA.get(facility_id)
    if not meta:
        raise ValueError(f"Unknown facility ID: {facility_id}")
        
    now = simulated_time or datetime.now()
    
    # If edge sensor has reported within the last 2 minutes, use live hardware count
    if facility_id in _SENSOR_READINGS_CACHE:
        cache_entry = _SENSOR_READINGS_CACHE[facility_id]
        if (datetime.now() - cache_entry["timestamp"]).total_seconds() < 120:
            pred = predict_queue_metrics(facility_id, now, overrides={"num_counters_open": cache_entry["counters_open"]})
            pred["queue_length"] = cache_entry["queue_length"]
            pred["data_source"] = cache_entry["source"]
            pred["trend"] = "steady"
            return pred
            
    # Dataset replay / ML prediction based on current time
    pred = predict_queue_metrics(facility_id, now)
    
    # Check trend by looking back 15 minutes
    past_pred = predict_queue_metrics(facility_id, now - timedelta(minutes=15))
    if pred["waiting_time_min"] > past_pred["waiting_time_min"] + 1.5:
        trend = "rising"
    elif pred["waiting_time_min"] < past_pred["waiting_time_min"] - 1.5:
        trend = "falling"
    else:
        trend = "steady"
        
    return {
        "facility_id": facility_id,
        "name": meta["name"],
        "facility_type": meta["type"],
        "location": meta["location"],
        "operating_hours": meta["operating_hours"],
        "current_queue_length": pred["queue_length"],
        "estimated_wait_time_min": pred["waiting_time_min"],
        "crowd_level": pred["crowd_level"],
        "counters_open": pred["counters_open"],
        "max_counters": meta["max_counters"],
        "is_peak": pred["is_peak"],
        "trend": trend,
        "last_updated": now.strftime("%Y-%m-%d %H:%M:%S"),
        "data_source": "Historical Replay & XGBoost Inference"
    }

def get_all_facilities_status(db: Session, simulated_time: Optional[datetime] = None) -> List[Dict[str, Any]]:
    results = []
    for fac_id in FACILITY_METADATA.keys():
        status = get_current_facility_status(fac_id, db, simulated_time)
        results.append(status)
    return results

def get_peak_periods() -> List[Dict[str, Any]]:
    return [
        {
            "facility_id": "FAC_02",
            "facility_name": "Main Cafeteria",
            "period_name": "Lunch Rush Hour",
            "time_range": "12:00 - 14:00",
            "peak_days": "Monday - Friday",
            "expected_wait_min": 18.5,
            "peak_reason": "Simultaneous dismissal of core morning lectures and campus lunch demand.",
            "severity": "Critical"
        },
        {
            "facility_id": "FAC_02",
            "facility_name": "Main Cafeteria",
            "period_name": "Dinner Service",
            "time_range": "17:30 - 19:00",
            "peak_days": "Daily",
            "expected_wait_min": 12.0,
            "peak_reason": "Evening resident student dinner crowd.",
            "severity": "Moderate"
        },
        {
            "facility_id": "FAC_01",
            "facility_name": "Admin Office",
            "period_name": "Mid-Morning Document Request",
            "time_range": "10:30 - 12:00 & 14:00 - 15:30",
            "peak_days": "Monday, Wednesday, Friday",
            "expected_wait_min": 22.0,
            "peak_reason": "Degree verification, transcripts, and ID card renewals between classes.",
            "severity": "High"
        },
        {
            "facility_id": "FAC_05",
            "facility_name": "Fee Payment Counter",
            "period_name": "Tuition Installment Deadlines",
            "time_range": "10:00 - 14:30",
            "peak_days": "First 2 weeks of term & Exam week",
            "expected_wait_min": 25.0,
            "peak_reason": "High volume of in-person cashier transactions, scholarship forms, and clearance checks.",
            "severity": "Critical"
        },
        {
            "facility_id": "FAC_04",
            "facility_name": "Library Desk",
            "period_name": "Evening Study & Equipment Checkout",
            "time_range": "15:30 - 18:30",
            "peak_days": "Monday - Thursday (High in Exam Week)",
            "expected_wait_min": 10.5,
            "peak_reason": "Laptop loans, study room keys, and book reserve pickup.",
            "severity": "Moderate"
        },
        {
            "facility_id": "FAC_03",
            "facility_name": "Student Services Counter",
            "period_name": "Afternoon Academic Advising Surge",
            "time_range": "12:30 - 15:00",
            "peak_days": "Monday - Thursday",
            "expected_wait_min": 20.0,
            "peak_reason": "Course add/drop counseling, financial aid petitions, and housing queries.",
            "severity": "High"
        }
    ]

def get_recommendations_list(db: Session) -> List[Dict[str, Any]]:
    recs = db.query(RecommendationDB).filter(RecommendationDB.is_active == True).all()
    out = []
    for r in recs:
        meta = FACILITY_METADATA.get(r.facility_id, {})
        priority = "Urgent" if "heavily" in r.tip_text.lower() or "deadline" in r.tip_text.lower() else "Recommended"
        out.append({
            "id": r.id,
            "facility_id": r.facility_id,
            "facility_name": meta.get("name", r.facility_id),
            "title": r.title,
            "tip_text": r.tip_text,
            "category": r.category,
            "priority": priority
        })
    return out

def get_model_metrics_summary() -> Dict[str, Any]:
    metrics_path = os.path.join(MODELS_DIR, "metrics.json")
    feat_path = os.path.join(MODELS_DIR, "feature_importance.json")
    
    metrics_data = {}
    if os.path.exists(metrics_path):
        with open(metrics_path, "r") as f:
            metrics_data = json.load(f)
            
    top_feats = []
    if os.path.exists(feat_path):
        with open(feat_path, "r") as f:
            raw_feats = json.load(f)
            top_feats = [{"feature": k, "importance": round(v, 4)} for k, v in raw_feats[:12]]
            
    available_plots = [
        "actual_vs_predicted_wait_time.png",
        "actual_vs_predicted_queue_length.png",
        "residuals_distribution.png",
        "feature_importance.png",
        "confusion_matrix_peak.png",
        "model_comparison_bar.png"
    ]
    
    return {
        "best_models": metrics_data.get("best_models", {
            "waiting_time": "XGBoost",
            "queue_length": "Linear Regression",
            "peak_classifier": "XGBoost Classifier"
        }),
        "waiting_time_models": metrics_data.get("waiting_time", {}),
        "queue_length_models": metrics_data.get("queue_length", {}),
        "peak_classifier_models": metrics_data.get("peak_classification", {}),
        "top_feature_importance": top_feats,
        "model_trained_on": "67,160 Time-Series Replay Observations (May - Oct 2026)",
        "available_plots": available_plots
    }

def get_analytics_trends() -> Dict[str, Any]:
    global _TRENDS_CACHE
    if _TRENDS_CACHE is not None:
        return _TRENDS_CACHE
        
    if not os.path.exists(DATA_PATH):
        return {"daily_trends": [], "weekly_trends": [], "total_historical_records": 0}
        
    df = pd.read_csv(DATA_PATH)
    
    # Daily aggregation (sample last 30 days for smooth charting)
    daily_df = df.groupby("date").agg({
        "waiting_time_min": "mean",
        "queue_length": "mean",
        "record_id": "count"
    }).reset_index().rename(columns={"record_id": "total_samples"})
    
    daily_records = []
    step = max(1, len(daily_df) // 30)
    sampled_daily = daily_df.iloc[::step].tail(30)
    for _, row in sampled_daily.iterrows():
        daily_records.append({
            "date": str(row["date"]),
            "avg_waiting_time_min": round(float(row["waiting_time_min"]), 1),
            "avg_queue_length": round(float(row["queue_length"]), 1),
            "total_samples": int(row["total_samples"])
        })
        
    # Weekly aggregation by weekday (0=Mon to 6=Sun)
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekly_df = df.groupby("day_of_week").agg({
        "waiting_time_min": "mean",
        "queue_length": "mean"
    }).reset_index()
    
    weekly_records = []
    for _, row in weekly_df.iterrows():
        dow = int(row["day_of_week"])
        weekly_records.append({
            "day_name": day_names[dow],
            "day_of_week": dow,
            "avg_waiting_time_min": round(float(row["waiting_time_min"]), 1),
            "avg_queue_length": round(float(row["queue_length"]), 1)
        })
        
    _TRENDS_CACHE = {
        "daily_trends": daily_records,
        "weekly_trends": weekly_records,
        "total_historical_records": len(df)
    }
    return _TRENDS_CACHE

import os
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.schemas import (
    FacilityStatusResponse,
    ForecastResponse,
    PredictRequest,
    PredictResponse,
    BestTimeResponse,
    HourlyPatternResponse,
    PeakPeriod,
    RecommendationItem,
    AnalyticsTrendsResponse,
    ModelMetricsResponse
)
from backend.app.services.queue_service import (
    get_all_facilities_status,
    get_current_facility_status,
    get_peak_periods,
    get_recommendations_list,
    get_model_metrics_summary,
    get_analytics_trends
)
from ml.predict import (
    FACILITY_METADATA,
    predict_queue_metrics,
    get_facility_forecast,
    get_best_time_slots,
    get_hourly_pattern
)

router = APIRouter()

@router.get("/facilities", response_model=List[FacilityStatusResponse], summary="List all facilities with live status")
def list_facilities(db: Session = Depends(get_db)):
    """Returns a list of all campus facilities with real-time queue length, estimated wait, and crowd status."""
    return get_all_facilities_status(db)

@router.get("/facilities/{facility_id}/status", response_model=FacilityStatusResponse, summary="Get facility current status")
def facility_status(facility_id: str, db: Session = Depends(get_db)):
    """Returns live queue status, estimated wait time, crowd level, and active service counters for a facility."""
    if facility_id not in FACILITY_METADATA:
        raise HTTPException(status_code=404, detail=f"Facility '{facility_id}' not found. Available: {list(FACILITY_METADATA.keys())}")
    return get_current_facility_status(facility_id, db)

@router.get("/facilities/{facility_id}/forecast", response_model=ForecastResponse, summary="Get 1-3 hour queue forecast")
def facility_forecast(
    facility_id: str,
    hours: int = Query(default=3, ge=1, le=8, description="Number of hours ahead to forecast"),
    interval_minutes: int = Query(default=15, ge=5, le=60, description="Interval in minutes between forecast points")
):
    """Forecasts queue length and waiting time at regular intervals using trained ML regressors."""
    if facility_id not in FACILITY_METADATA:
        raise HTTPException(status_code=404, detail=f"Facility '{facility_id}' not found.")
    
    meta = FACILITY_METADATA[facility_id]
    now = datetime.now()
    intervals = get_facility_forecast(facility_id, start_dt=now, hours=hours, interval_minutes=interval_minutes)
    
    return ForecastResponse(
        facility_id=facility_id,
        facility_name=meta["name"],
        forecast_hours=hours,
        generated_at=now.strftime("%Y-%m-%d %H:%M:%S"),
        intervals=intervals
    )

@router.post("/predict", response_model=PredictResponse, summary="Custom point prediction for date & time")
def custom_predict(request: PredictRequest):
    """Predicts wait time, queue length, and peak status for a specific facility at any custom date/time."""
    if request.facility_id not in FACILITY_METADATA:
        raise HTTPException(status_code=404, detail=f"Facility '{request.facility_id}' not found.")
        
    try:
        # Parse datetime string (ISO format or common format)
        cleaned_str = request.datetime_str.replace("Z", "").replace("T", " ")
        if len(cleaned_str) == 16: # "YYYY-MM-DD HH:MM"
            cleaned_str += ":00"
        dt = datetime.fromisoformat(cleaned_str)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid datetime format '{request.datetime_str}'. Use ISO format (e.g., 2026-10-15T12:30:00). Error: {str(e)}")
        
    overrides = {}
    if request.counters_open is not None:
        overrides["num_counters_open"] = request.counters_open
        
    meta = FACILITY_METADATA[request.facility_id]
    result = predict_queue_metrics(request.facility_id, dt, overrides)
    
    explanation = (
        f"At {dt.strftime('%A %I:%M %p')}, {meta['name']} is expected to have "
        f"{result['crowd_level'].lower()} crowd traffic (~{result['queue_length']} people in queue) "
        f"with an anticipated wait of {result['waiting_time_min']} minutes across {result['counters_open']} active counters."
    )
    
    return PredictResponse(
        facility_id=request.facility_id,
        facility_name=meta["name"],
        requested_datetime=dt.strftime("%Y-%m-%d %H:%M:%S"),
        predicted_wait_time_min=result["waiting_time_min"],
        predicted_queue_length=result["queue_length"],
        is_peak=result["is_peak"],
        crowd_level=result["crowd_level"],
        counters_open=result["counters_open"],
        explanation=explanation
    )

@router.get("/facilities/{facility_id}/best-time", response_model=BestTimeResponse, summary="Find best 3 time slots today")
def best_time(facility_id: str):
    """Finds the top 3 optimal time slots today with minimal waiting time."""
    if facility_id not in FACILITY_METADATA:
        raise HTTPException(status_code=404, detail=f"Facility '{facility_id}' not found.")
        
    meta = FACILITY_METADATA[facility_id]
    now = datetime.now()
    best_slots = get_best_time_slots(facility_id, target_date=now, top_k=3)
    
    return BestTimeResponse(
        facility_id=facility_id,
        facility_name=meta["name"],
        target_date=now.strftime("%Y-%m-%d (%A)"),
        best_slots=best_slots
    )

@router.get("/facilities/{facility_id}/hourly-pattern", response_model=HourlyPatternResponse, summary="Hourly heatmap matrix")
def hourly_pattern(facility_id: str):
    """Provides average wait time across each hour of each day of week for heatmap visualization."""
    if facility_id not in FACILITY_METADATA:
        raise HTTPException(status_code=404, detail=f"Facility '{facility_id}' not found.")
        
    meta = FACILITY_METADATA[facility_id]
    patterns = get_hourly_pattern(facility_id)
    return HourlyPatternResponse(
        facility_id=facility_id,
        facility_name=meta["name"],
        patterns=patterns
    )

@router.get("/peaks", response_model=List[PeakPeriod], summary="Identified peak periods across facilities")
def peak_periods():
    """Lists recurring peak crowd periods and bottlenecks detected for each campus facility."""
    return get_peak_periods()

@router.get("/recommendations", response_model=List[RecommendationItem], summary="Student tips and queue advice")
def student_recommendations(db: Session = Depends(get_db)):
    """Returns dynamic tips, fastest counter suggestions, and visit advice for students."""
    return get_recommendations_list(db)

@router.get("/analytics/trends", response_model=AnalyticsTrendsResponse, summary="Historical daily and weekly trends")
def analytics_trends():
    """Aggregates multi-month historical trends including day-of-week averages and daily volume."""
    return get_analytics_trends()

@router.get("/model/metrics", response_model=ModelMetricsResponse, summary="ML model performance metrics and importances")
def model_metrics():
    """Returns MAE, RMSE, R2, accuracy, precision, recall, F1, and feature importance scores for all models."""
    return get_model_metrics_summary()

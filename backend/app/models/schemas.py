from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class FacilityBase(BaseModel):
    facility_id: str
    name: str
    facility_type: str
    location: str
    operating_hours: str
    default_counters: int
    max_counters: int

class FacilityStatusResponse(BaseModel):
    facility_id: str
    name: str
    facility_type: str
    location: str
    operating_hours: str
    current_queue_length: int
    estimated_wait_time_min: float
    crowd_level: str # "Low", "Medium", "High", "Closed"
    counters_open: int
    max_counters: int
    is_peak: bool
    trend: str # "rising", "falling", "steady"
    last_updated: str
    data_source: str

class ForecastItem(BaseModel):
    timestamp: str
    time_label: str
    waiting_time_min: float
    queue_length: int
    crowd_level: str
    counters_open: int
    is_peak: bool
    prediction_method: Optional[str] = "model_horizon_15m"

class ForecastResponse(BaseModel):
    facility_id: str
    facility_name: str
    forecast_hours: int
    generated_at: str
    intervals: List[ForecastItem]

class PredictRequest(BaseModel):
    facility_id: str = Field(..., example="FAC_02")
    datetime_str: str = Field(..., alias="datetime", example="2026-10-15T12:30:00")
    counters_open: Optional[int] = Field(None, example=4)

class PredictResponse(BaseModel):
    facility_id: str
    facility_name: str
    requested_datetime: str
    predicted_wait_time_min: float
    predicted_queue_length: int
    is_peak: bool
    crowd_level: str
    counters_open: int
    explanation: str
    prediction_method: Optional[str] = "model_calendar_nolag"

class BestTimeSlot(BaseModel):
    time_slot: str
    start_time: str
    waiting_time_min: float
    queue_length: int
    crowd_level: str
    is_peak: bool

class BestTimeResponse(BaseModel):
    facility_id: str
    facility_name: str
    target_date: str
    best_slots: List[BestTimeSlot]

class HourlyPatternItem(BaseModel):
    day_of_week: int
    day_name: str
    hour: int
    hour_label: str
    avg_wait_time_min: float

class HourlyPatternResponse(BaseModel):
    facility_id: str
    facility_name: str
    patterns: List[HourlyPatternItem]

class PeakPeriod(BaseModel):
    facility_id: str
    facility_name: str
    period_name: str # e.g. "Lunch Rush", "Exam Peak", "Fee Rush"
    time_range: str
    peak_days: str
    expected_wait_min: float
    peak_reason: str
    severity: str # "Moderate", "High", "Critical"

class RecommendationItem(BaseModel):
    id: int
    facility_id: str
    facility_name: str
    title: str
    tip_text: str
    category: str # "Timing", "Counter Speed", "General Advice"
    priority: str # "Info", "Recommended", "Urgent"

class ModelMetricsResponse(BaseModel):
    best_models: Dict[str, str]
    waiting_time_models: Dict[str, Dict[str, Any]]
    queue_length_models: Dict[str, Dict[str, Any]]
    peak_classifier_models: Dict[str, Dict[str, Any]]
    top_feature_importance: List[Dict[str, Any]]
    model_trained_on: str
    available_plots: List[str]
    baselines: Optional[Dict[str, Any]] = None
    horizons: Optional[Dict[str, Any]] = None
    walk_forward_cv: Optional[Dict[str, Any]] = None
    per_facility: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None

class DailyTrendItem(BaseModel):
    date: str
    avg_waiting_time_min: float
    avg_queue_length: float
    total_samples: int

class WeeklyTrendItem(BaseModel):
    day_name: str
    day_of_week: int
    avg_waiting_time_min: float
    avg_queue_length: float

class AnalyticsTrendsResponse(BaseModel):
    daily_trends: List[DailyTrendItem]
    weekly_trends: List[WeeklyTrendItem]
    total_historical_records: int

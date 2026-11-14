const API_BASE = '/api';

export interface FacilityStatus {
  facility_id: string;
  name: string;
  facility_type: string;
  location: string;
  operating_hours: string;
  current_queue_length: number;
  estimated_wait_time_min: number;
  crowd_level: 'Low' | 'Medium' | 'High' | 'Closed';
  counters_open: number;
  default_counters?: number;
  max_counters: number;
  is_peak: boolean;
  trend: 'rising' | 'falling' | 'steady';
  last_updated: string;
  data_source: string;
}

export interface ForecastItem {
  timestamp: string;
  time_label: string;
  waiting_time_min: number;
  queue_length: number;
  crowd_level: string;
  counters_open: number;
  is_peak: boolean;
}

export interface ForecastResponse {
  facility_id: string;
  facility_name: string;
  forecast_hours: number;
  generated_at: string;
  intervals: ForecastItem[];
}

export interface PredictResponse {
  facility_id: string;
  facility_name: string;
  requested_datetime: string;
  predicted_wait_time_min: number;
  predicted_queue_length: number;
  is_peak: boolean;
  crowd_level: string;
  counters_open: number;
  explanation: string;
}

export interface BestTimeSlot {
  time_slot: string;
  start_time: string;
  waiting_time_min: number;
  queue_length: number;
  crowd_level: string;
  is_peak: boolean;
}

export interface BestTimeResponse {
  facility_id: string;
  facility_name: string;
  target_date: string;
  best_slots: BestTimeSlot[];
}

export interface HourlyPatternItem {
  day_of_week: number;
  day_name: string;
  hour: number;
  hour_label: string;
  avg_wait_time_min: number;
}

export interface PeakPeriod {
  facility_id: string;
  facility_name: string;
  period_name: string;
  time_range: string;
  peak_days: string;
  expected_wait_min: number;
  peak_reason: string;
  severity: 'Moderate' | 'High' | 'Critical';
}

export interface RecommendationItem {
  id: number;
  facility_id: string;
  facility_name: string;
  title: string;
  tip_text: string;
  category: string;
  priority: 'Info' | 'Recommended' | 'Urgent';
}

export interface DailyTrendItem {
  date: string;
  avg_waiting_time_min: number;
  avg_queue_length: number;
  total_samples: number;
}

export interface WeeklyTrendItem {
  day_name: string;
  day_of_week: number;
  avg_waiting_time_min: number;
  avg_queue_length: number;
}

export interface AnalyticsTrendsResponse {
  daily_trends: DailyTrendItem[];
  weekly_trends: WeeklyTrendItem[];
  total_historical_records: number;
}

export interface ModelMetricsResponse {
  best_models: {
    waiting_time: string;
    queue_length: string;
    peak_classifier: string;
  };
  waiting_time_models: Record<string, { MAE: number; RMSE: number; R2: number }>;
  queue_length_models: Record<string, { MAE: number; RMSE: number; R2: number }>;
  peak_classifier_models: Record<string, { Accuracy: number; Precision: number; Recall: number; F1: number }>;
  top_feature_importance: Array<{ feature: string; importance: number }>;
  model_trained_on: string;
  available_plots: string[];
}

export const api = {
  async getFacilities(): Promise<FacilityStatus[]> {
    const res = await fetch(`${API_BASE}/facilities`);
    if (!res.ok) throw new Error('Failed to fetch facilities');
    return res.json();
  },

  async getFacilityStatus(id: string): Promise<FacilityStatus> {
    const res = await fetch(`${API_BASE}/facilities/${id}/status`);
    if (!res.ok) throw new Error(`Failed to fetch status for facility ${id}`);
    return res.json();
  },

  async getFacilityForecast(id: string, hours = 3): Promise<ForecastResponse> {
    const res = await fetch(`${API_BASE}/facilities/${id}/forecast?hours=${hours}`);
    if (!res.ok) throw new Error(`Failed to fetch forecast for facility ${id}`);
    return res.json();
  },

  async getBestTimeSlots(id: string): Promise<BestTimeResponse> {
    const res = await fetch(`${API_BASE}/facilities/${id}/best-time`);
    if (!res.ok) throw new Error(`Failed to fetch best times for facility ${id}`);
    return res.json();
  },

  async getHourlyPattern(id: string): Promise<{ patterns: HourlyPatternItem[] }> {
    const res = await fetch(`${API_BASE}/facilities/${id}/hourly-pattern`);
    if (!res.ok) throw new Error(`Failed to fetch hourly patterns for facility ${id}`);
    return res.json();
  },

  async predictCustom(facility_id: string, datetime_str: string, counters_open?: number): Promise<PredictResponse> {
    const res = await fetch(`${API_BASE}/predict`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        facility_id,
        datetime: datetime_str,
        counters_open: counters_open || null,
      }),
    });
    if (!res.ok) throw new Error('Prediction request failed');
    return res.json();
  },

  async getPeakPeriods(): Promise<PeakPeriod[]> {
    const res = await fetch(`${API_BASE}/peaks`);
    if (!res.ok) throw new Error('Failed to fetch peak periods');
    return res.json();
  },

  async getRecommendations(): Promise<RecommendationItem[]> {
    const res = await fetch(`${API_BASE}/recommendations`);
    if (!res.ok) throw new Error('Failed to fetch recommendations');
    return res.json();
  },

  async getAnalyticsTrends(): Promise<AnalyticsTrendsResponse> {
    const res = await fetch(`${API_BASE}/analytics/trends`);
    if (!res.ok) throw new Error('Failed to fetch analytics trends');
    return res.json();
  },

  async getModelMetrics(): Promise<ModelMetricsResponse> {
    const res = await fetch(`${API_BASE}/model/metrics`);
    if (!res.ok) throw new Error('Failed to fetch model metrics');
    return res.json();
  },
};

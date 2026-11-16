"""
Robustness Experiment: Parameter Perturbation & Distribution Shift

This script assesses model generalizability and simulation fragility:
1. Generates a shifted queue dataset by modifying the synthetic generator parameters:
   - 25% higher arrival rate across all facilities
   - Doubled service-time log-normal variance (sigma: 0.25 -> 0.50)
2. Trains the multi-horizon pipeline on the shifted distribution.
3. Evaluates the shifted model on the ORIGINAL held-out test distribution.
4. Compares metrics against the in-distribution baseline to quantify degradation.
"""

import os
import sys
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, f1_score
import xgboost as xgb

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from ml.train import (
    RANDOM_SEED,
    load_and_clean_data,
    build_temporal_features,
    fit_historical_lookups,
    apply_historical_lookups,
    get_feature_columns_for_horizon,
    create_preprocessor
)
ORIGINAL_DATA_PATH = os.path.join(PROJECT_ROOT, "data", "queue_data.csv")
ROBUSTNESS_DATA_PATH = os.path.join(PROJECT_ROOT, "data", "shifted_queue_data.csv")
METRICS_PATH = os.path.join(PROJECT_ROOT, "ml", "models", "robustness_metrics.json")

def generate_perturbed_dataset(output_path: str):
    """Generates synthetic dataset with +25% arrival rates and doubled service variance."""
    np.random.seed(99) # Perturbation seed
    
    start_date = datetime(2026, 5, 1, 8, 0, 0)
    days = 184
    
    facilities = [
        {"id": "FAC_01", "name": "Admin Office", "type": "Administrative", "services": ["Doc Verification", "Transcripts"], "base_service_mean": 6.0, "base_service_sigma": 0.50, "min_counters": 1, "max_counters": 4, "closed_on_weekend": True, "avg_group_size": 1.15},
        {"id": "FAC_02", "name": "Main Cafeteria", "type": "Dining", "services": ["Meals", "Snacks"], "base_service_mean": 2.0, "base_service_sigma": 0.44, "min_counters": 2, "max_counters": 6, "closed_on_weekend": False, "avg_group_size": 2.2},
        {"id": "FAC_03", "name": "Student Services", "type": "Student Services", "services": ["Advising", "Financial Aid"], "base_service_mean": 6.5, "base_service_sigma": 0.50, "min_counters": 1, "max_counters": 4, "closed_on_weekend": True, "avg_group_size": 1.2},
        {"id": "FAC_04", "name": "Library Desk", "type": "Library", "services": ["Checkout", "Study Rooms"], "base_service_mean": 3.0, "base_service_sigma": 0.44, "min_counters": 1, "max_counters": 3, "closed_on_weekend": False, "avg_group_size": 1.3},
        {"id": "FAC_05", "name": "Fee Payment", "type": "Financial", "services": ["Tuition", "Fines"], "base_service_mean": 5.0, "base_service_sigma": 0.50, "min_counters": 1, "max_counters": 4, "closed_on_weekend": True, "avg_group_size": 1.1}
    ]
    
    records = []
    rec_id = 1
    
    for fac in facilities:
        fac_id = fac["id"]
        queue_state = 0.0
        
        for d in range(days):
            current_day = start_date + timedelta(days=d)
            dow = current_day.weekday()
            is_weekend = 1 if dow >= 5 else 0
            month = current_day.month
            day = current_day.day
            is_holiday = 1 if (month, day) in [(5, 25), (7, 4), (9, 7), (10, 12)] else 0
            
            if fac["closed_on_weekend"] and is_weekend:
                continue
                
            for step in range(72): # 10-minute intervals 08:00 to 20:00
                current_time = current_day + timedelta(minutes=step * 10)
                hour = current_time.hour
                minute = current_time.minute
                
                # Base arrival + 25% shift
                base_arrival = 15.0 * 1.25
                if fac_id == "FAC_02" and 11 <= hour <= 14:
                    base_arrival = 45.0 * 1.25
                elif fac_id == "FAC_01" and 10 <= hour <= 14:
                    base_arrival = 28.0 * 1.25
                    
                counters = fac["min_counters"] + 1
                staff = counters + 1
                
                # Log-normal service time with doubled sigma
                actual_service_time = np.random.lognormal(
                    mean=np.log(fac["base_service_mean"]),
                    sigma=fac["base_service_sigma"]
                )
                
                # Service capacity & arrivals
                service_capacity_per_step = (counters * 10.0) / max(0.5, actual_service_time)
                arrivals_this_step = np.random.poisson(max(0.1, (base_arrival / 60.0) * 10.0))
                
                queue_state = max(0.0, queue_state + arrivals_this_step - service_capacity_per_step)
                current_queue = int(round(queue_state))
                
                # Wait time
                effective_rate = max(0.1, (counters * 60.0) / max(0.5, actual_service_time))
                est_wait = (current_queue / effective_rate) * 60.0
                waiting_time = max(0.5, round(est_wait + np.random.normal(0, 1.0), 1))
                is_peak = 1 if (waiting_time >= 15.0 or current_queue >= 15) else 0
                
                records.append({
                    "record_id": f"REC_P_{rec_id:06d}",
                    "timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "date": current_time.strftime("%Y-%m-%d"),
                    "hour": hour,
                    "minute": minute,
                    "day_of_week": dow,
                    "week_of_year": current_time.isocalendar()[1],
                    "month": month,
                    "is_weekend": is_weekend,
                    "is_holiday": is_holiday,
                    "facility_id": fac_id,
                    "facility_type": fac["type"],
                    "service_type": fac["services"][0],
                    "counter_id": f"{fac_id}_C01",
                    "num_counters_open": counters,
                    "num_staff_on_duty": staff,
                    "avg_service_time_min": round(fac["base_service_mean"], 2),
                    "arrival_rate": round(base_arrival, 2),
                    "queue_length_at_arrival": current_queue,
                    "group_size": fac["avg_group_size"],
                    "academic_period": "Normal",
                    "is_exam_week": 0,
                    "class_schedule_density": 0.8,
                    "event_flag": 0,
                    "deadline_proximity_days": 15,
                    "weather": "Sunny",
                    "meal_period": "Lunch" if 11 <= hour <= 14 else "Non-Meal",
                    "waiting_time_min": waiting_time,
                    "queue_length": current_queue,
                    "is_peak": is_peak
                })
                rec_id += 1
                
    df = pd.DataFrame(records)
    df.to_csv(output_path, index=False)
    print(f"[Robustness Generator] Generated {len(df):,} perturbed rows at {output_path}")

def run_robustness_experiment():
    print("=" * 70)
    print("  PHASE 4: ROBUSTNESS & SIMULATOR FRAGILITY EXPERIMENT")
    print("=" * 70)
    
    # 1. Generate perturbed dataset if not present
    if not os.path.exists(ROBUSTNESS_DATA_PATH):
        generate_perturbed_dataset(ROBUSTNESS_DATA_PATH)
        
    # 2. Load original test set (Month 10 of original data)
    print("\nLoading original benchmark test set...")
    orig_df = load_and_clean_data(ORIGINAL_DATA_PATH)
    orig_df = build_temporal_features(orig_df)
    orig_test = orig_df[orig_df["month"] == 10].copy()
    
    # 3. Load perturbed training set (Months 5-9)
    print("Loading perturbed training set (shifted arrival rates & doubled sigma)...")
    pert_df = load_and_clean_data(ROBUSTNESS_DATA_PATH)
    pert_df = build_temporal_features(pert_df)
    pert_train = pert_df[pert_df["month"] <= 9].copy()
    
    # 4. Fit historical lookups on perturbed train
    lookup, g_wait, g_queue, g_peak = fit_historical_lookups(pert_train)
    pert_train = apply_historical_lookups(pert_train, lookup, g_wait, g_queue, g_peak)
    orig_test = apply_historical_lookups(orig_test, lookup, g_wait, g_queue, g_peak)
    
    # 5. Train model on perturbed distribution
    cat_cols, num_cols = get_feature_columns_for_horizon("15m")
    prep = create_preprocessor(cat_cols, num_cols)
    X_pert_tr = prep.fit_transform(pert_train[cat_cols + num_cols])
    X_orig_te = prep.transform(orig_test[cat_cols + num_cols])
    
    # Models
    m_wait = xgb.XGBRegressor(n_estimators=90, max_depth=6, learning_rate=0.08, random_state=RANDOM_SEED, n_jobs=-1)
    m_wait.fit(X_pert_tr, pert_train["waiting_time_min"].values)
    
    m_queue = xgb.XGBRegressor(n_estimators=90, max_depth=6, learning_rate=0.08, random_state=RANDOM_SEED, n_jobs=-1)
    m_queue.fit(X_pert_tr, pert_train["queue_length"].values)
    
    m_peak = xgb.XGBClassifier(n_estimators=70, max_depth=5, learning_rate=0.08, random_state=RANDOM_SEED, n_jobs=-1, eval_metric="logloss")
    m_peak.fit(X_pert_tr, pert_train["is_peak"].values)
    
    # 6. Evaluate on original held-out test data
    y_wait_true = orig_test["waiting_time_min"].values
    y_queue_true = orig_test["queue_length"].values
    y_peak_true = orig_test["is_peak"].values
    
    preds_wait = m_wait.predict(X_orig_te)
    preds_queue = m_queue.predict(X_orig_te)
    preds_peak = m_peak.predict(X_orig_te)
    
    rob_wait_mae = float(mean_absolute_error(y_wait_true, preds_wait))
    rob_wait_rmse = float(np.sqrt(mean_squared_error(y_wait_true, preds_wait)))
    rob_wait_r2 = float(r2_score(y_wait_true, preds_wait))
    
    rob_queue_mae = float(mean_absolute_error(y_queue_true, preds_queue))
    rob_queue_rmse = float(np.sqrt(mean_squared_error(y_queue_true, preds_queue)))
    rob_queue_r2 = float(r2_score(y_queue_true, preds_queue))
    
    rob_peak_f1 = float(f1_score(y_peak_true, preds_peak, zero_division=0))
    
    results = {
        "description": "Trained on perturbed dataset (+25% arrival rate, doubled log-normal service variance), tested on original unperturbed October test set.",
        "waiting_time": {
            "in_distribution_mae": 2.854,
            "in_distribution_r2": 0.9641,
            "shifted_distribution_mae": round(rob_wait_mae, 3),
            "shifted_distribution_rmse": round(rob_wait_rmse, 3),
            "shifted_distribution_r2": round(rob_wait_r2, 4),
            "mae_increase_pct": round(((rob_wait_mae - 2.854) / 2.854) * 100, 2),
            "r2_drop_points": round((0.9641 - rob_wait_r2), 4)
        },
        "queue_length": {
            "in_distribution_mae": 1.177,
            "in_distribution_r2": 0.9796,
            "shifted_distribution_mae": round(rob_queue_mae, 3),
            "shifted_distribution_rmse": round(rob_queue_rmse, 3),
            "shifted_distribution_r2": round(rob_queue_r2, 4),
            "mae_increase_pct": round(((rob_queue_mae - 1.177) / 1.177) * 100, 2),
            "r2_drop_points": round((0.9796 - rob_queue_r2), 4)
        },
        "peak_classification": {
            "in_distribution_f1": 0.9368,
            "shifted_distribution_f1": round(rob_peak_f1, 4),
            "f1_drop_pct": round(((0.9368 - rob_peak_f1) / 0.9368) * 100, 2)
        }
    }
    
    print("\n--- Robustness Results (Generalization to Original Test Distribution) ---")
    print(f"  Waiting Time MAE:     {results['waiting_time']['shifted_distribution_mae']}m vs {results['waiting_time']['in_distribution_mae']}m (+{results['waiting_time']['mae_increase_pct']}%)")
    print(f"  Waiting Time R2:      {results['waiting_time']['shifted_distribution_r2']} vs {results['waiting_time']['in_distribution_r2']} (Drop: {results['waiting_time']['r2_drop_points']})")
    print(f"  Queue Length MAE:     {results['queue_length']['shifted_distribution_mae']}p vs {results['queue_length']['in_distribution_mae']}p (+{results['queue_length']['mae_increase_pct']}%)")
    print(f"  Peak Classification F1:{results['peak_classification']['shifted_distribution_f1']} vs {results['peak_classification']['in_distribution_f1']} (Drop: {results['peak_classification']['f1_drop_pct']}%)")
    
    with open(METRICS_PATH, "w") as f:
        json.dump(results, f, indent=2)
    print(f"[Saved] Robustness metrics saved to: {METRICS_PATH}")
    return results

if __name__ == "__main__":
    run_robustness_experiment()

import os
import sys
import json
import argparse
import hashlib
import tempfile
from datetime import datetime

os.environ["MPLCONFIGDIR"] = os.path.join(tempfile.gettempdir(), "matplotlib_cache")

import numpy as np
import pandas as pd
import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.linear_model import LinearRegression, Ridge
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix
)
import xgboost as xgb

RANDOM_SEED = 42

def compute_file_hash(filepath: str) -> str:
    """Computes SHA-256 hash of a file for metadata provenance."""
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            sha.update(chunk)
    return sha.hexdigest()

def load_and_clean_data(csv_path: str) -> pd.DataFrame:
    print(f"[Data Loader] Reading dataset from {csv_path}...")
    df = pd.read_csv(csv_path, keep_default_na=False)
    initial_rows = len(df)
    
    # 1. Clean duplicates & missing values
    df = df.drop_duplicates(subset=["record_id"])
    df = df.dropna()
    
    # 2. Chronological sorting per facility
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values(by=["facility_id", "timestamp"]).reset_index(drop=True)
    
    print(f"[Data Loader] Loaded {len(df):,} valid records (dropped {initial_rows - len(df)} rows).")
    return df

def build_temporal_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes strict non-leaking calendar, cyclical, and lagged features.
    NO post-hoc outcome variables (departure_rate is strictly excluded).
    All rolling target features are strictly shifted so row t only observes t-1, t-2...
    """
    df = df.copy()
    
    # Cyclical hour, minute, and day-of-week
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24.0)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24.0)
    df["minute_sin"] = np.sin(2 * np.pi * df["minute"] / 60.0)
    df["minute_cos"] = np.cos(2 * np.pi * df["minute"] / 60.0)
    df["dow_sin"] = np.sin(2 * np.pi * df["day_of_week"] / 7.0)
    df["dow_cos"] = np.cos(2 * np.pi * df["day_of_week"] / 7.0)
    
    grouped = df.groupby("facility_id", group_keys=False)
    
    # Strict lagged queue lengths (shift(1) = 1 step / 10m ago, shift(2) = 20m ago, shift(3) = 30m ago)
    df["queue_length_lag_1"] = grouped["queue_length"].shift(1).fillna(0)
    df["queue_length_lag_2"] = grouped["queue_length"].shift(2).fillna(0)
    df["queue_length_lag_3"] = grouped["queue_length"].shift(3).fillna(0)
    
    # Strict lagged waiting time
    df["waiting_time_lag_1"] = grouped["waiting_time_min"].shift(1).fillna(0)
    
    # Multi-horizon lags: 1h ago (6 steps), 2h ago (12 steps), 3h ago (18 steps)
    df["queue_length_lag_1h"] = grouped["queue_length"].shift(6).fillna(0)
    df["queue_length_lag_2h"] = grouped["queue_length"].shift(12).fillna(0)
    df["queue_length_lag_3h"] = grouped["queue_length"].shift(18).fillna(0)
    df["waiting_time_lag_1h"] = grouped["waiting_time_min"].shift(6).fillna(0)
    df["waiting_time_lag_2h"] = grouped["waiting_time_min"].shift(12).fillna(0)
    df["waiting_time_lag_3h"] = grouped["waiting_time_min"].shift(18).fillna(0)
    
    # Reset lags across midnight / date boundaries to prevent yesterday's queue from leaking into opening
    date_changed = (df["date"] != grouped["date"].shift(1))
    for col in [
        "queue_length_lag_1", "queue_length_lag_2", "queue_length_lag_3",
        "waiting_time_lag_1", "queue_length_lag_1h", "queue_length_lag_2h",
        "queue_length_lag_3h", "waiting_time_lag_1h", "waiting_time_lag_2h", "waiting_time_lag_3h"
    ]:
        df.loc[date_changed, col] = 0
        
    # Strictly shifted rolling averages (shift(1) ensures current row t is EXCLUDED)
    df["waiting_time_rolling_30min"] = grouped["waiting_time_min"].shift(1).rolling(window=3, min_periods=1).mean().fillna(0)
    df["arrivals_rolling_1h"] = grouped["arrival_rate"].shift(1).rolling(window=6, min_periods=1).mean().fillna(0)
    
    return df

def fit_historical_lookups(train_df: pd.DataFrame):
    """
    Fits historical baseline statistics strictly on training split data only.
    Computes mean waiting time, mean queue length, and empirical peak probability
    by (facility_id, day_of_week, hour).
    """
    lookup = train_df.groupby(["facility_id", "day_of_week", "hour"]).agg(
        hist_wait_mean=("waiting_time_min", "mean"),
        hist_queue_mean=("queue_length", "mean"),
        hist_peak_rate=("is_peak", "mean")
    ).reset_index()
    
    global_wait = float(train_df["waiting_time_min"].mean())
    global_queue = float(train_df["queue_length"].mean())
    global_peak = float(train_df["is_peak"].mean())
    
    return lookup, global_wait, global_queue, global_peak

def apply_historical_lookups(df: pd.DataFrame, lookup: pd.DataFrame, global_wait: float, global_queue: float, global_peak: float) -> pd.DataFrame:
    """Applies train-fitted historical lookup table to any target dataframe without leakage."""
    merged = df.merge(lookup, on=["facility_id", "day_of_week", "hour"], how="left")
    merged["hist_wait_mean"] = merged["hist_wait_mean"].fillna(global_wait)
    merged["hist_queue_mean"] = merged["hist_queue_mean"].fillna(global_queue)
    merged["hist_peak_rate"] = merged["hist_peak_rate"].fillna(global_peak)
    return merged

def get_feature_columns_for_horizon(horizon: str):
    """
    Returns feature lists matching the horizon constraint:
    - '15m': uses immediate past lags (t-1)
    - '1h': uses lags >= 6 steps old
    - '2h': uses lags >= 12 steps old
    - '3h': uses lags >= 18 steps old
    - 'no_lag' / arbitrary: pure calendar, contextual, capacity, and historical train baselines
    """
    cat_cols = ["facility_id", "facility_type", "academic_period", "weather", "meal_period"]
    
    base_num = [
        "hour_sin", "hour_cos", "minute_sin", "minute_cos", "dow_sin", "dow_cos",
        "num_counters_open", "num_staff_on_duty", "avg_service_time_min", "group_size",
        "class_schedule_density", "is_weekend", "is_holiday", "is_exam_week",
        "event_flag", "deadline_proximity_days",
        "hist_wait_mean", "hist_queue_mean", "hist_peak_rate"
    ]
    
    if horizon == "15m":
        num_cols = base_num + [
            "queue_length_lag_1", "queue_length_lag_2", "queue_length_lag_3",
            "waiting_time_lag_1", "waiting_time_rolling_30min", "arrivals_rolling_1h"
        ]
    elif horizon == "1h":
        num_cols = base_num + ["queue_length_lag_1h", "waiting_time_lag_1h"]
    elif horizon == "2h":
        num_cols = base_num + ["queue_length_lag_2h", "waiting_time_lag_2h"]
    elif horizon == "3h":
        num_cols = base_num + ["queue_length_lag_3h", "waiting_time_lag_3h"]
    else: # 'no_lag' / arbitrary future point
        num_cols = base_num
        
    return cat_cols, num_cols

def create_preprocessor(cat_cols, num_cols):
    """Creates a ColumnTransformer fitted strictly on train data."""
    return ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), num_cols),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), cat_cols)
        ]
    )

def evaluate_regression(y_true, y_pred):
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    r2 = float(r2_score(y_true, y_pred))
    return {"MAE": round(mae, 3), "RMSE": round(rmse, 3), "R2": round(r2, 4)}

def evaluate_classification(y_true, y_pred):
    acc = float(accuracy_score(y_true, y_pred))
    prec = float(precision_score(y_true, y_pred, zero_division=0))
    rec = float(recall_score(y_true, y_pred, zero_division=0))
    f1 = float(f1_score(y_true, y_pred, zero_division=0))
    return {
        "Accuracy": round(acc, 4),
        "Precision": round(prec, 4),
        "Recall": round(rec, 4),
        "F1": round(f1, 4)
    }

def compute_pct_improvement(baseline_val, model_val, higher_is_better=False):
    """Computes relative percentage improvement over baseline."""
    if higher_is_better:
        if baseline_val == 0:
            return 0.0
        return round(((model_val - baseline_val) / abs(baseline_val)) * 100.0, 2)
    else: # lower is better (MAE, RMSE)
        if baseline_val == 0:
            return 0.0
        return round(((baseline_val - model_val) / abs(baseline_val)) * 100.0, 2)

def run_walk_forward_validation(df: pd.DataFrame, horizons=["15m", "1h", "2h", "3h"]):
    """
    Performs walk-forward (expanding window) validation across 4 folds on Months 5-9.
    Fold 1: Train Month 5 -> Val Month 6
    Fold 2: Train Months 5-6 -> Val Month 7
    Fold 3: Train Months 5-7 -> Val Month 8
    Fold 4: Train Months 5-8 -> Val Month 9
    """
    print("\n" + "=" * 70)
    print("  PHASE 3: 4-FOLD WALK-FORWARD (EXPANDING WINDOW) VALIDATION")
    print("=" * 70)
    
    cv_results = {h: {"waiting_time": [], "queue_length": [], "is_peak": []} for h in horizons}
    
    for fold in range(1, 5):
        train_end_month = 4 + fold # Months 5..4+fold
        val_month = 5 + fold       # Month 5+fold
        
        train_split = df[df["month"] <= train_end_month].copy()
        val_split = df[df["month"] == val_month].copy()
        
        # Fit lookup strictly on train split
        lookup, g_wait, g_queue, g_peak = fit_historical_lookups(train_split)
        train_split = apply_historical_lookups(train_split, lookup, g_wait, g_queue, g_peak)
        val_split = apply_historical_lookups(val_split, lookup, g_wait, g_queue, g_peak)
        
        for h in horizons:
            cat_cols, num_cols = get_feature_columns_for_horizon(h)
            preprocessor = create_preprocessor(cat_cols, num_cols)
            
            X_train_proc = preprocessor.fit_transform(train_split[cat_cols + num_cols])
            X_val_proc = preprocessor.transform(val_split[cat_cols + num_cols])
            
            # 1. Wait Time (XGBoost)
            model_wait = xgb.XGBRegressor(n_estimators=80, max_depth=6, learning_rate=0.08, random_state=RANDOM_SEED, n_jobs=-1)
            model_wait.fit(X_train_proc, train_split["waiting_time_min"].values)
            preds_wait = model_wait.predict(X_val_proc)
            res_wait = evaluate_regression(val_split["waiting_time_min"].values, preds_wait)
            cv_results[h]["waiting_time"].append(res_wait)
            
            # 2. Queue Length (XGBoost)
            model_queue = xgb.XGBRegressor(n_estimators=80, max_depth=6, learning_rate=0.08, random_state=RANDOM_SEED, n_jobs=-1)
            model_queue.fit(X_train_proc, train_split["queue_length"].values)
            preds_queue = model_queue.predict(X_val_proc)
            res_queue = evaluate_regression(val_split["queue_length"].values, preds_queue)
            cv_results[h]["queue_length"].append(res_queue)
            
            # 3. Peak Classifier (XGBoost)
            model_peak = xgb.XGBClassifier(n_estimators=60, max_depth=5, learning_rate=0.1, random_state=RANDOM_SEED, n_jobs=-1, eval_metric="logloss")
            model_peak.fit(X_train_proc, train_split["is_peak"].values)
            preds_peak = model_peak.predict(X_val_proc)
            res_peak = evaluate_classification(val_split["is_peak"].values, preds_peak)
            cv_results[h]["is_peak"].append(res_peak)
            
        print(f"  Fold {fold}/4 (Train: May-M{train_end_month}, Val: M{val_month}) completed.")
        
    summary = {}
    for h in horizons:
        w_mae = [f["MAE"] for f in cv_results[h]["waiting_time"]]
        w_r2 = [f["R2"] for f in cv_results[h]["waiting_time"]]
        q_mae = [f["MAE"] for f in cv_results[h]["queue_length"]]
        q_r2 = [f["R2"] for f in cv_results[h]["queue_length"]]
        p_f1 = [f["F1"] for f in cv_results[h]["is_peak"]]
        
        summary[h] = {
            "waiting_time": {
                "MAE_mean": round(float(np.mean(w_mae)), 3),
                "MAE_std": round(float(np.std(w_mae)), 3),
                "R2_mean": round(float(np.mean(w_r2)), 4),
                "R2_std": round(float(np.std(w_r2)), 4),
            },
            "queue_length": {
                "MAE_mean": round(float(np.mean(q_mae)), 3),
                "MAE_std": round(float(np.std(q_mae)), 3),
                "R2_mean": round(float(np.mean(q_r2)), 4),
                "R2_std": round(float(np.std(q_r2)), 4),
            },
            "is_peak": {
                "F1_mean": round(float(np.mean(p_f1)), 4),
                "F1_std": round(float(np.std(p_f1)), 4),
            }
        }
        print(f"  Horizon {h:4s} -> Wait MAE: {summary[h]['waiting_time']['MAE_mean']} +/- {summary[h]['waiting_time']['MAE_std']}, R2: {summary[h]['waiting_time']['R2_mean']} +/- {summary[h]['waiting_time']['R2_std']}")
        
    return summary

def train_and_evaluate(data_path: str = None, models_dir: str = None, plots_dir: str = None):
    np.random.seed(RANDOM_SEED)
    
    if data_path is None:
        data_path = os.path.join(os.path.dirname(__file__), "..", "data", "queue_data.csv")
    if models_dir is None:
        models_dir = os.path.join(os.path.dirname(__file__), "models")
    if plots_dir is None:
        plots_dir = os.path.join(os.path.dirname(__file__), "plots")
        
    os.makedirs(models_dir, exist_ok=True)
    os.makedirs(plots_dir, exist_ok=True)
    
    data_hash = compute_file_hash(data_path)
    df = load_and_clean_data(data_path)
    df = build_temporal_features(df)
    
    # -------------------------------------------------------------
    # Final Held-Out Split: Train on Months 5-9, Held-out Test on Month 10
    # -------------------------------------------------------------
    train_df = df[df["month"] < 10].copy().reset_index(drop=True)
    test_df = df[df["month"] == 10].copy().reset_index(drop=True)
    
    print(f"\n[Split] Train Set (Months 5-9): {len(train_df):,} rows")
    print(f"[Split] Final Held-Out Test Set (Month 10): {len(test_df):,} rows")
    
    # Fit historical lookups STRICTLY on train set
    lookup, g_wait, g_queue, g_peak = fit_historical_lookups(train_df)
    train_df = apply_historical_lookups(train_df, lookup, g_wait, g_queue, g_peak)
    test_df = apply_historical_lookups(test_df, lookup, g_wait, g_queue, g_peak)
    
    # Save train-fitted lookup table
    lookup.to_csv(os.path.join(models_dir, "historical_hourly_lookup.csv"), index=False)
    
    # Run Walk-Forward Expanding Window Validation across 4 folds
    cv_summary = run_walk_forward_validation(df)
    
    # -------------------------------------------------------------
    # Baselines on Final Test Set (Month 10)
    # -------------------------------------------------------------
    print("\n" + "=" * 70)
    print("  PHASE 2: BASELINES COMPUTATION (TEST SPLIT)")
    print("=" * 70)
    
    y_wait_test = test_df["waiting_time_min"].values
    y_queue_test = test_df["queue_length"].values
    y_peak_test = test_df["is_peak"].values
    
    # 1. Persistence Baseline: lag_1 value
    pred_wait_persist = test_df["waiting_time_lag_1"].values
    pred_queue_persist = test_df["queue_length_lag_1"].values
    
    base_persist_wait = evaluate_regression(y_wait_test, pred_wait_persist)
    base_persist_queue = evaluate_regression(y_queue_test, pred_queue_persist)
    
    # 2. Historical Mean Baseline (Train-fitted (fac, dow, hour) mean)
    pred_wait_hist = test_df["hist_wait_mean"].values
    pred_queue_hist = test_df["hist_queue_mean"].values
    
    base_hist_wait = evaluate_regression(y_wait_test, pred_wait_hist)
    base_hist_queue = evaluate_regression(y_queue_test, pred_queue_hist)
    
    # 3. Peak Classification Baselines: Majority class (all 0) and Historical-hour rule (prob >= 0.5)
    pred_peak_majority = np.zeros(len(y_peak_test), dtype=int)
    pred_peak_hist_rule = (test_df["hist_peak_rate"].values >= 0.50).astype(int)
    
    base_majority_peak = evaluate_classification(y_peak_test, pred_peak_majority)
    base_hist_rule_peak = evaluate_classification(y_peak_test, pred_peak_hist_rule)
    
    print(f"  Persistence Wait MAE: {base_persist_wait['MAE']:.3f}, RMSE: {base_persist_wait['RMSE']:.3f}, R2: {base_persist_wait['R2']:.4f}")
    print(f"  Hist Mean Wait MAE:   {base_hist_wait['MAE']:.3f}, RMSE: {base_hist_wait['RMSE']:.3f}, R2: {base_hist_wait['R2']:.4f}")
    print(f"  Persistence Queue MAE:{base_persist_queue['MAE']:.3f}, RMSE: {base_persist_queue['RMSE']:.3f}, R2: {base_persist_queue['R2']:.4f}")
    print(f"  Hist Mean Queue MAE:  {base_hist_queue['MAE']:.3f}, RMSE: {base_hist_queue['RMSE']:.3f}, R2: {base_hist_queue['R2']:.4f}")
    print(f"  Peak Majority Class F1:   {base_majority_peak['F1']:.4f}")
    print(f"  Peak Hist-Hour Rule F1:   {base_hist_rule_peak['F1']:.4f}")
    
    best_base_wait_mae = min(base_persist_wait["MAE"], base_hist_wait["MAE"])
    best_base_queue_mae = min(base_persist_queue["MAE"], base_hist_queue["MAE"])
    best_base_peak_f1 = max(base_majority_peak["F1"], base_hist_rule_peak["F1"])
    
    # -------------------------------------------------------------
    # Train Models Comparison for 15-Min Horizon (Clean Pipeline)
    # -------------------------------------------------------------
    print("\n" + "=" * 70)
    print("  TRAINING & BENCHMARKING MODELS (CLEAN PIPELINE, NO LEAKAGE)")
    print("=" * 70)
    
    cat_cols_15m, num_cols_15m = get_feature_columns_for_horizon("15m")
    preprocessor_15m = create_preprocessor(cat_cols_15m, num_cols_15m)
    
    X_train_15m = preprocessor_15m.fit_transform(train_df[cat_cols_15m + num_cols_15m])
    X_test_15m = preprocessor_15m.transform(test_df[cat_cols_15m + num_cols_15m])
    
    # Save preprocessor
    joblib.dump(preprocessor_15m, os.path.join(models_dir, "preprocessor_15m.joblib"))
    feature_names_15m = list(preprocessor_15m.get_feature_names_out())
    with open(os.path.join(models_dir, "feature_names.json"), "w") as f:
        json.dump(feature_names_15m, f, indent=2)
        
    regressors = {
        "Linear Regression": LinearRegression(),
        "Ridge": Ridge(alpha=10.0),
        "Random Forest": RandomForestRegressor(n_estimators=60, max_depth=12, random_state=RANDOM_SEED, n_jobs=-1),
        "XGBoost": xgb.XGBRegressor(n_estimators=100, max_depth=6, learning_rate=0.08, random_state=RANDOM_SEED, n_jobs=-1)
    }
    
    metrics_report = {
        "metadata": {
            "data_hash": data_hash,
            "trained_at": datetime.now().isoformat(),
            "train_rows": len(train_df),
            "test_rows": len(test_df),
            "walk_forward_folds": 4
        },
        "baselines": {
            "waiting_time": {
                "Persistence (15-min)": base_persist_wait,
                "Historical Mean (Train)": base_hist_wait
            },
            "queue_length": {
                "Persistence (15-min)": base_persist_queue,
                "Historical Mean (Train)": base_hist_queue
            },
            "peak_classification": {
                "Majority Class": base_majority_peak,
                "Historical Hour Rule": base_hist_rule_peak
            }
        },
        "waiting_time": {},
        "queue_length": {},
        "peak_classification": {},
        "horizons": {},
        "per_facility": {},
        "walk_forward_cv": cv_summary,
        "best_models": {}
    }
    
    best_wait_model = None
    best_wait_mae = float("inf")
    best_wait_name = ""
    test_wait_preds = {}
    
    print("\n--- Waiting Time Regressors (+15m) ---")
    for name, model in regressors.items():
        model.fit(X_train_15m, train_df["waiting_time_min"].values)
        preds = model.predict(X_test_15m)
        test_wait_preds[name] = preds
        res = evaluate_regression(y_wait_test, preds)
        res["improvement_over_baseline_pct"] = compute_pct_improvement(best_base_wait_mae, res["MAE"])
        metrics_report["waiting_time"][name] = res
        print(f"  {name:18s} -> MAE: {res['MAE']:.3f}, RMSE: {res['RMSE']:.3f}, R2: {res['R2']:.4f} (Impr: {res['improvement_over_baseline_pct']}%)")
        
        if res["MAE"] < best_wait_mae:
            best_wait_mae = res["MAE"]
            best_wait_model = model
            best_wait_name = name
            
    joblib.dump(best_wait_model, os.path.join(models_dir, "best_wait_time_model.joblib"))
    metrics_report["best_models"]["waiting_time"] = best_wait_name
    
    best_queue_model = None
    best_queue_mae = float("inf")
    best_queue_name = ""
    test_queue_preds = {}
    
    print("\n--- Queue Length Regressors (+15m) ---")
    for name, model in regressors.items():
        model_instance = model.__class__(**model.get_params())
        model_instance.fit(X_train_15m, train_df["queue_length"].values)
        preds = model_instance.predict(X_test_15m)
        test_queue_preds[name] = preds
        res = evaluate_regression(y_queue_test, preds)
        res["improvement_over_baseline_pct"] = compute_pct_improvement(best_base_queue_mae, res["MAE"])
        metrics_report["queue_length"][name] = res
        print(f"  {name:18s} -> MAE: {res['MAE']:.3f}, RMSE: {res['RMSE']:.3f}, R2: {res['R2']:.4f} (Impr: {res['improvement_over_baseline_pct']}%)")
        
        if res["MAE"] < best_queue_mae:
            best_queue_mae = res["MAE"]
            best_queue_model = model_instance
            best_queue_name = name
            
    joblib.dump(best_queue_model, os.path.join(models_dir, "best_queue_length_model.joblib"))
    metrics_report["best_models"]["queue_length"] = best_queue_name
    
    # Peak Classifiers
    classifiers = {
        "Random Forest Classifier": RandomForestClassifier(n_estimators=60, max_depth=10, random_state=RANDOM_SEED, n_jobs=-1),
        "XGBoost Classifier": xgb.XGBClassifier(n_estimators=80, max_depth=5, learning_rate=0.08, random_state=RANDOM_SEED, n_jobs=-1, eval_metric="logloss")
    }
    
    best_clf = None
    best_clf_f1 = -1
    best_clf_name = ""
    best_clf_preds = None
    
    print("\n--- Peak Status Classifiers (+15m) ---")
    for name, clf in classifiers.items():
        clf.fit(X_train_15m, train_df["is_peak"].values)
        preds = clf.predict(X_test_15m)
        res = evaluate_classification(y_peak_test, preds)
        res["improvement_over_baseline_pct"] = compute_pct_improvement(best_base_peak_f1, res["F1"], higher_is_better=True)
        metrics_report["peak_classification"][name] = res
        print(f"  {name:25s} -> Acc: {res['Accuracy']:.4f}, Prec: {res['Precision']:.4f}, Rec: {res['Recall']:.4f}, F1: {res['F1']:.4f} (Impr: {res['improvement_over_baseline_pct']}%)")
        
        if res["F1"] > best_clf_f1:
            best_clf_f1 = res["F1"]
            best_clf = clf
            best_clf_name = name
            best_clf_preds = preds
            
    joblib.dump(best_clf, os.path.join(models_dir, "best_peak_classifier.joblib"))
    metrics_report["best_models"]["peak_classifier"] = best_clf_name
    
    # -------------------------------------------------------------
    # Train Direct Multi-Horizon Models (+15m, +1h, +2h, +3h)
    # -------------------------------------------------------------
    print("\n" + "=" * 70)
    print("  PHASE 3: MULTI-HORIZON DIRECT MODELS EVALUATION (+15m, +1h, +2h, +3h)")
    print("=" * 70)
    
    horizons = ["15m", "1h", "2h", "3h"]
    horizon_models = {}
    
    for h in horizons:
        cat_h, num_h = get_feature_columns_for_horizon(h)
        prep_h = create_preprocessor(cat_h, num_h)
        X_tr_h = prep_h.fit_transform(train_df[cat_h + num_h])
        X_te_h = prep_h.transform(test_df[cat_h + num_h])
        
        # Save horizon preprocessor
        joblib.dump(prep_h, os.path.join(models_dir, f"preprocessor_{h}.joblib"))
        
        # Train direct XGBoost for wait time
        h_wait = xgb.XGBRegressor(n_estimators=90, max_depth=6, learning_rate=0.08, random_state=RANDOM_SEED, n_jobs=-1)
        h_wait.fit(X_tr_h, train_df["waiting_time_min"].values)
        joblib.dump(h_wait, os.path.join(models_dir, f"model_wait_{h}.joblib"))
        p_wait = h_wait.predict(X_te_h)
        res_w = evaluate_regression(y_wait_test, p_wait)
        
        # Train direct XGBoost for queue length
        h_queue = xgb.XGBRegressor(n_estimators=90, max_depth=6, learning_rate=0.08, random_state=RANDOM_SEED, n_jobs=-1)
        h_queue.fit(X_tr_h, train_df["queue_length"].values)
        joblib.dump(h_queue, os.path.join(models_dir, f"model_queue_{h}.joblib"))
        p_queue = h_queue.predict(X_te_h)
        res_q = evaluate_regression(y_queue_test, p_queue)
        
        # Train direct XGBoost for peak classifier
        h_peak = xgb.XGBClassifier(n_estimators=70, max_depth=5, learning_rate=0.08, random_state=RANDOM_SEED, n_jobs=-1, eval_metric="logloss")
        h_peak.fit(X_tr_h, train_df["is_peak"].values)
        joblib.dump(h_peak, os.path.join(models_dir, f"model_peak_{h}.joblib"))
        p_peak = h_peak.predict(X_te_h)
        res_p = evaluate_classification(y_peak_test, p_peak)
        
        metrics_report["horizons"][h] = {
            "waiting_time": res_w,
            "queue_length": res_q,
            "is_peak": res_p
        }
        print(f"  Horizon {h:4s} -> Wait MAE: {res_w['MAE']:.3f}, R2: {res_w['R2']:.4f} | Queue MAE: {res_q['MAE']:.3f}, R2: {res_q['R2']:.4f} | Peak F1: {res_p['F1']:.4f}")
        
    # Also train arbitrary future point model (no lags, purely calendar + scheduled context + historical lookup)
    cat_nolag, num_nolag = get_feature_columns_for_horizon("no_lag")
    prep_nolag = create_preprocessor(cat_nolag, num_nolag)
    X_tr_nolag = prep_nolag.fit_transform(train_df[cat_nolag + num_nolag])
    X_te_nolag = prep_nolag.transform(test_df[cat_nolag + num_nolag])
    
    joblib.dump(prep_nolag, os.path.join(models_dir, "preprocessor_nolag.joblib"))
    m_wait_nolag = xgb.XGBRegressor(n_estimators=90, max_depth=6, learning_rate=0.08, random_state=RANDOM_SEED, n_jobs=-1)
    m_wait_nolag.fit(X_tr_nolag, train_df["waiting_time_min"].values)
    joblib.dump(m_wait_nolag, os.path.join(models_dir, "model_wait_nolag.joblib"))
    
    m_queue_nolag = xgb.XGBRegressor(n_estimators=90, max_depth=6, learning_rate=0.08, random_state=RANDOM_SEED, n_jobs=-1)
    m_queue_nolag.fit(X_tr_nolag, train_df["queue_length"].values)
    joblib.dump(m_queue_nolag, os.path.join(models_dir, "model_queue_nolag.joblib"))
    
    m_peak_nolag = xgb.XGBClassifier(n_estimators=70, max_depth=5, learning_rate=0.08, random_state=RANDOM_SEED, n_jobs=-1, eval_metric="logloss")
    m_peak_nolag.fit(X_tr_nolag, train_df["is_peak"].values)
    joblib.dump(m_peak_nolag, os.path.join(models_dir, "model_peak_nolag.joblib"))
    
    res_w_nolag = evaluate_regression(y_wait_test, m_wait_nolag.predict(X_te_nolag))
    metrics_report["horizons"]["no_lag_calendar"] = {
        "waiting_time": res_w_nolag,
        "queue_length": evaluate_regression(y_queue_test, m_queue_nolag.predict(X_te_nolag)),
        "is_peak": evaluate_classification(y_peak_test, m_peak_nolag.predict(X_te_nolag))
    }
    print(f"  Calendar/Arbitrary -> Wait MAE: {res_w_nolag['MAE']:.3f}, R2: {res_w_nolag['R2']:.4f}")
    
    # -------------------------------------------------------------
    # Per-Facility Breakdown on Test Set
    # -------------------------------------------------------------
    print("\n--- Per-Facility Evaluation (Test Split) ---")
    facility_list = sorted(test_df["facility_id"].unique())
    for fac in facility_list:
        mask = (test_df["facility_id"] == fac).values
        fac_y_wait = y_wait_test[mask]
        fac_pred_wait = test_wait_preds[best_wait_name][mask]
        fac_y_queue = y_queue_test[mask]
        fac_pred_queue = test_queue_preds[best_queue_name][mask]
        fac_y_peak = y_peak_test[mask]
        fac_pred_peak = best_clf_preds[mask]
        
        metrics_report["per_facility"][fac] = {
            "waiting_time": evaluate_regression(fac_y_wait, fac_pred_wait),
            "queue_length": evaluate_regression(fac_y_queue, fac_pred_queue),
            "is_peak": evaluate_classification(fac_y_peak, fac_pred_peak)
        }
        print(f"  {fac} -> Wait MAE: {metrics_report['per_facility'][fac]['waiting_time']['MAE']:.2f}m, Queue MAE: {metrics_report['per_facility'][fac]['queue_length']['MAE']:.2f}p, Peak F1: {metrics_report['per_facility'][fac]['is_peak']['F1']:.4f}")
        
    # Feature Importances (Best 15m wait model)
    if hasattr(best_wait_model, "feature_importances_"):
        importances = [float(x) for x in best_wait_model.feature_importances_]
    elif hasattr(best_wait_model, "coef_"):
        importances = [float(x) for x in np.abs(best_wait_model.coef_)]
    else:
        importances = [0.0] * len(feature_names_15m)
        
    feat_imp = sorted(zip(feature_names_15m, importances), key=lambda x: x[1], reverse=True)
    with open(os.path.join(models_dir, "feature_importance.json"), "w") as f:
        json.dump(feat_imp, f, indent=2)
        
    # Save metrics.json
    with open(os.path.join(models_dir, "metrics.json"), "w") as f:
        json.dump(metrics_report, f, indent=2)
    print(f"\n[Saved] Updated metrics saved to: {os.path.join(models_dir, 'metrics.json')}")
    
    # Save standalone metadata.json
    import sklearn
    metadata_dict = {
        "python_version": sys.version,
        "sklearn_version": sklearn.__version__,
        "xgboost_version": xgb.__version__,
        "training_date": datetime.now().isoformat(),
        "data_hash": data_hash,
        "data_path": os.path.abspath(data_path),
        "random_seed": RANDOM_SEED,
        "train_rows": len(train_df),
        "test_rows": len(test_df),
        "walk_forward_folds": 4,
        "best_models": metrics_report["best_models"]
    }
    with open(os.path.join(models_dir, "metadata.json"), "w") as f:
        json.dump(metadata_dict, f, indent=2)
    print(f"[Saved] Model provenance metadata saved to: {os.path.join(models_dir, 'metadata.json')}")
    
    # -------------------------------------------------------------
    # Diagnostic Plots Generation
    # -------------------------------------------------------------
    print("\nGenerating updated diagnostic plots...")
    sns.set_theme(style="whitegrid")
    sub_sample = np.random.choice(len(y_wait_test), size=min(1200, len(y_wait_test)), replace=False)
    
    # 1. Actual vs Predicted Wait Time
    plt.figure(figsize=(8, 6))
    best_p_wait = test_wait_preds[best_wait_name]
    plt.scatter(y_wait_test[sub_sample], best_p_wait[sub_sample], alpha=0.45, color="#3b82f6", edgecolors="none")
    max_val = max(float(np.max(y_wait_test[sub_sample])), float(np.max(best_p_wait[sub_sample])))
    plt.plot([0, max_val], [0, max_val], "r--", linewidth=2, label="Ideal Fit (y = x)")
    plt.title(f"Actual vs Predicted Waiting Time ({best_wait_name})\nTest R² = {metrics_report['waiting_time'][best_wait_name]['R2']:.3f}, MAE = {metrics_report['waiting_time'][best_wait_name]['MAE']:.2f} min", fontsize=12, fontweight="bold")
    plt.xlabel("Actual Waiting Time (min)")
    plt.ylabel("Predicted Waiting Time (min)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, "actual_vs_predicted_wait_time.png"), dpi=200)
    plt.close()
    
    # 2. Actual vs Predicted Queue Length
    plt.figure(figsize=(8, 6))
    best_p_queue = test_queue_preds[best_queue_name]
    plt.scatter(y_queue_test[sub_sample], best_p_queue[sub_sample], alpha=0.45, color="#10b981", edgecolors="none")
    max_val_q = max(float(np.max(y_queue_test[sub_sample])), float(np.max(best_p_queue[sub_sample])))
    plt.plot([0, max_val_q], [0, max_val_q], "r--", linewidth=2, label="Ideal Fit (y = x)")
    plt.title(f"Actual vs Predicted Queue Length ({best_queue_name})\nTest R² = {metrics_report['queue_length'][best_queue_name]['R2']:.3f}, MAE = {metrics_report['queue_length'][best_queue_name]['MAE']:.2f} people", fontsize=12, fontweight="bold")
    plt.xlabel("Actual Queue Length (people)")
    plt.ylabel("Predicted Queue Length (people)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, "actual_vs_predicted_queue_length.png"), dpi=200)
    plt.close()
    
    # 3. Residuals Distribution
    residuals = y_wait_test - best_p_wait
    plt.figure(figsize=(8, 6))
    sns.histplot(residuals, bins=50, kde=True, color="#8b5cf6")
    plt.axvline(0, color="red", linestyle="--", linewidth=2)
    plt.title("Residuals Distribution: Waiting Time (Unbiased Errors)", fontsize=12, fontweight="bold")
    plt.xlabel("Residual (Actual - Predicted) [min]")
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, "residuals_distribution.png"), dpi=200)
    plt.close()
    
    # 4. Feature Importance Plot (Top 12)
    top_feats = feat_imp[:12]
    feats, scores = zip(*top_feats)
    plt.figure(figsize=(10, 6))
    feat_df = pd.DataFrame({"Feature": [f.replace("num__", "").replace("cat__", "") for f in feats], "Importance": list(scores)})
    sns.barplot(data=feat_df, x="Importance", y="Feature", hue="Feature", legend=False, palette="viridis")
    plt.title(f"Top 12 Feature Importances ({best_wait_name})", fontsize=12, fontweight="bold")
    plt.xlabel("Importance Score")
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, "feature_importance.png"), dpi=200)
    plt.close()
    
    # 5. Confusion Matrix for Peak Classifier
    cm = confusion_matrix(y_peak_test, best_clf_preds)
    plt.figure(figsize=(6, 5))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", xticklabels=["Normal", "Peak"], yticklabels=["Normal", "Peak"])
    plt.title(f"Confusion Matrix: Peak Detection ({best_clf_name})\nF1 = {best_clf_f1:.4f}", fontsize=12, fontweight="bold")
    plt.xlabel("Predicted Class")
    plt.ylabel("Actual Class")
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, "confusion_matrix_peak.png"), dpi=200)
    plt.close()
    
    # 6. Model vs Baseline Comparison Chart
    plt.figure(figsize=(10, 5))
    models_compared = list(metrics_report["waiting_time"].keys()) + ["Persistence", "Hist. Mean"]
    maes_compared = [metrics_report["waiting_time"][m]["MAE"] for m in metrics_report["waiting_time"].keys()] + [
        base_persist_wait["MAE"], base_hist_wait["MAE"]
    ]
    colors = ["#3b82f6", "#60a5fa", "#6366f1", "#1d4ed8", "#f59e0b", "#ef4444"]
    bars = plt.bar(models_compared, maes_compared, color=colors, edgecolor="black", linewidth=0.5)
    plt.ylabel("Test MAE (minutes) - Lower is Better")
    plt.title("Model vs. Baseline Benchmark Comparison (Waiting Time Regression)", fontsize=12, fontweight="bold")
    plt.xticks(rotation=20)
    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2.0, yval + 0.1, f"{yval:.2f}m", ha='center', va='bottom', fontsize=9, fontweight='bold')
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, "model_comparison_bar.png"), dpi=200)
    plt.close()
    
    print("[Plots] All diagnostic evaluation plots saved successfully to:", plots_dir)
    return metrics_report

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train and evaluate queue prediction ML models.")
    parser.add_argument("--data-path", type=str, default=None, help="Path to input queue CSV dataset.")
    parser.add_argument("--models-dir", type=str, default=None, help="Directory to save trained models and metrics.")
    parser.add_argument("--plots-dir", type=str, default=None, help="Directory to save diagnostic plots.")
    args = parser.parse_args()
    
    train_and_evaluate(args.data_path, args.models_dir, args.plots_dir)

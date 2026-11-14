import os
import sys
import json
import tempfile

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

def load_and_clean_data(csv_path: str) -> pd.DataFrame:
    print(f"Loading data from {csv_path}...")
    df = pd.read_csv(csv_path, keep_default_na=False)
    
    # 1. Clean data: duplicates, missing values, sorting
    initial_rows = len(df)
    df = df.drop_duplicates(subset=["record_id"])
    df = df.dropna()
    
    # Sort chronologically by timestamp and facility
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values(by=["facility_id", "timestamp"]).reset_index(drop=True)
    
    print(f"Loaded {len(df):,} valid rows (dropped {initial_rows - len(df)} rows).")
    return df

def feature_engineering(df: pd.DataFrame):
    print("Performing feature engineering...")
    
    # Cyclical hour encoding
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24.0)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24.0)
    df["minute_sin"] = np.sin(2 * np.pi * df["minute"] / 60.0)
    df["minute_cos"] = np.cos(2 * np.pi * df["minute"] / 60.0)
    df["dow_sin"] = np.sin(2 * np.pi * df["day_of_week"] / 7.0)
    df["dow_cos"] = np.cos(2 * np.pi * df["day_of_week"] / 7.0)
    
    # Group by facility for time-series features
    grouped = df.groupby("facility_id", group_keys=False)
    
    # Lag features for queue length: lag 1 (10 min), lag 2 (20 min), lag 3 (30 min)
    df["queue_length_lag_1"] = grouped["queue_length"].shift(1).fillna(0)
    df["queue_length_lag_2"] = grouped["queue_length"].shift(2).fillna(0)
    df["queue_length_lag_3"] = grouped["queue_length"].shift(3).fillna(0)
    
    # If the date changed, reset the lag to 0 to prevent yesterday's queue from leaking into today's start
    date_changed = (df["date"] != grouped["date"].shift(1))
    df.loc[date_changed, "queue_length_lag_1"] = 0
    df.loc[date_changed, "queue_length_lag_2"] = 0
    df.loc[date_changed, "queue_length_lag_3"] = 0
    
    # Rolling averages:
    # 30 min waiting time (approx 3 10-min windows)
    df["waiting_time_rolling_30min"] = grouped["waiting_time_min"].rolling(window=3, min_periods=1).mean().reset_index(drop=True).fillna(0)
    # 1 hour arrivals (approx 6 10-min windows)
    df["arrivals_rolling_1h"] = grouped["arrival_rate"].rolling(window=6, min_periods=1).mean().reset_index(drop=True).fillna(0)
    
    # Historical baseline: average wait for the same hour and day of week
    lookup_table = df.groupby(["facility_id", "day_of_week", "hour"])["waiting_time_min"].mean().rename("avg_wait_same_hour_last_week").reset_index()
    df = df.merge(lookup_table, on=["facility_id", "day_of_week", "hour"], how="left")
    df["avg_wait_same_hour_last_week"] = df["avg_wait_same_hour_last_week"].fillna(df["waiting_time_min"].mean())
    
    # Categoricals to one-hot encode
    cat_cols = ["facility_id", "facility_type", "academic_period", "weather", "meal_period"]
    encoded_df = pd.get_dummies(df[cat_cols], drop_first=False, dtype=float)
    
    # Numerical and cyclical features
    num_cols = [
        "hour_sin", "hour_cos", "minute_sin", "minute_cos", "dow_sin", "dow_cos",
        "num_counters_open", "num_staff_on_duty", "avg_service_time_min",
        "arrival_rate", "departure_rate", "group_size", "class_schedule_density",
        "is_weekend", "is_holiday", "is_exam_week", "event_flag", "deadline_proximity_days",
        "queue_length_lag_1", "queue_length_lag_2", "queue_length_lag_3",
        "waiting_time_rolling_30min", "arrivals_rolling_1h", "avg_wait_same_hour_last_week"
    ]
    
    X = pd.concat([df[num_cols], encoded_df], axis=1)
    feature_names = list(X.columns)
    
    y_wait = df["waiting_time_min"].values
    y_queue = df["queue_length"].values
    y_peak = df["is_peak"].values
    
    return df, X, y_wait, y_queue, y_peak, feature_names, lookup_table

def time_based_split(df, X, y_wait, y_queue, y_peak):
    # Sort chronologically by timestamp
    sort_idx = np.argsort(df["timestamp"].values)
    X = X.iloc[sort_idx].reset_index(drop=True)
    y_wait = y_wait[sort_idx]
    y_queue = y_queue[sort_idx]
    y_peak = y_peak[sort_idx]
    
    n = len(X)
    train_end = int(0.70 * n)
    val_end = int(0.85 * n)
    
    X_train, y_wait_train, y_queue_train, y_peak_train = X.iloc[:train_end], y_wait[:train_end], y_queue[:train_end], y_peak[:train_end]
    X_val, y_wait_val, y_queue_val, y_peak_val = X.iloc[train_end:val_end], y_wait[train_end:val_end], y_queue[train_end:val_end], y_peak[train_end:val_end]
    X_test, y_wait_test, y_queue_test, y_peak_test = X.iloc[val_end:], y_wait[val_end:], y_queue[val_end:], y_peak[val_end:]
    
    print(f"Time-based split: Train={len(X_train):,}, Val={len(X_val):,}, Test={len(X_test):,}")
    return (X_train, y_wait_train, y_queue_train, y_peak_train,
            X_val, y_wait_val, y_queue_val, y_peak_val,
            X_test, y_wait_test, y_queue_test, y_peak_test)

def train_and_evaluate():
    data_path = os.path.join(os.path.dirname(__file__), "..", "data", "queue_data.csv")
    models_dir = os.path.join(os.path.dirname(__file__), "models")
    plots_dir = os.path.join(os.path.dirname(__file__), "plots")
    os.makedirs(models_dir, exist_ok=True)
    os.makedirs(plots_dir, exist_ok=True)
    
    df = load_and_clean_data(data_path)
    df, X, y_wait, y_queue, y_peak, feature_names, lookup_table = feature_engineering(df)
    
    (X_train, y_wait_train, y_queue_train, y_peak_train,
     X_val, y_wait_val, y_queue_val, y_peak_val,
     X_test, y_wait_test, y_queue_test, y_peak_test) = time_based_split(df, X, y_wait, y_queue, y_peak)
    
    # Save feature names and historical baseline lookup
    with open(os.path.join(models_dir, "feature_names.json"), "w") as f:
        json.dump(feature_names, f, indent=2)
    lookup_table.to_csv(os.path.join(models_dir, "historical_hourly_lookup.csv"), index=False)
    
    # -----------------------------
    # Regression Models Comparison
    # -----------------------------
    regressors = {
        "Linear Regression": LinearRegression(),
        "Ridge": Ridge(alpha=1.0),
        "Random Forest": RandomForestRegressor(n_estimators=50, max_depth=14, random_state=42, n_jobs=-1),
        "XGBoost": xgb.XGBRegressor(n_estimators=100, max_depth=6, learning_rate=0.08, random_state=42, n_jobs=-1)
    }
    
    metrics_report = {
        "waiting_time": {},
        "queue_length": {},
        "peak_classification": {}
    }
    
    best_wait_model = None
    best_wait_r2 = -float("inf")
    best_wait_name = ""
    wait_preds_test = {}
    
    best_queue_model = None
    best_queue_r2 = -float("inf")
    best_queue_name = ""
    queue_preds_test = {}
    
    print("\n--- Training Waiting Time Regressors ---")
    for name, model in regressors.items():
        print(f"Training {name} for waiting_time_min...")
        model.fit(X_train, y_wait_train)
        pred_val = model.predict(X_val)
        pred_test = model.predict(X_test)
        wait_preds_test[name] = pred_test
        
        mae = float(mean_absolute_error(y_wait_test, pred_test))
        rmse = float(np.sqrt(mean_squared_error(y_wait_test, pred_test)))
        r2 = float(r2_score(y_wait_test, pred_test))
        
        metrics_report["waiting_time"][name] = {"MAE": round(mae, 3), "RMSE": round(rmse, 3), "R2": round(r2, 4)}
        print(f"  {name} -> MAE: {mae:.2f}, RMSE: {rmse:.2f}, R2: {r2:.4f}")
        
        if r2 > best_wait_r2:
            best_wait_r2 = r2
            best_wait_model = model
            best_wait_name = name
            
    print(f"--> Best Waiting Time Model: {best_wait_name} (R2={best_wait_r2:.4f})")
    joblib.dump(best_wait_model, os.path.join(models_dir, "best_wait_time_model.joblib"))
    
    print("\n--- Training Queue Length Regressors ---")
    for name, model in regressors.items():
        print(f"Training {name} for queue_length...")
        # create new instance
        model_instance = model.__class__(**model.get_params())
        model_instance.fit(X_train, y_queue_train)
        pred_val = model_instance.predict(X_val)
        pred_test = model_instance.predict(X_test)
        queue_preds_test[name] = pred_test
        
        mae = float(mean_absolute_error(y_queue_test, pred_test))
        rmse = float(np.sqrt(mean_squared_error(y_queue_test, pred_test)))
        r2 = float(r2_score(y_queue_test, pred_test))
        
        metrics_report["queue_length"][name] = {"MAE": round(mae, 3), "RMSE": round(rmse, 3), "R2": round(r2, 4)}
        print(f"  {name} -> MAE: {mae:.2f}, RMSE: {rmse:.2f}, R2: {r2:.4f}")
        
        if r2 > best_queue_r2:
            best_queue_r2 = r2
            best_queue_model = model_instance
            best_queue_name = name
            
    print(f"--> Best Queue Length Model: {best_queue_name} (R2={best_queue_r2:.4f})")
    joblib.dump(best_queue_model, os.path.join(models_dir, "best_queue_length_model.joblib"))
    
    # -----------------------------
    # Peak Classifier Comparison
    # -----------------------------
    print("\n--- Training Peak Period Classifiers ---")
    classifiers = {
        "Random Forest Classifier": RandomForestClassifier(n_estimators=60, max_depth=12, random_state=42, n_jobs=-1),
        "XGBoost Classifier": xgb.XGBClassifier(n_estimators=80, max_depth=6, learning_rate=0.1, random_state=42, n_jobs=-1, eval_metric="logloss")
    }
    
    best_clf = None
    best_clf_f1 = -1
    best_clf_name = ""
    best_clf_preds = None
    
    for name, clf in classifiers.items():
        print(f"Training {name} for is_peak...")
        clf.fit(X_train, y_peak_train)
        pred_test = clf.predict(X_test)
        
        acc = float(accuracy_score(y_peak_test, pred_test))
        prec = float(precision_score(y_peak_test, pred_test, zero_division=0))
        rec = float(recall_score(y_peak_test, pred_test, zero_division=0))
        f1 = float(f1_score(y_peak_test, pred_test, zero_division=0))
        
        metrics_report["peak_classification"][name] = {
            "Accuracy": round(acc, 4),
            "Precision": round(prec, 4),
            "Recall": round(rec, 4),
            "F1": round(f1, 4)
        }
        print(f"  {name} -> Acc: {acc:.4f}, Prec: {prec:.4f}, Rec: {rec:.4f}, F1: {f1:.4f}")
        
        if f1 > best_clf_f1:
            best_clf_f1 = f1
            best_clf = clf
            best_clf_name = name
            best_clf_preds = pred_test
            
    print(f"--> Best Classifier: {best_clf_name} (F1={best_clf_f1:.4f})")
    joblib.dump(best_clf, os.path.join(models_dir, "best_peak_classifier.joblib"))
    
    # Extract Feature Importances
    if hasattr(best_wait_model, "feature_importances_"):
        importances = best_wait_model.feature_importances_
    elif hasattr(best_wait_model, "coef_"):
        importances = np.abs(best_wait_model.coef_)
    else:
        importances = np.zeros(len(feature_names))
        
    feat_imp = sorted(zip(feature_names, [float(x) for x in importances]), key=lambda x: x[1], reverse=True)
    with open(os.path.join(models_dir, "feature_importance.json"), "w") as f:
        json.dump(feat_imp, f, indent=2)
        
    metrics_report["best_models"] = {
        "waiting_time": best_wait_name,
        "queue_length": best_queue_name,
        "peak_classifier": best_clf_name
    }
    
    with open(os.path.join(models_dir, "metrics.json"), "w") as f:
        json.dump(metrics_report, f, indent=2)
    print(f"Metrics saved to {os.path.join(models_dir, 'metrics.json')}")
    
    # -----------------------------
    # Plot Generation
    # -----------------------------
    print("\nGenerating evaluation plots...")
    sns.set_theme(style="whitegrid")
    
    # 1. Actual vs Predicted (Waiting Time)
    plt.figure(figsize=(8, 6))
    best_wait_preds = wait_preds_test[best_wait_name]
    sub_sample = np.random.choice(len(y_wait_test), size=min(1000, len(y_wait_test)), replace=False)
    plt.scatter(y_wait_test[sub_sample], best_wait_preds[sub_sample], alpha=0.45, color="#3b82f6", edgecolors="none")
    max_val = max(np.max(y_wait_test[sub_sample]), np.max(best_wait_preds[sub_sample]))
    plt.plot([0, max_val], [0, max_val], "r--", linewidth=2, label="Ideal Fit (y = x)")
    plt.title(f"Actual vs Predicted Waiting Time ({best_wait_name})\nTest R² = {best_wait_r2:.3f}", fontsize=13, fontweight="bold")
    plt.xlabel("Actual Waiting Time (min)")
    plt.ylabel("Predicted Waiting Time (min)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, "actual_vs_predicted_wait_time.png"), dpi=200)
    plt.close()
    
    # 2. Actual vs Predicted (Queue Length)
    plt.figure(figsize=(8, 6))
    best_queue_preds = queue_preds_test[best_queue_name]
    plt.scatter(y_queue_test[sub_sample], best_queue_preds[sub_sample], alpha=0.45, color="#10b981", edgecolors="none")
    max_val_q = max(np.max(y_queue_test[sub_sample]), np.max(best_queue_preds[sub_sample]))
    plt.plot([0, max_val_q], [0, max_val_q], "r--", linewidth=2, label="Ideal Fit (y = x)")
    plt.title(f"Actual vs Predicted Queue Length ({best_queue_name})\nTest R² = {best_queue_r2:.3f}", fontsize=13, fontweight="bold")
    plt.xlabel("Actual Queue Length (people)")
    plt.ylabel("Predicted Queue Length (people)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, "actual_vs_predicted_queue_length.png"), dpi=200)
    plt.close()
    
    # 3. Residuals Distribution
    residuals = y_wait_test - best_wait_preds
    plt.figure(figsize=(8, 6))
    sns.histplot(residuals, bins=50, kde=True, color="#8b5cf6")
    plt.axvline(0, color="red", linestyle="--", linewidth=2)
    plt.title("Residuals Distribution (Waiting Time)", fontsize=13, fontweight="bold")
    plt.xlabel("Residual (Actual - Predicted) [min]")
    plt.ylabel("Count")
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, "residuals_distribution.png"), dpi=200)
    plt.close()
    
    # 4. Feature Importance Plot (Top 12)
    top_feats = feat_imp[:12]
    feats, scores = zip(*top_feats)
    plt.figure(figsize=(10, 6))
    feat_df = pd.DataFrame({"Feature": list(feats), "Importance": list(scores)})
    sns.barplot(data=feat_df, x="Importance", y="Feature", hue="Feature", legend=False, palette="viridis")
    plt.title(f"Top 12 Feature Importances ({best_wait_name})", fontsize=13, fontweight="bold")
    plt.xlabel("Importance Score")
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, "feature_importance.png"), dpi=200)
    plt.close()
    
    # 5. Confusion Matrix for Peak Classifier
    cm = confusion_matrix(y_peak_test, best_clf_preds)
    plt.figure(figsize=(6, 5))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", xticklabels=["Normal", "Peak"], yticklabels=["Normal", "Peak"])
    plt.title(f"Confusion Matrix: Peak Detection ({best_clf_name})", fontsize=13, fontweight="bold")
    plt.xlabel("Predicted Class")
    plt.ylabel("Actual Class")
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, "confusion_matrix_peak.png"), dpi=200)
    plt.close()
    
    # 6. Model Comparison Bar Chart
    plt.figure(figsize=(9, 5))
    model_names = list(metrics_report["waiting_time"].keys())
    r2_scores = [metrics_report["waiting_time"][m]["R2"] for m in model_names]
    maes = [metrics_report["waiting_time"][m]["MAE"] for m in model_names]
    x_pos = np.arange(len(model_names))
    width = 0.35
    
    plt.bar(x_pos - width/2, r2_scores, width, label="R² Score", color="#3b82f6")
    plt.bar(x_pos + width/2, [1.0 / max(0.1, m) for m in maes], width, label="1 / MAE (Efficiency)", color="#f59e0b")
    plt.xticks(x_pos, model_names, rotation=15)
    plt.ylabel("Score")
    plt.title("Model Performance Comparison (Waiting Time Regression)", fontsize=13, fontweight="bold")
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, "model_comparison_bar.png"), dpi=200)
    plt.close()
    
    print("All plots generated and saved successfully to:", plots_dir)

if __name__ == "__main__":
    train_and_evaluate()

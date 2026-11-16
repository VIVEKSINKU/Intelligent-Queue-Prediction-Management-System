# Machine Learning Evaluation & Audit Report
**Project: Intelligent Queue Prediction & Management System**

---

## 1. System Overview & Pre-Audit Baseline (Phase 0)

### 1.1 Features Used by Models (Pre-Audit)
Prior to the audit, the models in `ml/train.py` trained on the following features:
- **Cyclical Temporal**: `hour_sin`, `hour_cos`, `minute_sin`, `minute_cos`, `dow_sin`, `dow_cos`
- **Facility & Operational**: `num_counters_open`, `num_staff_on_duty`, `avg_service_time_min`, `arrival_rate`, `departure_rate`, `group_size`
- **Academic & Contextual**: `class_schedule_density`, `is_weekend`, `is_holiday`, `is_exam_week`, `event_flag`, `deadline_proximity_days`
- **Categoricals (One-Hot Encoded)**: `facility_id`, `facility_type`, `academic_period`, `weather`, `meal_period`
- **Target Lags & Rolling Features**:
  - `queue_length_lag_1`, `queue_length_lag_2`, `queue_length_lag_3`
  - `waiting_time_rolling_30min` (rolling mean of `waiting_time_min` with window=3)
  - `arrivals_rolling_1h` (rolling mean of `arrival_rate` with window=6)
  - `avg_wait_same_hour_last_week` (historical hourly average)

### 1.2 Target Definitions in Data Simulator
- **`queue_length`**: $\text{queue\_length}_t = \max(0, \text{queue\_length}_{t-1} + \text{arrivals}_t - \text{actual\_departures}_t)$
- **`waiting_time_min`**: If counters open $>0$, calculated as $\frac{\text{queue\_length}_t \times \text{avg\_service\_time}_t}{\text{counters\_open}_t} + \epsilon$; otherwise $0.0$.
- **`is_peak`**: Defined by thresholding targets:
  - Cafeteria (`FAC_02`): $\text{waiting\_time\_min} \ge 12.0 \lor \text{queue\_length} \ge 18$
  - Library (`FAC_04`): $\text{waiting\_time\_min} \ge 8.0 \lor \text{queue\_length} \ge 7$
  - Other facilities: $\text{waiting\_time\_min} \ge 15.0 \lor \text{queue\_length} \ge 8$

### 1.3 Target-Derived & Target-Lagged Features
1. `waiting_time_rolling_30min`: derived from `waiting_time_min` without lag (included row $t$).
2. `avg_wait_same_hour_last_week`: computed by aggregating `waiting_time_min` across the entire dataset.
3. `queue_length_lag_1..3`: direct lags of `queue_length`.
4. `departure_rate`: calculated directly from `actual_departures` in interval $[t, t+10\text{min}]$, which directly dictates `queue_length` at time $t$.

---

## 2. Leakage Audit (Phase 1)

### 2.1 Identified Data Leaks & Root Causes

#### Leak 1: Post-Hoc Target Component (`departure_rate`)
- **Location**: `ml/train.py`, `data/generate_dataset.py`
- **Mechanism**: `departure_rate` represents the departures processed during time step $t$ ($\text{actual\_departures} \times 6$). Because $\text{queue\_length}_t = \text{queue\_length}_{t-1} + \frac{\text{arrival\_rate}_t}{6} - \frac{\text{departure\_rate}_t}{6}$, the feature vector contained the exact algebraic equation of the target.
- **Why Linear Regression achieved $R^2 \approx 0.9999$**:
  Ordinary Least Squares was able to solve the exact arithmetic identity:
  $$\text{queue\_length} = 1.0 \times \text{queue\_length\_lag\_1} + 0.1667 \times \text{arrival\_rate} - 0.1667 \times \text{departure\_rate}$$
  resulting in an artificial near-zero MAE (0.045 people) and $R^2 = 0.9999$. In practice, actual departures cannot be observed prior to queue realization.

#### Leak 2: Unshifted Target Rolling Window (`waiting_time_rolling_30min`)
- **Location**: `ml/train.py` line 73: `df["waiting_time_rolling_30min"] = grouped["waiting_time_min"].rolling(window=3, min_periods=1).mean()`
- **Mechanism**: Pandas `.rolling(window=3)` includes the current row $t$ by default if `.shift(1)` is omitted. The feature was $(y_{t-2} + y_{t-1} + y_t) / 3$, directly leaking $\frac{1}{3} \times y_t$ into the feature vector.

#### Leak 3: Global Dataset Target Aggregation (`avg_wait_same_hour_last_week`)
- **Location**: `ml/train.py` line 78
- **Mechanism**: Groupby mean of `waiting_time_min` by `(facility_id, day_of_week, hour)` was performed on the full dataframe `df` prior to train/test splitting. This leaked future test-set target values into the training and validation features.

#### Leak 4: Trivial Peak Classification via Leaked Targets
- **Location**: `ml/train.py`
- **Mechanism**: Since `is_peak` is a deterministic threshold on `waiting_time_min` and `queue_length`, feeding leaked `waiting_time_rolling_30min` and `departure_rate` made the classifier trivially invert the threshold, producing an artificial $98.78\%$ accuracy and $0.9847$ F1 score.

#### Leak 5: Unencapsulated Preprocessing & Categorical Encoding
- **Location**: `ml/train.py` line 84
- **Mechanism**: `pd.get_dummies` was applied globally across all rows. No scikit-learn `Pipeline` or `ColumnTransformer` was fitted solely on training splits.

---

## 3. Remediation & Clean Pipeline Design

To resolve all identified leaks:
1. **Removed `departure_rate`**: Completely excised from all feature sets.
2. **Properly Shifted Lags & Rolling Features**: Any rolling feature uses `.shift(1).rolling(...)` so only historical steps $\le t-1$ are accessible for nowcasting, and $\le t-H$ for horizon $H$.
3. **Train-Only Encoders & Lookups**:
   - `OneHotEncoder(handle_unknown='ignore')` fitted strictly on `X_train`.
   - `historical_hourly_lookup` computed strictly on `train_df`. Unseen test groups fall back to overall training mean.
4. **Pipeline Encapsulation**: Model pipelines are encapsulated using `scikit-learn` `Pipeline` and `ColumnTransformer`.
5. **No-Future-Information Feature Set for Multi-Horizon Forecasting**: Lags from $t-1$ are excluded for multi-step ahead forecasts ($+1\text{h}$, $+2\text{h}$, $+3\text{h}$) where future queue states are unknown.

*(Sections 4, 5, and 6 will report empirical baseline comparisons, walk-forward validation results, and before/after metrics).*

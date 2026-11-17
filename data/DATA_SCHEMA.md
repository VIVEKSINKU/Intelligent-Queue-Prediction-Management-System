# Queue Dataset Schema & Real Data Ingestion Guide

This document specifies the required schema and format for importing real sensor/ticketing queue data into the **Intelligent Queue Prediction & Management System**.

## Ingestion Overview

The training pipeline supports dropping in a real-world dataset directly using the `--data-path` flag:

```bash
python ml/train.py --data-path data/real_queue_data.csv
```

---

## Required Column Specification

Any real-world CSV dataset provided to `train.py` must include the following schema:

| Column Name | Data Type | Description | Example Values |
|-------------|-----------|-------------|----------------|
| `record_id` | String / UUID | Unique record identifier | `"REC_000001"` |
| `timestamp` | Datetime ISO-8601 | Timestamp of observation | `"2026-10-15 12:30:00"` |
| `date` | Date (YYYY-MM-DD) | Observation calendar date | `"2026-10-15"` |
| `hour` | Integer (0-23) | Hour of the day | `12` |
| `minute` | Integer (0-59) | Minute of the hour | `30` |
| `day_of_week` | Integer (0-6) | Monday = 0, Sunday = 6 | `3` |
| `week_of_year` | Integer (1-52) | ISO calendar week number | `42` |
| `month` | Integer (1-12) | Calendar month number | `10` |
| `is_weekend` | Integer (0 or 1) | 1 if Saturday or Sunday, else 0 | `0` |
| `is_holiday` | Integer (0 or 1) | 1 if statutory campus holiday | `0` |
| `facility_id` | Categorical String | Facility identifier | `"FAC_01"`, `"FAC_02"`, etc. |
| `facility_type` | Categorical String | Type category | `"Dining"`, `"Administrative"` |
| `service_type` | Categorical String | Service desk task | `"Meal Purchase"`, `"Transcript Request"` |
| `counter_id` | String | Individual counter desk identifier | `"COUNTER_01"` |
| `num_counters_open` | Integer ($\ge 0$) | Total active counters open | `4` |
| `num_staff_on_duty` | Integer ($\ge 0$) | Total staff present | `5` |
| `avg_service_time_min` | Float ($> 0$) | Average nominal service time | `2.5` |
| `arrival_rate` | Float ($\ge 0$) | Arrivals per hour | `24.0` |
| `group_size` | Float ($\ge 1.0$) | Mean visitor party size | `1.5` |
| `academic_period` | Categorical String | Semester phase | `"Normal"`, `"Registration"`, `"Midterms"` |
| `is_exam_week` | Integer (0 or 1) | 1 if exams are in session | `0` |
| `class_schedule_density` | Float (0.0 - 1.0) | Fraction of active students in class | `0.75` |
| `event_flag` | Integer (0 or 1) | 1 if special campus event today | `0` |
| `deadline_proximity_days` | Integer ($\ge 0$) | Days until nearest fee/admin deadline | `7` |
| `weather` | Categorical String | Weather condition | `"Sunny"`, `"Rainy"`, `"Overcast"` |
| `meal_period` | Categorical String | Meal slot | `"Breakfast"`, `"Lunch"`, `"Dinner"`, `"Non-Meal"` |
| `waiting_time_min` | Float ($\ge 0$) | **Target 1**: Observed wait time in minutes | `14.5` |
| `queue_length` | Integer ($\ge 0$) | **Target 2**: Observed people in queue | `18` |
| `is_peak` | Integer (0 or 1) | **Target 3**: Binary flag if wait $\ge 15$m or queue $\ge 15$ | `1` |

---

## Leakage Prevention Protocol for Real Data

When logging real sensor or ticketing data:
1. **Never include `departure_rate`** or post-service completion rates as features.
2. All rolling features must be computed **strictly backward-looking** (shifted by at least 1 observation so the current row is unobserved).
3. Any custom historical lookups must be computed **only over the training split**.

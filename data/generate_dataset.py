import os
import math
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

def generate_queue_dataset():
    np.random.seed(42)
    
    start_date = datetime(2026, 5, 1, 8, 0, 0)
    days = 184 # ~6 months from May to end of October 2026
    
    facilities = [
        {
            "id": "FAC_01",
            "name": "Admin Office",
            "type": "Administrative",
            "services": ["Document Verification", "Transcript Request", "Student ID Issuance"],
            "base_service_mean": 6.0,
            "base_service_sigma": 0.25,
            "min_counters": 1,
            "max_counters": 4,
            "closed_on_weekend": True,
            "avg_group_size": 1.15
        },
        {
            "id": "FAC_02",
            "name": "Main Cafeteria",
            "type": "Dining",
            "services": ["Meal Purchase", "Snack & Beverage", "Express Counter"],
            "base_service_mean": 2.0,
            "base_service_sigma": 0.22,
            "min_counters": 2,
            "max_counters": 6,
            "closed_on_weekend": False,
            "avg_group_size": 2.2
        },
        {
            "id": "FAC_03",
            "name": "Student Services Counter",
            "type": "Student Services",
            "services": ["Academic Advising", "Financial Aid Inquiry", "Housing Assistance"],
            "base_service_mean": 6.5,
            "base_service_sigma": 0.25,
            "min_counters": 1,
            "max_counters": 4,
            "closed_on_weekend": True,
            "avg_group_size": 1.2
        },
        {
            "id": "FAC_04",
            "name": "Library Desk",
            "type": "Library",
            "services": ["Book Checkout & Return", "Study Room Booking", "Reference Assistance"],
            "base_service_mean": 3.0,
            "base_service_sigma": 0.22,
            "min_counters": 1,
            "max_counters": 3,
            "closed_on_weekend": False,
            "avg_group_size": 1.3
        },
        {
            "id": "FAC_05",
            "name": "Fee Payment Counter",
            "type": "Financial",
            "services": ["Tuition Fee Payment", "Fine Payment", "Scholarship Check-in"],
            "base_service_mean": 5.0,
            "base_service_sigma": 0.25,
            "min_counters": 1,
            "max_counters": 4,
            "closed_on_weekend": True,
            "avg_group_size": 1.1
        }
    ]
    
    holidays = {
        (5, 25): "Memorial Day / Campus Break",
        (7, 4): "Independence Day",
        (9, 7): "Labor Day",
        (10, 12): "Fall Holiday"
    }
    
    rows = []
    record_counter = 1
    
    step_minutes = 10
    total_steps_per_day = int((12 * 60) / step_minutes) + 1 # 73 steps
    
    weather_options = ["Sunny", "Cloudy", "Rainy", "Cold"]
    weather_weights = [0.55, 0.25, 0.15, 0.05]
    
    for day_idx in range(days):
        current_date = start_date.date() + timedelta(days=day_idx)
        month = current_date.month
        day = current_date.day
        weekday = current_date.weekday() # 0 = Monday, 6 = Sunday
        is_weekend = 1 if weekday >= 5 else 0
        is_holiday = 1 if (month, day) in holidays else 0
        week_of_year = current_date.isocalendar()[1]
        
        # Academic period assignment
        if day_idx <= 14:
            academic_period = "Registration"
            deadline_proximity_days = max(0, 14 - day_idx)
        elif 42 <= day_idx <= 54:
            academic_period = "Midterms"
            deadline_proximity_days = max(0, 50 - day_idx)
        elif 95 <= day_idx <= 108:
            academic_period = "Fee Payment Due"
            deadline_proximity_days = max(0, 105 - day_idx)
        elif 165 <= day_idx <= 178:
            academic_period = "Final Exams"
            deadline_proximity_days = max(0, 175 - day_idx)
        elif (month == 7 and 1 <= day <= 20) or day_idx > 180:
            academic_period = "Summer Break"
            deadline_proximity_days = 30
        else:
            academic_period = "Normal"
            deadline_proximity_days = min(30, max(5, 30 - (day_idx % 25)))
            
        is_exam_week = 1 if academic_period in ["Midterms", "Final Exams"] else 0
        
        # Daily factors
        day_weather = np.random.choice(weather_options, p=weather_weights)
        event_flag = 1 if (np.random.rand() < 0.10 and not is_weekend and not is_holiday) else 0
        
        # Base schedule density
        if is_holiday:
            base_density = 0.05
        elif is_weekend:
            base_density = 0.15
        elif weekday in [1, 2, 3]: # Tue, Wed, Thu
            base_density = 0.85
        else: # Mon, Fri
            base_density = 0.70
            
        for fac in facilities:
            fac_id = fac["id"]
            fac_type = fac["type"]
            services = fac["services"]
            
            is_closed_day = (fac["closed_on_weekend"] and is_weekend) or is_holiday
            current_queue = 0
            
            for step in range(total_steps_per_day):
                timestamp = datetime(current_date.year, current_date.month, current_date.day, 8, 0, 0) + timedelta(minutes=step * step_minutes)
                hour = timestamp.hour
                minute = timestamp.minute
                
                # Meal period categorization
                if 8 <= hour < 10:
                    meal_period = "Breakfast"
                elif 11 <= hour < 14:
                    meal_period = "Lunch"
                elif 17 <= hour < 20:
                    meal_period = "Dinner"
                else:
                    meal_period = "Non-Meal"
                    
                is_class_break = 1 if (minute in [50, 0]) and (9 <= hour <= 16) and not is_weekend else 0
                
                # Hourly density
                if 9 <= hour <= 16 and not is_weekend:
                    class_schedule_density = round(min(1.0, max(0.2, base_density + np.random.uniform(-0.05, 0.08))), 2)
                else:
                    class_schedule_density = round(max(0.1, base_density * 0.35), 2)
                    
                if is_closed_day:
                    lambda_arrival = np.random.uniform(0.0, 0.1)
                    counters_open = 0
                    staff_on_duty = 0
                else:
                    # Calibrate arrivals and counters to produce natural queues (5 to 30 min wait during peak, 1-5 min offpeak)
                    if fac_id == "FAC_02": # Main Cafeteria
                        # Service mean: 2 min. 1 counter handles 5 people / 10 min.
                        if 12 <= hour < 14:
                            lambda_arrival = 28.0 if minute in [0, 10, 20] else 22.0
                            counters_open = 4 if minute in [0, 10, 20] else 3
                        elif 17 <= hour < 19:
                            lambda_arrival = 16.0
                            counters_open = 3
                        elif 8 <= hour < 10:
                            lambda_arrival = 10.0
                            counters_open = 2
                        else:
                            lambda_arrival = 5.0
                            counters_open = 2
                        if is_class_break:
                            lambda_arrival += 6.0
                        if day_weather == "Rainy":
                            lambda_arrival *= 1.15
                        if is_weekend:
                            lambda_arrival *= 0.6
                            counters_open = max(2, counters_open - 1)
                            
                    elif fac_id == "FAC_01": # Admin Office
                        # Service mean: 6 min. 1 counter handles 1.67 people / 10 min.
                        if 10 <= hour <= 11 or 14 <= hour <= 15:
                            lambda_arrival = 4.2
                            counters_open = 2
                        elif 12 <= hour <= 13:
                            lambda_arrival = 2.5
                            counters_open = 1 # Lunch break for staff
                        else:
                            lambda_arrival = 2.0
                            counters_open = 2
                        if academic_period == "Registration":
                            lambda_arrival += 2.2
                            counters_open = min(4, counters_open + 1)
                        if deadline_proximity_days <= 3:
                            lambda_arrival += 1.5
                            
                    elif fac_id == "FAC_03": # Student Services
                        # Service mean: 6.5 min. 1 counter handles 1.5 people / 10 min.
                        if 11 <= hour <= 14:
                            lambda_arrival = 4.0
                            counters_open = 2
                        else:
                            lambda_arrival = 1.8
                            counters_open = 1
                        if academic_period in ["Registration", "Midterms"]:
                            lambda_arrival += 1.8
                            counters_open = min(4, counters_open + 1)
                        if event_flag:
                            lambda_arrival += 1.2
                            
                    elif fac_id == "FAC_04": # Library Desk
                        # Service mean: 3.0 min. 1 counter handles 3.3 people / 10 min.
                        if is_exam_week and (14 <= hour <= 19):
                            lambda_arrival = 9.0
                            counters_open = 2
                        elif 15 <= hour <= 18:
                            lambda_arrival = 6.2
                            counters_open = 2
                        else:
                            lambda_arrival = 2.4
                            counters_open = 1
                        if day_weather in ["Rainy", "Cold"]:
                            lambda_arrival += 1.2
                        if is_weekend:
                            lambda_arrival *= 0.7
                            
                    elif fac_id == "FAC_05": # Fee Counter
                        # Service mean: 5.0 min. 1 counter handles 2.0 people / 10 min.
                        if (academic_period == "Fee Payment Due" or deadline_proximity_days <= 5) and (10 <= hour <= 14):
                            lambda_arrival = 7.0
                            counters_open = 3
                        elif 10 <= hour <= 13:
                            lambda_arrival = 3.6
                            counters_open = 2
                        else:
                            lambda_arrival = 1.2
                            counters_open = 1
                        if academic_period == "Registration":
                            lambda_arrival += 1.2
                            
                    counters_open = min(fac["max_counters"], max(fac["min_counters"], counters_open))
                    # Queue reactive counter addition
                    if current_queue >= 12 and counters_open < fac["max_counters"]:
                        counters_open += 1
                    staff_on_duty = counters_open + (1 if np.random.rand() > 0.4 else 0)
                
                # Sample arrivals from Poisson distribution
                arrivals = int(np.random.poisson(lam=max(0.1, lambda_arrival)))
                arrival_rate = round(float(arrivals * (60.0 / step_minutes)), 1)
                
                # Sample service times
                mu = np.log(fac["base_service_mean"]) - 0.5 * (fac["base_service_sigma"] ** 2)
                sampled_service_times = np.random.lognormal(mean=mu, sigma=fac["base_service_sigma"], size=max(1, arrivals))
                avg_service_time_min = round(float(np.mean(sampled_service_times)), 2)
                
                if counters_open > 0:
                    service_capacity = (counters_open * step_minutes) / avg_service_time_min
                    actual_capacity = int(service_capacity * np.random.uniform(0.90, 1.10))
                else:
                    actual_capacity = 0
                    
                queue_length_at_arrival = current_queue
                total_in_queue = current_queue + arrivals
                actual_departures = min(total_in_queue, actual_capacity)
                current_queue = total_in_queue - actual_departures
                departure_rate = round(float(actual_departures * (60.0 / step_minutes)), 1)
                
                # Wait time
                if counters_open > 0:
                    expected_wait = (current_queue * avg_service_time_min) / counters_open
                    noise = np.random.normal(0, 0.4 + expected_wait * 0.04)
                    waiting_time_min = max(0.5, round(float(expected_wait + noise), 2))
                else:
                    waiting_time_min = 0.0
                    current_queue = 0
                    
                queue_length = int(current_queue)
                
                # Peak logic: wait time exceeds threshold or queue is long
                if fac_id == "FAC_02": # Cafeteria
                    is_peak = 1 if (waiting_time_min >= 12.0 or queue_length >= 18) else 0
                elif fac_id == "FAC_04": # Library
                    is_peak = 1 if (waiting_time_min >= 8.0 or queue_length >= 7) else 0
                else:
                    is_peak = 1 if (waiting_time_min >= 15.0 or queue_length >= 8) else 0
                
                service_type = np.random.choice(services)
                counter_id = f"C{np.random.randint(1, counters_open + 1)}" if counters_open > 0 else "C0"
                group_size = round(max(1.0, np.random.normal(fac["avg_group_size"], 0.25)), 1)
                
                rows.append({
                    "record_id": f"REC_{record_counter:07d}",
                    "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "date": timestamp.strftime("%Y-%m-%d"),
                    "hour": hour,
                    "minute": minute,
                    "day_of_week": weekday,
                    "week_of_year": week_of_year,
                    "month": month,
                    "is_weekend": is_weekend,
                    "is_holiday": is_holiday,
                    "facility_id": fac_id,
                    "facility_type": fac_type,
                    "service_type": service_type,
                    "counter_id": counter_id,
                    "num_counters_open": counters_open,
                    "num_staff_on_duty": staff_on_duty,
                    "avg_service_time_min": avg_service_time_min,
                    "arrival_rate": arrival_rate,
                    "departure_rate": departure_rate,
                    "queue_length_at_arrival": queue_length_at_arrival,
                    "group_size": group_size,
                    "academic_period": academic_period,
                    "is_exam_week": is_exam_week,
                    "class_schedule_density": class_schedule_density,
                    "event_flag": event_flag,
                    "deadline_proximity_days": deadline_proximity_days,
                    "weather": day_weather,
                    "meal_period": meal_period,
                    "waiting_time_min": waiting_time_min,
                    "queue_length": queue_length,
                    "is_peak": is_peak
                })
                record_counter += 1
                
    df = pd.DataFrame(rows)
    output_path = os.path.join(os.path.dirname(__file__), "queue_data.csv")
    df.to_csv(output_path, index=False)
    print(f"Dataset generation complete! Generated {len(df):,} rows.")
    print(f"Saved to: {output_path}")
    print("\nSummary Statistics:")
    print(df[["waiting_time_min", "queue_length", "arrival_rate", "num_counters_open"]].describe())
    print("\nDistribution of Peaks:")
    print(df["is_peak"].value_counts(normalize=True))
    print("\nFacility Breakdown:")
    print(df.groupby("facility_id")[["waiting_time_min", "queue_length", "is_peak"]].mean())

if __name__ == "__main__":
    generate_queue_dataset()

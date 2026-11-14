from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text
from backend.app.database import Base

class FacilityDB(Base):
    __tablename__ = "facilities"
    
    facility_id = Column(String(20), primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    facility_type = Column(String(50), nullable=False)
    location = Column(String(150), nullable=False)
    operating_hours = Column(String(100), nullable=False)
    default_counters = Column(Integer, default=2)
    max_counters = Column(Integer, default=4)
    closed_on_weekend = Column(Boolean, default=True)

class QueueSnapshotDB(Base):
    __tablename__ = "queue_snapshots"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    facility_id = Column(String(20), index=True, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    queue_length = Column(Integer, default=0)
    waiting_time_min = Column(Float, default=0.0)
    crowd_level = Column(String(20), default="Low")
    counters_open = Column(Integer, default=1)
    is_peak = Column(Boolean, default=False)
    data_source = Column(String(50), default="Dataset Replay Simulator") # or "CV Sensor", "Ticketing API"

class RecommendationDB(Base):
    __tablename__ = "recommendations"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    facility_id = Column(String(20), index=True, nullable=False)
    title = Column(String(100), nullable=False)
    tip_text = Column(Text, nullable=False)
    category = Column(String(50), default="Timing") # "Timing", "Counter Efficiency", "General"
    is_active = Column(Boolean, default=True)

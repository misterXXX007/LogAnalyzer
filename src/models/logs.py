from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, Boolean,  JSON
from database.sqlite import Base

class RawLog(Base):
    __tablename__ = "raw_logs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, index=True)
    event = Column(String)
    payload = Column(JSON)
    processed = Column(Boolean, default=False)

class JobAnalytics(Base):
    __tablename__ = "job_analytics"

    job_id = Column(Integer, primary_key=True, index=True)
    user = Column(String, index=True)
    start_time = Column(String)
    end_time = Column(String)
    status = Column(String)


class TaskAnalytics(Base):
    __tablename__ = "task_analytics"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String, index=True)
    job_id = Column(Integer)
    timestamp = Column(String)
    duration_ms = Column(Integer)
    successful = Column(Boolean)


# Pydantic models for API responses
class JobSummary(BaseModel):
    """Summary of a single job's analytics"""
    job_id: int
    user: Optional[str]
    start_time: Optional[str]
    end_time: Optional[str]
    status: Optional[str]
    task_count: int
    failed_tasks: int
    success_rate: float
    duration_seconds: Optional[int]

    class Config:
        orm_mode = True
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class AnalyticsSummary(BaseModel):
    """Summary statistics for all jobs on a given date"""
    total_jobs: int
    total_tasks: int
    failed_tasks: int
    avg_success_rate: float
    avg_duration_seconds: float

    class Config:
        json_encoders = {
            float: lambda v: round(v, 2)
        }


class AnalyticsResponse(BaseModel):
    """Complete analytics response for the summary endpoint"""
    date: str
    summary: AnalyticsSummary
    jobs: List[JobSummary]

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

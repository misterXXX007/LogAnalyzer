from datetime import datetime, timedelta
from typing import List
from sqlalchemy.orm import Session
from models.logs import JobAnalytics, TaskAnalytics, JobSummary, AnalyticsSummary, AnalyticsResponse

def calculate_job_metrics(job: JobAnalytics, db: Session) -> JobSummary:
    """
    Calculate metrics for a single job.
    
    Args:
        job: JobAnalytics object
        db: Database session
        
    Returns:
        JobSummary: Calculated job metrics
    """
    tasks = db.query(TaskAnalytics).filter(TaskAnalytics.job_id == job.job_id).all()
    task_count = len(tasks)
    failed_tasks = sum(1 for t in tasks if not t.successful)
    success_rate = round(100 * (task_count - failed_tasks) / task_count, 2) if task_count else 0.0
    
    duration = None
    if job.start_time and job.end_time:
        start_dt = datetime.fromisoformat(job.start_time.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(job.end_time.replace("Z", "+00:00"))
        duration = int((end_dt - start_dt).total_seconds())

    return JobSummary(
        job_id=job.job_id,
        user=job.user,
        start_time=job.start_time,
        end_time=job.end_time,
        status=job.status,
        task_count=task_count,
        failed_tasks=failed_tasks,
        success_rate=success_rate,
        duration_seconds=duration
    )

def get_jobs_for_date_range(db: Session, start_date: datetime, end_date: datetime) -> List[JobAnalytics]:
    """
    Retrieve jobs within a date range.
    
    Args:
        db: Database session
        start_date: Start of date range
        end_date: End of date range
        
    Returns:
        List[JobAnalytics]: List of jobs in the date range
    """
    return db.query(JobAnalytics).filter(
        JobAnalytics.start_time >= start_date.isoformat(),
        JobAnalytics.start_time < end_date.isoformat()
    ).all()

def calculate_summary_metrics(job_summaries: List[JobSummary]) -> AnalyticsSummary:
    """
    Calculate summary metrics from a list of job summaries.
    
    Args:
        job_summaries: List of job summaries
        
    Returns:
        AnalyticsSummary: Calculated summary metrics
    """
    total_jobs = len(job_summaries)
    if not total_jobs:
        return AnalyticsSummary(
            total_jobs=0,
            total_tasks=0,
            failed_tasks=0,
            avg_success_rate=0.0,
            avg_duration_seconds=0.0
        )

    total_tasks = sum(js.task_count for js in job_summaries)
    failed_tasks = sum(js.failed_tasks for js in job_summaries)
    avg_success_rate = round(sum(js.success_rate for js in job_summaries) / total_jobs, 2)
    
    # Calculate average duration excluding None values
    durations = [js.duration_seconds for js in job_summaries if js.duration_seconds is not None]
    avg_duration = round(sum(durations) / len(durations), 2) if durations else 0.0

    return AnalyticsSummary(
        total_jobs=total_jobs,
        total_tasks=total_tasks,
        failed_tasks=failed_tasks,
        avg_success_rate=avg_success_rate,
        avg_duration_seconds=avg_duration
    )

def get_analytics_summary_data(db: Session, date: str) -> AnalyticsResponse:
    """
    Get analytics summary data for a specific date.
    
    Args:
        db: Database session
        date: Date string in YYYY-MM-DD format
        
    Returns:
        AnalyticsResponse: Analytics data for the specified date
    """
    try:
        query_date = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise ValueError("Invalid date format. Use YYYY-MM-DD")

    next_day = query_date + timedelta(days=1)
    jobs = get_jobs_for_date_range(db, query_date, next_day)
    
    if not jobs:
        return AnalyticsResponse(
            date=date,
            summary=AnalyticsSummary(
                total_jobs=0,
                total_tasks=0,
                failed_tasks=0,
                avg_success_rate=0.0,
                avg_duration_seconds=0.0
            ),
            jobs=[]
        )
    
    job_summaries = [calculate_job_metrics(job, db) for job in jobs]
    summary = calculate_summary_metrics(job_summaries)
    
    return AnalyticsResponse(
        date=date,
        summary=summary,
        jobs=job_summaries
    )

import logging
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from models.logs import JobAnalytics, TaskAnalytics, JobSummary, AnalyticsSummary, AnalyticsResponse

# Configure logging
logger = logging.getLogger(__name__)

logger.setLevel(logging.INFO)

# Create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
# Create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
# Add the handlers to the logger
logger.addHandler(ch)

def calculate_job_metrics(job: JobAnalytics, db: Session) -> Optional[JobSummary]:
    """
    Calculate metrics for a single job.
    
    Args:
        job: JobAnalytics object
        db: Database session
        
    Returns:
        Optional[JobSummary]: Calculated job metrics or None if calculation fails
    """
    try:
        logger.info(f"Calculating metrics for job_id: {job.job_id}")
        
        # Log job details
        logger.debug(f"Job details - ID: {job.job_id}, User: {job.user}, Status: {job.status}")
        
        # Query tasks for the job
        tasks = db.query(TaskAnalytics).filter(TaskAnalytics.job_id == job.job_id).all()
        task_count = len(tasks)
        failed_tasks = sum(1 for t in tasks if not t.successful)
        
        logger.debug(f"Found {task_count} tasks with {failed_tasks} failed tasks")
        
        # Calculate success rate with safe division
        success_rate = 0.0
        if task_count > 0:
            success_rate = round(100 * (task_count - failed_tasks) / task_count, 2)
        
        # Calculate duration if both start and end times are available
        duration = None
        if job.start_time and job.end_time:
            try:
                start_dt = datetime.fromisoformat(job.start_time.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(job.end_time.replace("Z", "+00:00"))
                duration = int((end_dt - start_dt).total_seconds())
                logger.debug(f"Job duration: {duration} seconds")
            except Exception as e:
                logger.error(f"Error calculating duration for job {job.job_id}: {str(e)}")
                logger.debug(f"start_time: {job.start_time}, end_time: {job.end_time}")
        else:
            logger.warning(f"Missing time data for job {job.job_id} - start_time: {job.start_time}, end_time: {job.end_time}")
        
        # Create and return job summary
        job_summary = JobSummary(
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
        
        logger.info(f"Successfully calculated metrics for job_id: {job.job_id}")
        return job_summary
        
    except Exception as e:
        logger.error(f"Error calculating metrics for job {job.job_id if job else 'unknown'}: {str(e)}", exc_info=True)
        return None

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
    try:
        logger.info(f"Fetching jobs between {start_date.isoformat()} and {end_date.isoformat()}")
        
        # Validate input dates
        if start_date > end_date:
            logger.warning(f"Start date {start_date} is after end date {end_date}")
            return []
        
        # Execute query
        jobs = db.query(JobAnalytics).filter(
            JobAnalytics.start_time >= start_date.isoformat(),
            JobAnalytics.start_time < end_date.isoformat()
        ).all()
        
        logger.info(f"Found {len(jobs)} jobs in the specified date range")
        return jobs
        
    except Exception as e:
        logger.error(f"Error fetching jobs from database: {str(e)}", exc_info=True)
        # Return empty list on error to prevent cascading failures
        return []

def calculate_summary_metrics(job_summaries: List[JobSummary]) -> AnalyticsSummary:
    """
    Calculate summary metrics from a list of job summaries.
    
    Args:
        job_summaries: List of job summaries
        
    Returns:
        AnalyticsSummary: Calculated summary metrics
    """
    logger.info(f"Calculating summary metrics for {len(job_summaries)} jobs")
    
    total_jobs = len(job_summaries)
    if not total_jobs:
        logger.info("No job summaries provided, returning empty summary")
        return AnalyticsSummary(
            total_jobs=0,
            total_tasks=0,
            failed_tasks=0,
            avg_success_rate=0.0,
            avg_duration_seconds=0.0
        )

    try:
        # Calculate basic metrics
        total_tasks = sum(js.task_count for js in job_summaries)
        failed_tasks = sum(js.failed_tasks for js in job_summaries)
        
        # Calculate success rate
        success_rates = [js.success_rate for js in job_summaries if js.success_rate is not None]
        avg_success_rate = round(sum(success_rates) / len(success_rates), 2) if success_rates else 0.0
        
        # Calculate average duration excluding None values
        durations = [js.duration_seconds for js in job_summaries if js.duration_seconds is not None]
        avg_duration = round(sum(durations) / len(durations), 2) if durations else 0.0
        
        logger.debug(
            f"Summary - Jobs: {total_jobs}, Tasks: {total_tasks}, "
            f"Failed: {failed_tasks}, Success Rate: {avg_success_rate}%, "
            f"Avg Duration: {avg_duration}s"
        )
        
        return AnalyticsSummary(
            total_jobs=total_jobs,
            total_tasks=total_tasks,
            failed_tasks=failed_tasks,
            avg_success_rate=avg_success_rate,
            avg_duration_seconds=avg_duration
        )
        
    except Exception as e:
        logger.error(f"Error calculating summary metrics: {str(e)}", exc_info=True)
        # Return empty summary on error
        return AnalyticsSummary(
            total_jobs=0,
            total_tasks=0,
            failed_tasks=0,
            avg_success_rate=0.0,
            avg_duration_seconds=0.0
        )

def get_analytics_summary_data(db: Session, date: str) -> AnalyticsResponse:
    """
    Get analytics summary data for a specific date.
    
    Args:
        db: Database session
        date: Date string in YYYY-MM-DD format
        
    Returns:
        AnalyticsResponse: Analytics data for the specified date
        
    Raises:
        ValueError: If the date format is invalid
    """
    logger.info(f"Generating analytics summary for date: {date}")
    
    try:
        # Validate and parse the input date
        try:
            query_date = datetime.strptime(date, "%Y-%m-%d")
            logger.debug(f"Parsed query date: {query_date}")
        except ValueError as e:
            logger.error(f"Invalid date format: {date}. Expected YYYY-MM-DD")
            raise ValueError("Invalid date format. Use YYYY-MM-DD") from e
        
        # Define date range for the query
        next_day = query_date + timedelta(days=1)
        logger.debug(f"Querying jobs between {query_date} and {next_day}")
        
        # Get jobs for the date range
        jobs = get_jobs_for_date_range(db, query_date, next_day)
        
        # Handle case where no jobs are found
        if not jobs:
            logger.info(f"No jobs found for date: {date}")
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
        
        # Calculate metrics for each job
        logger.info(f"Processing {len(jobs)} jobs for analytics summary")
        job_summaries = []
        for job in jobs:
            summary = calculate_job_metrics(job, db)
            if summary:  # Only include valid summaries
                job_summaries.append(summary)
        
        # Calculate overall summary
        summary = calculate_summary_metrics(job_summaries)
        logger.info(f"Generated summary for {len(job_summaries)} jobs: {summary}")
        
        # Prepare and return the response
        response = AnalyticsResponse(
            date=date,
            summary=summary,
            jobs=job_summaries
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error generating analytics summary for date {date}: {str(e)}", exc_info=True)
        # Return empty response on error
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

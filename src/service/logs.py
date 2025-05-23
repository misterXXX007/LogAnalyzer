import logging
from typing import Dict, Any, Optional, List, Union
from starlette.responses import JSONResponse
from database.sqlite import SessionLocal
from models.logs import RawLog, JobAnalytics, TaskAnalytics
from utils.logs import get_analytics_summary_data

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

def handle_ingest_log(log: Dict[str, Any]) -> Optional[JSONResponse]:
    """
    Handle incoming log ingestion request.
    
    Args:
        log: Dictionary containing log data
        
    Returns:
        JSONResponse: If there's an error, None otherwise
    """
    logger.info(f"Processing log ingestion for job_id: {log.get('job_id')}, event: {log.get('event')}")
    db = SessionLocal()
    try:
        # Check for idempotency
        error = check_idempotency(log, db)
        if error:
            logger.warning(f"Idempotency check failed: {error.status_code} - {error.body.decode()}")
            return error
            
        # Save raw log
        db_log = RawLog(job_id=log["job_id"], event=log["event"], payload=log)
        db.add(db_log)
        db.commit()
        logger.info(f"Successfully saved raw log for job_id: {log.get('job_id')}")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error processing log ingestion: {str(e)}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error while processing log"}
        )
    finally:
        db.close()
    return None

def check_idempotency(log: Dict[str, Any], db) -> Optional[JSONResponse]:
    """
    Check for duplicate or conflicting log entries.
    
    Args:
        log: Dictionary containing log data
        db: Database session
        
    Returns:
        JSONResponse: If idempotency check fails, None otherwise
    """
    event_type = log.get("event")
    job_id = log.get("job_id")
    
    logger.debug(f"Checking idempotency for job_id: {job_id}, event: {event_type}")
    
    try:
        if event_type == "SparkListenerJobStart":
            job = db.query(JobAnalytics).filter(JobAnalytics.job_id == job_id).first()
            if job and job.status == "processing":
                logger.warning(f"Duplicate job start for job_id: {job_id}")
                return JSONResponse(
                    status_code=400,
                    content={"error": "Job is already being processed"}
                )

        elif event_type == "SparkListenerJobEnd":
            job = db.query(JobAnalytics).filter(JobAnalytics.job_id == job_id).first()
            if job and job.status == "success":
                logger.warning(f"Duplicate job end for completed job_id: {job_id}")
                return JSONResponse(
                    status_code=400,
                    content={"error": "Job has already completed successfully"}
                )

        elif event_type == "SparkListenerTaskEnd":
            task_id = log.get("task_id")
            if task_id and db.query(TaskAnalytics).filter(TaskAnalytics.task_id == task_id).first():
                logger.warning(f"Duplicate task end for task_id: {task_id}")
                return JSONResponse(
                    status_code=400,
                    content={"error": "Task has already been processed"}
                )
                
    except Exception as e:
        logger.error(f"Error during idempotency check: {str(e)}", exc_info=True)
        # Don't fail the request if idempotency check itself fails
        
    return None

def get_analytics_summary_service(date: str) -> Dict[str, Any]:
    """
    Get analytics summary for a specific date.
    
    Args:
        date: Date string in YYYY-MM-DD format
        
    Returns:
        Dictionary containing analytics data
    """
    logger.info(f"Fetching analytics summary for date: {date}")
    db = SessionLocal()
    try:
        result = get_analytics_summary_data(db, date)
        logger.info(f"Successfully retrieved analytics for {date}")
        return result
    except Exception as e:
        logger.error(f"Error fetching analytics for date {date}: {str(e)}", exc_info=True)
        return {"error": "Failed to fetch analytics data"}
    finally:
        db.close()

def process_raw_logs() -> List[Dict[str, Any]]:
    """
    Process all unprocessed raw logs.
    
    Returns:
        List of processing results
    """
    logger.info("Starting raw log processing")
    db = SessionLocal()
    analytics_results = []
    processed_count = 0
    error_count = 0
    
    try:
        # Get all unprocessed logs
        logs = db.query(RawLog).filter(RawLog.processed == False).all()
        total_logs = len(logs)
        logger.info(f"Found {total_logs} unprocessed logs")
        
        if not total_logs:
            return []
            
        # Process each log
        for log in logs:
            try:
                result = process_log_entry(log, db)
                if result:
                    analytics_results.append(result)
                log.processed = True
                processed_count += 1
                
                # Log progress periodically
                if processed_count % 10 == 0:
                    logger.info(f"Processed {processed_count}/{total_logs} logs")
                    
            except Exception as e:
                error_count += 1
                log.processed = True  # Mark as processed to prevent infinite retries
                logger.error(f"Error processing log ID {log.id}: {str(e)}", exc_info=True)
                
        # Commit all changes
        db.commit()
        
        # Log summary
        success_rate = (processed_count / total_logs * 100) if total_logs > 0 else 0
        logger.info(
            f"Completed log processing. "
            f"Total: {total_logs}, "
            f"Processed: {processed_count}, "
            f"Errors: {error_count}, "
            f"Success rate: {success_rate:.2f}%"
        )
        
    except Exception as e:
        db.rollback()
        logger.critical(f"Critical error during log processing: {str(e)}", exc_info=True)
    finally:
        db.close()
        
    return analytics_results

def process_log_entry(log: RawLog, db) -> Optional[Dict[str, Any]]:
    """
    Process a single log entry and update the database accordingly.
    
    Args:
        log: RawLog object to process
        db: Database session
        
    Returns:
        Dictionary with processing results or None if not processed
    """
    data = log.payload
    event_type = data.get("event")
    job_id = log.job_id
    
    logger.debug(f"Processing log entry - ID: {log.id}, Job: {job_id}, Event: {event_type}")
    
    try:
        if event_type == "SparkListenerJobStart":
            return _process_job_start(log, data, db)
            
        elif event_type == "SparkListenerJobEnd":
            return _process_job_end(log, data, db)
            
        elif event_type == "SparkListenerTaskEnd":
            return _process_task_end(log, data, db)
            
        else:
            logger.warning(f"Unhandled event type: {event_type}")
            return None
            
    except Exception as e:
        logger.error(
            f"Error processing log entry ID {log.id}, "
            f"Job: {job_id}, Event: {event_type}: {str(e)}",
            exc_info=True
        )
        raise  # Re-raise to be handled by the caller


def _process_job_start(log: RawLog, data: Dict[str, Any], db) -> Dict[str, Any]:
    """Process a job start event."""
    job_id = log.job_id
    logger.info(f"Processing job start - Job ID: {job_id}")
    
    job = db.query(JobAnalytics).filter(JobAnalytics.job_id == job_id).first()
    
    if not job:
        logger.debug(f"Creating new job entry for job_id: {job_id}")
        job = JobAnalytics(
            job_id=job_id,
            user=data.get("user"),
            start_time=data.get("timestamp"),
            status="processing"
        )
    else:
        logger.debug(f"Updating existing job entry for job_id: {job_id}")
        job.user = data.get("user")
        job.start_time = data.get("timestamp")
        if not job.status:
            job.status = "processing"
    
    db.merge(job)
    logger.info(f"Successfully processed job start for job_id: {job_id}")
    
    return {
        "job_id": job_id,
        "user": job.user,
        "start_time": job.start_time,
        "status": job.status,
        "event": "job_start_processed"
    }


def _process_job_end(log: RawLog, data: Dict[str, Any], db) -> Dict[str, Any]:
    """Process a job end event."""
    job_id = log.job_id
    logger.info(f"Processing job end - Job ID: {job_id}")
    
    job = db.query(JobAnalytics).filter(JobAnalytics.job_id == job_id).first()
    
    if not job:
        logger.warning(f"Job end received for non-existent job_id: {job_id}, creating entry")
        job = JobAnalytics(job_id=job_id)
    
    # Update job end time and status
    end_time = data.get("completion_time", data.get("timestamp"))
    status = "success" if data.get("job_result") == "JobSucceeded" else "failure"
    
    job.end_time = end_time
    job.status = status
    
    db.merge(job)
    logger.info(f"Job {job_id} marked as {status} at {end_time}")
    
    return {
        "job_id": job_id,
        "end_time": end_time,
        "status": status,
        "event": "job_end_processed"
    }


def _process_task_end(log: RawLog, data: Dict[str, Any], db) -> Dict[str, Any]:
    """Process a task end event."""
    job_id = log.job_id
    task_id = data.get("task_id")
    
    if not task_id:
        logger.error("Task end event received without task_id")
        raise ValueError("task_id is required for task end events")
    
    logger.debug(f"Processing task end - Job: {job_id}, Task: {task_id}")
    
    # Check if task already exists
    task = db.query(TaskAnalytics).filter(
        TaskAnalytics.task_id == task_id,
        TaskAnalytics.job_id == job_id
    ).first()
    
    if not task:
        logger.debug(f"Creating new task entry for task_id: {task_id}")
        task = TaskAnalytics(
            task_id=task_id,
            job_id=job_id
        )
    
    # Update task details
    timestamp = data.get("timestamp")
    duration = data.get("duration_ms")
    successful = data.get("successful", True)
    
    task.timestamp = timestamp
    task.duration_ms = duration
    task.successful = successful
    
    db.merge(task)
    logger.debug(f"Processed task end - Task: {task_id}, Duration: {duration}ms, Success: {successful}")
    
    return {
        "job_id": job_id,
        "task_id": task_id,
        "timestamp": timestamp,
        "duration_ms": duration,
        "successful": successful,
        "event": "task_end_processed"
    }

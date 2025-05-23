import logging
import time
import uuid
from typing import Dict, Any, Optional, Union
from fastapi import APIRouter, Request, Query, status, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime
from celery.result import AsyncResult

from models.logs import AnalyticsResponse
from tasks.processor import process_logs
from service.logs import get_analytics_summary_service, handle_ingest_log

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

router = APIRouter(
    tags=["logs"],
    responses={
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "Internal server error"}
    }
)

@router.post(
    "/logs/ingest",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest log data",
    response_description="Log ingestion initiated"
)
async def ingest_log(request: Request) -> Dict[str, Any]:
    """
    Ingest log data for processing.
    
    This endpoint accepts log data in JSON format and initiates asynchronous processing.
    
    Args:
        request: The incoming HTTP request containing log data
        
    Returns:
        Dict containing status and task ID for tracking
        
    Raises:
        HTTPException: If there's an error processing the request
    """
    start_time = time.time()
    
    logger.info(f"Received log ingestion request")
    
    try:
        # Parse request body
        log = await request.json()
        logger.debug("Parsed request data")
        
        # Handle log ingestion
        error_response = handle_ingest_log(log)
        if error_response:
            logger.warning(
                f"Log ingestion validation failed: "
                f"{error_response.status_code} - {error_response.body.decode()}"
            )
            return error_response
        
        # Start async processing
        task = process_logs.delay()
        task_id = str(task)
        
        logger.info(
            f"Successfully queued log for processing. "
            f"Task ID: {task_id}"
        )
        
        # Log performance
        duration = (time.time() - start_time) * 1000  # Convert to milliseconds
        logger.debug(f"Request processed in {duration:.2f}ms")
        
        return {
            "status": "accepted",
            "task_id": task_id
        }
        
    except Exception as e:
        logger.error(
            f"Error processing log ingestion: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing your request"
        )

@router.get(
    "/analytics/jobs/{job_id}",
    summary="Get job analytics by ID",
    response_description="Job analytics data"
)
async def get_job_analytics(
    job_id: str,
    request: Request
) -> Dict[str, Any]:
    """
    Retrieve analytics for a specific job by its ID.
    
    Args:
        job_id: The ID of the job to retrieve analytics for
        request: The incoming HTTP request
        
    Returns:
        Dict containing job analytics data or processing status
        
    Raises:
        HTTPException: If the job is not found or an error occurs
    """
    logger.info(f"Fetching analytics for job: {job_id}")
    
    try:
        # Get task status
        task = AsyncResult(str(job_id))
        
        # If task is still processing
        if not task.ready():
            logger.info(f"Job {job_id} is still processing")
            return JSONResponse(
                status_code=status.HTTP_202_ACCEPTED,
                content={
                    "task_id": str(job_id),
                    "status": "processing"
                },
            )
        
        # Get task result
        logger.debug(f"Retrieving result for job: {job_id}")
        result = task.get()
        
        logger.info(f"Successfully retrieved analytics for job: {job_id}")
        return {
            "task_id": job_id,
            "status": "success",
            "result": result
        }
        
    except Exception as e:
        logger.error(
            f"Error fetching analytics for job {job_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving job analytics: {str(e)}"
        )
    

@router.get(
    "/analytics/summary",
    response_model=AnalyticsResponse,
    summary="Get analytics summary for a date",
    response_description="Analytics summary data"
)
async def get_analytics_summary(
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
) -> Union[AnalyticsResponse, JSONResponse]:
    """
    Get analytics summary for a specific date.
    
    Args:
        date: The date to get analytics for (format: YYYY-MM-DD)
        
    Returns:
        Analytics summary data for the specified date
        
    Raises:
        HTTPException: If the date format is invalid or an error occurs
    """
    logger.info(f"Fetching analytics summary for date: {date}")
    
    # Validate date format
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError as e:
        error_msg = f"Invalid date format: {date}. Use YYYY-MM-DD"
        logger.warning(f"{error_msg}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": error_msg}
        )
    
    try:
        start_time = time.time()
        logger.debug(f"Starting to process analytics for {date}")
        
        # Get analytics data
        result = get_analytics_summary_service(date)
        
        # Log performance
        duration = (time.time() - start_time) * 1000  # Convert to milliseconds
        logger.info(
            f"Successfully retrieved analytics for {date} "
            f"in {duration:.2f}ms"
        )
        
        return result
        
    except HTTPException as he:
        # Re-raise HTTP exceptions as-is
        logger.warning(
            f"HTTP error in analytics summary for {date}: "
            f"{he.status_code} - {he.detail}"
        )
        raise
    except Exception as e:
        error_msg = f"Error generating analytics summary: {str(e)}"
        logger.error(
            f"{error_msg}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": error_msg}
        )

@router.get(
    "/health",
    summary="Health check endpoint",
    response_description="Service health status"
)
async def health_check() -> Dict[str, str]:
    """
    Health check endpoint to verify the service is running.
    
    Returns:
        Dict containing the service status
    """
    logger.debug("Health check request received")
    return {
        "status": "ok",
        "service": "Log Analytics API",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

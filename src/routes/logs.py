from fastapi import APIRouter
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi import Query
from models.logs import AnalyticsResponse
from tasks.processor import process_logs
from datetime import datetime
from celery.result import AsyncResult
from service.logs import get_analytics_summary_service, handle_ingest_log

router = APIRouter()

# Logs ingestion endpoint
@router.post("/ingest")
async def ingest_log(request: Request):
    
    log = await request.json()
    error_response = handle_ingest_log(log)

    if error_response:
        return error_response

    taskid = process_logs.delay()
    return {"status": "received", "task_id": str(taskid)}

# Analytics query endpoint
@router.get("/jobs/{job_id}")
def get_job_analytics(job_id: str):
    task = AsyncResult(str(job_id))
    if not task.ready():
        return JSONResponse(
            status_code=202,
            content={"task_id": str(job_id), "status": "Processing"},
        )
    result = task.get()
    return {"task_id": job_id, "status": "Success", "result": result}
    

@router.get("/summary", response_model=AnalyticsResponse)
def get_analytics_summary(
    date: str = Query(..., description="Date in YYYY-MM-DD format")
):
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return JSONResponse(status_code=400, content={"error": "Invalid date format. Use YYYY-MM-DD"})

    try:
        return get_analytics_summary_service(date)
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# Root endpoint
@router.get("/health")
async def root():
    return {"status": "ok"}

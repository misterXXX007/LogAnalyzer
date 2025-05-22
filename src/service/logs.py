from starlette.responses import JSONResponse
from database.sqlite import SessionLocal
from models.logs import RawLog
from models.logs import JobAnalytics, TaskAnalytics
from utils.logs import get_analytics_summary_data

def handle_ingest_log(log: dict):
    db = SessionLocal()
    try:
        error = check_idempotency(log, db)
        if error:
            return error
        # Save raw log
        db_log = RawLog(job_id=log["job_id"], event=log["event"], payload=log)
        db.add(db_log)
        db.commit()
    finally:
        db.close()
    return None

def check_idempotency(log: dict, db):
    if log["event"] == "SparkListenerJobStart":
        job = db.query(JobAnalytics).filter(JobAnalytics.job_id == log["job_id"]).first()
        if job and job.status == "processing":
            return JSONResponse(status_code=400, content={"error": "Job ID already exists"})

    elif log["event"] == "SparkListenerJobEnd":
        job = db.query(JobAnalytics).filter(JobAnalytics.job_id == log["job_id"]).first()
        if job and job.status == "success":
            return JSONResponse(status_code=400, content={"error": "Job ID already exists"})

    elif log["event"] == "SparkListenerTaskEnd":
        if db.query(TaskAnalytics).filter(TaskAnalytics.task_id == log["task_id"]).first():
            return JSONResponse(status_code=400, content={"error": "Job ID already exists"})

    return None

def get_analytics_summary_service(date:str):
    db = SessionLocal()
    try:
        return get_analytics_summary_data(db, date)
    finally:
        db.close()

def process_raw_logs():
    db = SessionLocal()
    analytics_results = []
    try:
        logs = db.query(RawLog).filter(RawLog.processed == False).all()

        for log in logs:
            try:
                result = process_log_entry(log, db)
                if result:
                    analytics_results.append(result)
                log.processed = True  # Mark log as processed after successful handling
            except Exception as e:
                print(f"Error processing log {log.id}: {e}")

        db.commit()
    finally:
        db.close()
    return analytics_results


def process_log_entry(log, db):
    data = log.payload
    event_type = data.get("event")
    job_id = log.job_id

    if event_type == "SparkListenerJobStart":
        job = db.query(JobAnalytics).filter(JobAnalytics.job_id == job_id).first()
        if not job:
            job = JobAnalytics(
                job_id=job_id,
                user=data.get("user"),
                start_time=data.get("timestamp"),
                status="processing"
            )
        else:
            job.user = data.get("user")
            job.start_time = data.get("timestamp")
            if not job.status:
                job.status = "processing"
        db.merge(job)

        return {
            "job_id": job_id,
            "user": job.user,
            "start_time": job.start_time,
            "status": job.status
        }

    elif event_type == "SparkListenerJobEnd":
        job = db.query(JobAnalytics).filter(JobAnalytics.job_id == job_id).first()
        if not job:
            job = JobAnalytics(job_id=job_id)
        job.end_time = data.get("completion_time", data.get("timestamp"))
        job.status = "success" if data.get("job_result") == "JobSucceeded" else "failure"
        db.merge(job)

        return {
            "job_id": job_id,
            "end_time": job.end_time,
            "status": job.status
        }

    elif event_type == "SparkListenerTaskEnd":
        task_id = data.get("task_id")
        task = db.query(TaskAnalytics).filter(
            TaskAnalytics.task_id == task_id,
            TaskAnalytics.job_id == job_id
        ).first()
        if not task:
            task = TaskAnalytics(
                task_id=task_id,
                job_id=job_id
            )
        task.timestamp = data.get("timestamp")
        task.duration_ms = data.get("duration_ms")
        task.successful = data.get("successful", True)
        db.merge(task)

        return {
            "job_id": job_id,
            "task_id": task.task_id,
            "timestamp": task.timestamp,
            "duration_ms": task.duration_ms,
            "successful": task.successful
        }

    return None

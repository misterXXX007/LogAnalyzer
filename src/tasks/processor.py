from celery import Task
from celery_worker import celery_app
from service.logs import process_raw_logs


class ProcessLog(Task):
    abstract = True

    def __init__(self):
        super().__init__()

    def __call__(self, *args, **kwargs):
        return self.run(*args, **kwargs)


@celery_app.task(
    ignore_result=False,
    bind=True,
    base=ProcessLog,
    name="processor.process_logs"
)
def process_logs(self):
    analytics_data = process_raw_logs()
    if not analytics_data:
        return {"status": "empty"}
    return {"job_id": analytics_data[0]["job_id"], "status": "success", "result": analytics_data[0]}
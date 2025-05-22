import os
from celery import Celery
from dotenv import load_dotenv

load_dotenv("../.env")

celery_app = Celery(
    "celery_app",
    broker=os.environ.get("CELERY_BROKER_URL"),
    backend=os.environ.get("CELERY_RESULT_BACKEND"),
    include=["tasks.processor"]
)

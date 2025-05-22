from fastapi import FastAPI

from routes import logs

app = FastAPI()

app.include_router(prefix="/logs", router=logs.router)


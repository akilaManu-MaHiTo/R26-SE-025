from fastapi import FastAPI

from app.api.dashboard import router as dashboard_router
from app.api.lecturer import router as lecturer_router

app = FastAPI(title="DBMS Analytics API", version="1.0.0")
app.include_router(dashboard_router, prefix="/api")
app.include_router(lecturer_router, prefix="/api")
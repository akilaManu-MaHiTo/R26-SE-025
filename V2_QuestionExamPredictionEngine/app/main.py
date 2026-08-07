from fastapi import FastAPI

from app.api.dashboard import router as dashboard_router

app = FastAPI(title="DBMS Analytics API", version="1.0.0")
app.include_router(dashboard_router, prefix="/api")
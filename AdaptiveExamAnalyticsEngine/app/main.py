from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.dashboard import router as dashboard_router
from app.api.lecturer import router as lecturer_router

app = FastAPI(title="DBMS Analytics API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard_router, prefix="/api")
app.include_router(lecturer_router, prefix="/api")
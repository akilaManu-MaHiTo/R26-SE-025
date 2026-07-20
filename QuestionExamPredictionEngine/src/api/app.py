import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.config import settings
from src.api.routers import analytics, grading, models, prediction

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)-24s | %(levelname)-5s | %(message)s",
)

description = """
QuestionExamPredictionEngine API

Automated exam grading and student learning analytics for DBMS courses.
- **Grade** student answers using semantic similarity + concept scoring
- **Analyze** exams with weak topic detection, cognitive gap analysis, and more
- **Predict** topics and performance trends across exam years
"""

app = FastAPI(
    title="QuestionExamPredictionEngine",
    description=description,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(models.router)
app.include_router(grading.router)
app.include_router(analytics.router)
app.include_router(prediction.router)


@app.get("/")
def root():
    return {
        "service": "QuestionExamPredictionEngine",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }

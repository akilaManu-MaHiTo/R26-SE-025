import logging
import sys

from fastapi import APIRouter
from pathlib import Path

from src.api.config import settings
from src.api.dependencies import get_similarity_model
from src.api.schemas.responses import HealthResponse, ModelInfo, ModelsListResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Models"])


@router.get("/health", response_model=HealthResponse)
def health_check():
    models = {
        "similarity": settings.similarity_model_path.exists(),
        "weak_topic": settings.weak_topic_model_path.exists(),
        "cognitive_bloom": settings.cognitive_bloom_model_path.exists(),
    }
    return HealthResponse(
        status="ok",
        api_version="1.0.0",
        models_loaded=models,
        python_version=sys.version,
    )


@router.get("/models", response_model=ModelsListResponse)
def list_models():
    models = [
        ModelInfo(
            name="similarity",
            type="SentenceTransformer (MiniLM-L6-v2)",
            path=str(settings.similarity_model_path),
            loaded=settings.similarity_model_path.exists(),
            description="Semantic similarity model for grading student answers",
        ),
        ModelInfo(
            name="weak_topic",
            type="StandardScaler + LogisticRegression",
            path=str(settings.weak_topic_model_path),
            loaded=settings.weak_topic_model_path.exists(),
            description="Weak topic detection classifier",
        ),
        ModelInfo(
            name="cognitive_bloom",
            type="TF-IDF + LogisticRegression",
            path=str(settings.cognitive_bloom_model_path),
            loaded=settings.cognitive_bloom_model_path.exists(),
            description="Bloom's taxonomy cognitive level classifier",
        ),
    ]
    return ModelsListResponse(models=models)


@router.get("/models/load/similarity", response_model=dict)
def load_similarity_model():
    try:
        get_similarity_model()
        return {"status": "loaded", "path": str(settings.similarity_model_path)}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

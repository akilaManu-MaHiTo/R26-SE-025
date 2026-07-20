import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException, status

from src.api.config import settings

logger = logging.getLogger(__name__)


def load_json(path: Path) -> Any:
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {path}",
        )
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Invalid JSON in {path}: {e}",
        )


def get_exam_data(year: Optional[int] = None) -> dict:
    if year:
        path = settings.exams_dir / f"exam{year}.json"
    else:
        path = settings.data_dir / "exam.json"
    return load_json(path)


def get_student_answers(year: Optional[int] = None) -> list[dict]:
    if year:
        path = settings.answers_dir / f"student_answers{year}.json"
    else:
        path = settings.data_dir / "student_answers.json"
    data = load_json(path)
    return data if isinstance(data, list) else [data]


def get_topics() -> list[str]:
    return load_json(settings.topics_path)


def get_model_answer(year: int = 2021) -> dict:
    path = settings.data_dir / "model_answer" / f"model_answer_{year}.json"
    return load_json(path)


@lru_cache(maxsize=1)
def get_similarity_model():
    from sentence_transformers import SentenceTransformer
    logger.info("Loading similarity model from %s", settings.similarity_model_path)
    return SentenceTransformer(str(settings.similarity_model_path))


@lru_cache(maxsize=1)
def get_weak_topic_model():
    from src.analytics.weak_topic_model import WeakTopicModel
    return WeakTopicModel(model_path=settings.weak_topic_model_path)

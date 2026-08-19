from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]

class Settings:
    project_root: Path = PROJECT_ROOT
    data_dir: Path = PROJECT_ROOT / "data"
    exams_dir: Path = data_dir / "exams"
    answers_dir: Path = data_dir / "answers"
    model_dir: Path = PROJECT_ROOT / "model"
    similarity_model_path: Path = model_dir / "similarity" / "exam_similarity_model"
    weak_topic_model_path: Path = model_dir / "weak_topic" / "weak_topic_model.joblib"
    cognitive_bloom_model_path: Path = model_dir / "cognitive_bloom" / "cognitive_bloom_model.joblib"
    topics_path: Path = data_dir / "topics.json"
    output_dir: Path = PROJECT_ROOT / "output"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = ["*"]

    learning_weight_performance: float = 0.6
    learning_weight_concept: float = 0.25
    learning_weight_cognitive: float = 0.15

    weak_threshold: float = 0.5
    weak_min_students: int = 2
    weak_min_below_share: float = 0.4

settings = Settings()

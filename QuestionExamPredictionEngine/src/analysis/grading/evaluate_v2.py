"""Compatibility wrapper for the original v2 grading script."""

from functools import lru_cache
from pathlib import Path

from src.analysis.grading.service import grade_answer as _grade_answer

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODEL_PATH = PROJECT_ROOT / "model" / "similarity" / "exam_similarity_model"


@lru_cache(maxsize=1)
def _get_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(str(MODEL_PATH))


def grade_answer(model_answer, student_answer, max_marks):
    result = _grade_answer(
        _get_model(),
        model_answer,
        student_answer,
        max_marks,
        version="v2",
    )
    return (
        result["similarity"],
        result["concept_score"],
        result["marks_obtained"],
    )


def grade_answer_with_feedback(model_answer, student_answer, max_marks):
    return _grade_answer(
        _get_model(),
        model_answer,
        student_answer,
        max_marks,
        version="v2",
    )


if __name__ == "__main__":
    reference = "ACID stands for Atomicity, Consistency, Isolation, Durability"
    answer = "ACID = Atomicity, Consistency, Isolation, Durability"
    result = grade_answer_with_feedback(reference, answer, 2)
    print(result)

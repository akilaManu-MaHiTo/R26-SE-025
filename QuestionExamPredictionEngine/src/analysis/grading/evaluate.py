"""Compatibility wrapper for the original v1 grading script."""

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
        version="v1",
    )
    return (
        result["similarity"],
        result["concept_score"],
        result["marks_obtained"],
    )


if __name__ == "__main__":
    reference = (
        "Second normal form (2NF) eliminates partial dependencies; a table is "
        "in 2NF if it is in 1NF and all non-key attributes are fully "
        "functionally dependent on the entire primary key"
    )
    answer = "2NF removes transitive dependencies from a table"
    similarity, concept, marks = grade_answer(reference, answer, 2)
    print("Similarity:", similarity)
    print("Concept:", concept)
    print("Marks:", marks)

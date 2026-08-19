"""Shared answer-grading service.

The service owns grading calculations. API and command-line adapters are
responsible only for loading the similarity model and formatting results.
"""

from typing import Any

from src.analysis.scoring.concept_scoring import concept_score, extract_keywords


def semantic_similarity(model: Any, model_answer: str, student_answer: str) -> float:
    """Return cosine similarity for two answers using an encoding model."""
    from sentence_transformers import util

    reference_embedding = model.encode(model_answer, convert_to_tensor=True)
    student_embedding = model.encode(student_answer, convert_to_tensor=True)
    return float(util.cos_sim(reference_embedding, student_embedding))


def _feedback(concept: float, similarity: float) -> str:
    if concept >= 0.8:
        message = "Excellent! You have a strong understanding of the concept."
    elif concept >= 0.6:
        message = "Good understanding, but there are minor gaps in your knowledge."
    elif concept >= 0.4:
        message = "Fair understanding. Review the key concepts and try again."
    elif concept >= 0.2:
        message = "Weak understanding. Major conceptual errors detected."
    else:
        message = "Poor understanding. Please thoroughly review this topic."

    if similarity > 0.7 and concept < 0.4:
        message += (
            " Note: Your answer sounds correct but is conceptually wrong. "
            "Focus on understanding concepts, not just memorizing phrases."
        )
    return message


def grade_answer(
    model: Any,
    model_answer: str,
    student_answer: str,
    max_marks: float,
    version: str = "v2",
) -> dict:
    """Grade one answer with the requested scoring policy."""
    if max_marks <= 0:
        raise ValueError("max_marks must be greater than zero")
    if version not in {"v1", "v2"}:
        raise ValueError(f"Unsupported grading version: {version}")

    similarity = semantic_similarity(model, model_answer, student_answer)
    keywords = extract_keywords(model_answer)
    concept = concept_score(student_answer, keywords)

    if version == "v1":
        normalized_score = (0.6 * similarity) + (0.4 * concept)
        feedback = None
    else:
        if concept < 0.2:
            penalty = 0.3
        elif concept < 0.4:
            penalty = 0.6
        elif concept < 0.6:
            penalty = 0.85
        else:
            penalty = 1.0

        normalized_score = ((0.3 * similarity) + (0.7 * concept)) * penalty
        feedback = _feedback(concept, similarity)

    normalized_score = min(max(normalized_score, 0.0), 1.0)
    marks = round(normalized_score * max_marks, 2)

    result = {
        "similarity": round(similarity, 4),
        "concept_score": round(concept, 4),
        "marks_obtained": marks,
        "max_marks": max_marks,
        "percentage": round((marks / max_marks) * 100, 2),
    }
    if feedback is not None:
        result["feedback"] = feedback
    return result

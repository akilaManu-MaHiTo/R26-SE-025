import logging

from fastapi import APIRouter, HTTPException, status

from src.api.dependencies import get_similarity_model
from src.api.dependencies import get_similarity_model
from src.api.schemas.requests import GradeBatchRequest, GradeRequest
from src.api.schemas.responses import GradeBatchResponse, GradeResponse, GradeWithFeedbackResponse
from src.analysis.scoring.concept_scoring import concept_score, extract_keywords

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/grade", tags=["Grading"])


def _grade_v1(model_answer: str, student_answer: str, max_marks: float) -> GradeResponse:
    model = get_similarity_model()
    from sentence_transformers import util

    emb1 = model.encode(model_answer, convert_to_tensor=True)
    emb2 = model.encode(student_answer, convert_to_tensor=True)
    similarity = float(util.cos_sim(emb1, emb2))

    keywords = extract_keywords(model_answer)
    concept = concept_score(student_answer, keywords)

    final = 0.6 * similarity + 0.4 * concept
    marks = round(final * max_marks, 2)

    return GradeResponse(
        similarity=round(similarity, 4),
        concept_score=round(concept, 4),
        marks_obtained=marks,
        max_marks=max_marks,
        percentage=round(marks / max_marks * 100, 2),
    )


def _grade_v2(model_answer: str, student_answer: str, max_marks: float) -> GradeWithFeedbackResponse:
    model = get_similarity_model()
    from sentence_transformers import util

    emb1 = model.encode(model_answer, convert_to_tensor=True)
    emb2 = model.encode(student_answer, convert_to_tensor=True)
    similarity = float(util.cos_sim(emb1, emb2))

    keywords = extract_keywords(model_answer)
    concept = concept_score(student_answer, keywords)

    if concept < 0.2:
        penalty = 0.3
        feedback = "Poor understanding. Please thoroughly review this topic."
    elif concept < 0.4:
        penalty = 0.6
        feedback = "Weak understanding. Major conceptual errors detected."
    elif concept < 0.6:
        penalty = 0.85
        feedback = "Fair understanding. Review the key concepts and try again."
    else:
        penalty = 1.0
        feedback = "Good understanding, but there are minor gaps in your knowledge."

    if concept >= 0.8:
        feedback = "Excellent! You have a strong understanding of the concept."

    raw_score = (0.3 * similarity + 0.7 * concept) * penalty
    final_score = min(raw_score, 1.0)
    marks = round(final_score * max_marks, 2)

    if similarity > 0.7 and concept < 0.4:
        feedback += " Note: Your answer sounds correct but is conceptually wrong. Focus on understanding concepts, not just memorizing phrases."

    return GradeWithFeedbackResponse(
        similarity=round(similarity, 4),
        concept_score=round(concept, 4),
        marks_obtained=marks,
        max_marks=max_marks,
        percentage=round(marks / max_marks * 100, 2),
        feedback=feedback,
    )


@router.post("", response_model=GradeResponse)
def grade_single(req: GradeRequest):
    try:
        if req.version == "v2":
            return _grade_v2(req.model_answer, req.student_answer, req.max_marks)
        return _grade_v1(req.model_answer, req.student_answer, req.max_marks)
    except Exception as e:
        logger.exception("Grading failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/batch", response_model=GradeBatchResponse)
def grade_batch(req: GradeBatchRequest):
    results = []
    for item in req.items:
        if req.version == "v2":
            r = _grade_v2(item.model_answer, item.student_answer, item.max_marks)
        else:
            r = _grade_v1(item.model_answer, item.student_answer, item.max_marks)
        results.append(r)
    return GradeBatchResponse(results=results)


@router.post("/with-feedback", response_model=GradeWithFeedbackResponse)
def grade_with_feedback(req: GradeRequest):
    return _grade_v2(req.model_answer, req.student_answer, req.max_marks)

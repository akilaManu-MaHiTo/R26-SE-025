import logging

from fastapi import APIRouter, HTTPException, status

from src.analysis.grading.service import grade_answer
from src.api.dependencies import get_similarity_model
from src.api.schemas.requests import GradeBatchRequest, GradeRequest
from src.api.schemas.responses import (
    GradeBatchResponse,
    GradeResponse,
    GradeWithFeedbackResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/grade", tags=["Grading"])


def _grade(
    model_answer: str,
    student_answer: str,
    max_marks: float,
    version: str,
) -> GradeResponse:
    result = grade_answer(
        get_similarity_model(),
        model_answer,
        student_answer,
        max_marks,
        version=version,
    )
    if version == "v2":
        return GradeWithFeedbackResponse(**result)
    return GradeResponse(**result)


@router.post("", response_model=GradeResponse)
def grade_single(req: GradeRequest):
    try:
        return _grade(
            req.model_answer,
            req.student_answer,
            req.max_marks,
            req.version,
        )
    except Exception as exc:
        logger.exception("Grading failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.post("/batch", response_model=GradeBatchResponse)
def grade_batch(req: GradeBatchRequest):
    try:
        return GradeBatchResponse(results=[
            _grade(
                item.model_answer,
                item.student_answer,
                item.max_marks,
                req.version,
            )
            for item in req.items
        ])
    except Exception as exc:
        logger.exception("Batch grading failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.post("/with-feedback", response_model=GradeWithFeedbackResponse)
def grade_with_feedback(req: GradeRequest):
    try:
        return _grade(
            req.model_answer,
            req.student_answer,
            req.max_marks,
            "v2",
        )
    except Exception as exc:
        logger.exception("Grading with feedback failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

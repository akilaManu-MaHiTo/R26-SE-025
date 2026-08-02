import logging

from fastapi import APIRouter, HTTPException, status

from src.api.dependencies import (
    get_agent_orchestrator,
    get_exam_data,
    get_model_answer,
    get_student_answers,
)
from src.api.schemas.requests import AgentWorkflowAnalyzeExamRequest
from src.api.schemas.responses import AgentWorkflowAnalyzeExamResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agent-workflows", tags=["Agent Workflows"])


@router.post(
    "/analyze-exam",
    response_model=AgentWorkflowAnalyzeExamResponse,
)
def analyze_exam_agent_workflow(req: AgentWorkflowAnalyzeExamRequest):
    try:
        exam_data = get_exam_data(req.year)
        students = get_student_answers(req.year)
        model_answers = get_model_answer(req.year)
        result = get_agent_orchestrator().run(
            exam_data,
            students,
            model_answers,
            req.rubric,
            weak_threshold=req.weak_threshold,
            weak_min_students=req.weak_min_students,
            weak_min_below_share=req.weak_min_below_share,
            performance_weight=req.performance_weight,
            concept_weight=req.concept_weight,
            cognitive_weight=req.cognitive_weight,
        )
        return AgentWorkflowAnalyzeExamResponse(result=result)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Agent workflow failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Agent workflow failed",
        ) from exc

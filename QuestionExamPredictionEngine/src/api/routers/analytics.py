import logging

from fastapi import APIRouter, HTTPException, status

from src.analysis.exam_analysis import analyze_exam_records
from src.analysis.reporting import create_analysis_output_dir, write_analysis_outputs
from src.api.config import settings
from src.api.dependencies import get_exam_data, get_model_answer, get_student_answers
from src.api.schemas.requests import AnalyzeExamRequest
from src.api.schemas.responses import AnalyzeExamResponse, StudentReportRecord

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analyze", tags=["Analytics"])


@router.post("/exam", response_model=AnalyzeExamResponse)
def analyze_exam(req: AnalyzeExamRequest):
    """Analyze one exam year and persist its generated reports."""
    try:
        exam_data = get_exam_data(req.year)
        student_data = get_student_answers(req.year)
        model_answers = get_model_answer(req.year)

        results = analyze_exam_records(
            exam_data,
            student_data,
            model_answers,
            weak_threshold=req.weak_threshold,
            weak_min_students=req.weak_min_students,
            weak_min_below_share=req.weak_min_below_share,
            performance_weight=settings.learning_weight_performance,
            concept_weight=settings.learning_weight_concept,
            cognitive_weight=settings.learning_weight_cognitive,
        )
        output_dir = create_analysis_output_dir(
            settings.output_dir,
            exam_data,
            year=req.year,
        )
        write_analysis_outputs(results, output_dir)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Exam analysis failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    logger.info("Analysis saved to %s", output_dir)
    exam_name = exam_data.get("exam", "PAPERS").replace(" ", "_")
    return AnalyzeExamResponse(
        exam=exam_name,
        year=req.year,
        student_reports=[
            StudentReportRecord(**record)
            for record in results["student_reports"]
        ],
        question_summaries=results["question_summaries"],
        student_summaries=results["student_summaries"],
        misunderstood_questions=results["misunderstood_questions"],
        cognitive_gaps=results["cognitive_gaps"],
        weak_topics=results["weak_topics"],
        output_dir=str(output_dir),
    )

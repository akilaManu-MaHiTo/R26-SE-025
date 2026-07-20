import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from src.api.config import settings
from src.api.dependencies import get_exam_data, get_student_answers
from src.api.schemas.requests import AnalyzeExamRequest
from src.api.schemas.responses import AnalyzeExamResponse, StudentReportRecord
from src.analysis.scoring.cognitive import cognitive_score
from src.analysis.scoring.concept_scoring import concept_score, extract_keywords
from src.analytics.cognitive_gap_analysis import CognitiveGapAnalyzer
from src.analytics.misunderstood_questions import MisunderstoodQuestionsAnalyzer
from src.analytics.student_analysis import analyze_student_performance
from src.analytics.question_analysis import analyze_questions
from src.analytics.topic_utils import resolve_topic
from src.analytics.weak_topic_analysis import WeakTopicAnalyzer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analyze", tags=["Analytics"])


def _get_question_text(exam_data: dict, q_id: str, part_id: str) -> str:
    for q in exam_data.get("questions", []):
        if str(q.get("question_number")) == str(q_id):
            for part in q.get("parts", []):
                if part.get("part") == part_id:
                    return part.get("question", "")
    return ""


@router.post("/exam", response_model=AnalyzeExamResponse)
def analyze_exam(req: AnalyzeExamRequest):
    try:
        exam_data = get_exam_data(req.year)
        student_data = get_student_answers(req.year)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    students = student_data if isinstance(student_data, list) else [student_data]
    student_reports = []
    exam_name = exam_data.get("exam", "PAPERS").replace(" ", "_")
    exam_year = exam_data.get("year", str(req.year))

    for student in students:
        student_id = student.get("student_id", "UNKNOWN")
        year = student.get("year", str(req.year))

        for question in student.get("answers", []):
            q_id = str(question.get("question_number"))
            for part in question.get("parts", []):
                part_id = part.get("part")
                student_answer = part.get("answer", "")

                score = part.get("score", 0)
                max_marks = part.get("max_marks", 1)
                performance_score = score / max_marks if max_marks else 0
                question_text = _get_question_text(exam_data, q_id, part_id)

                keywords = extract_keywords(student_answer)
                concept = concept_score(student_answer, keywords)
                cog = cognitive_score(question_text, student_answer)

                learning_score = round(
                    (settings.learning_weight_performance * performance_score)
                    + (settings.learning_weight_concept * concept)
                    + (settings.learning_weight_cognitive * cog["cognitive_score"]),
                    3,
                )

                topic_key = resolve_topic(exam_data, q_id, part_id, default=f"Q{q_id}{part_id}")

                student_reports.append({
                    "student_id": student_id,
                    "exam": exam_name,
                    "year": str(year),
                    "question": q_id,
                    "part": part_id,
                    "performance_score": round(performance_score, 3),
                    "concept_score": round(concept, 3),
                    "cognitive_score": cog["cognitive_score"],
                    "student_level": cog["student_level"],
                    "required_level": cog["required_level"],
                    "topic": topic_key,
                    "learning_score": learning_score,
                })

    weak_analyzer = WeakTopicAnalyzer(
        exam_data=exam_data,
        threshold=req.weak_threshold,
    )
    weak_topics = weak_analyzer.analyze(student_reports)
    question_summaries = analyze_questions(student_reports, weak_threshold=req.weak_threshold)
    student_summaries = analyze_student_performance(student_reports, weak_threshold=req.weak_threshold)
    misunderstood = MisunderstoodQuestionsAnalyzer(
        threshold=req.weak_threshold,
        minimum_students=req.weak_min_students,
        minimum_below_share=req.weak_min_below_share,
    ).analyze(student_reports)
    cognitive_gaps = CognitiveGapAnalyzer().analyze(student_reports)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = settings.output_dir / str(exam_year) / exam_name / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    outputs = {
        "student_report.json": student_reports,
        "question_summary.json": question_summaries,
        "student_summary.json": student_summaries,
        "misunderstood_questions.json": misunderstood,
        "cognitive_gap_analysis.json": cognitive_gaps,
        "weak_topics.json": weak_topics,
    }
    for filename, data in outputs.items():
        with (output_dir / filename).open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    logger.info("Analysis saved to %s", output_dir)

    return AnalyzeExamResponse(
        exam=exam_name,
        year=int(exam_year) if str(exam_year).isdigit() else exam_year,
        student_reports=[StudentReportRecord(**r) for r in student_reports],
        question_summaries=question_summaries,
        student_summaries=student_summaries,
        misunderstood_questions=misunderstood,
        cognitive_gaps=cognitive_gaps,
        weak_topics=weak_topics,
        output_dir=str(output_dir),
    )

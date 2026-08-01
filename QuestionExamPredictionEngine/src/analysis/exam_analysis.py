"""Pure exam-analysis orchestration.

This module contains no HTTP or filesystem-writing concerns. It accepts loaded
exam, answer, and optional model-answer data and returns serializable results.
"""

from typing import Any, Iterable, Optional

from src.analysis.scoring.cognitive import cognitive_score
from src.analysis.scoring.concept_scoring import concept_score, extract_keywords
from src.analytics.cognitive_gap_analysis import CognitiveGapAnalyzer
from src.analytics.misunderstood_questions import MisunderstoodQuestionsAnalyzer
from src.analytics.question_analysis import analyze_questions
from src.analytics.student_analysis import analyze_student_performance
from src.analytics.topic_utils import resolve_topic
from src.analytics.weak_topic_analysis import WeakTopicAnalyzer


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _find_question_part(exam_data: dict, question_id: str, part_id: str) -> dict:
    for question in exam_data.get("questions", []):
        if str(question.get("question_number")) != str(question_id):
            continue
        for part in question.get("parts", []):
            if str(part.get("part")) == str(part_id):
                return part
    return {}


def _model_answer(model_answers: Optional[dict], question_id: str, part_id: str) -> str:
    if not model_answers:
        return ""

    question = model_answers.get(str(question_id), model_answers.get(question_id, {}))
    if not isinstance(question, dict):
        return ""
    value = question.get(str(part_id), question.get(part_id, ""))
    return str(value).strip() if value else ""


def _concept_reference(
    exam_part: dict,
    model_answers: Optional[dict],
    question_id: str,
    part_id: str,
) -> tuple[str, str]:
    reference = _model_answer(model_answers, question_id, part_id)
    if reference:
        return reference, "model_answer"

    for field in ("model_answer", "reference_answer"):
        value = exam_part.get(field)
        if value:
            return str(value), field

    # Question text is an imperfect fallback, but it is independent of the
    # student's response and therefore avoids self-referential concept scores.
    return str(exam_part.get("question", "")), "question_text"


def build_student_reports(
    exam_data: dict,
    student_data: Iterable[dict] | dict,
    model_answers: Optional[dict] = None,
    *,
    performance_weight: float = 0.6,
    concept_weight: float = 0.25,
    cognitive_weight: float = 0.15,
) -> list[dict]:
    """Build one analytical record per student answer part."""
    students = [student_data] if isinstance(student_data, dict) else list(student_data or [])
    reports = []
    exam_name = exam_data.get("exam", "PAPERS").replace(" ", "_")
    exam_year = exam_data.get("year", "UNKNOWN")

    for student in students:
        student_id = str(student.get("student_id", "UNKNOWN"))
        year = str(student.get("year", exam_year))

        for question in student.get("answers", []):
            question_id = str(question.get("question_number"))
            for answer_part in question.get("parts", []):
                part_id = str(answer_part.get("part", ""))
                student_answer = str(answer_part.get("answer", ""))
                exam_part = _find_question_part(exam_data, question_id, part_id)

                score = _as_float(answer_part.get("score"), 0.0)
                max_marks = _as_float(
                    answer_part.get("max_marks", exam_part.get("max_marks", 1)),
                    1.0,
                )
                performance = score / max_marks if max_marks > 0 else 0.0

                question_text = str(exam_part.get("question", ""))
                reference_text, reference_source = _concept_reference(
                    exam_part,
                    model_answers,
                    question_id,
                    part_id,
                )
                keywords = extract_keywords(reference_text)
                concept = concept_score(student_answer, keywords)
                cognitive = cognitive_score(question_text, student_answer)

                learning_score = round(
                    (performance_weight * performance)
                    + (concept_weight * concept)
                    + (cognitive_weight * cognitive["cognitive_score"]),
                    3,
                )
                topic = resolve_topic(
                    exam_data,
                    question_id,
                    part_id,
                    default=f"Q{question_id}{part_id}",
                )

                reports.append({
                    "student_id": student_id,
                    "exam": exam_name,
                    "year": year,
                    "question": question_id,
                    "part": part_id,
                    "score": round(score, 3),
                    "max_marks": round(max_marks, 3),
                    "performance_score": round(performance, 3),
                    "concept_score": round(concept, 3),
                    "concept_reference_source": reference_source,
                    "cognitive_score": cognitive["cognitive_score"],
                    "student_level": cognitive["student_level"],
                    "required_level": cognitive["required_level"],
                    "topic": topic,
                    "learning_score": learning_score,
                })

    return reports


def analyze_exam_records(
    exam_data: dict,
    student_data: Iterable[dict] | dict,
    model_answers: Optional[dict] = None,
    *,
    weak_threshold: float = 0.5,
    weak_min_students: int = 2,
    weak_min_below_share: float = 0.4,
    performance_weight: float = 0.6,
    concept_weight: float = 0.25,
    cognitive_weight: float = 0.15,
) -> dict[str, list[dict]]:
    """Run all analytics and return report-name-to-record mappings."""
    reports = build_student_reports(
        exam_data,
        student_data,
        model_answers,
        performance_weight=performance_weight,
        concept_weight=concept_weight,
        cognitive_weight=cognitive_weight,
    )

    return {
        "student_reports": reports,
        "question_summaries": analyze_questions(reports, weak_threshold=weak_threshold),
        "student_summaries": analyze_student_performance(reports, weak_threshold=weak_threshold),
        "misunderstood_questions": MisunderstoodQuestionsAnalyzer(
            threshold=weak_threshold,
            minimum_students=weak_min_students,
            minimum_below_share=weak_min_below_share,
        ).analyze(reports),
        "cognitive_gaps": CognitiveGapAnalyzer().analyze(reports),
        "weak_topics": WeakTopicAnalyzer(
            exam_data=exam_data,
            threshold=weak_threshold,
        ).analyze(reports),
    }

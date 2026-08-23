"""Generator that computes and persists lecturer-facing exam analytics."""

from datetime import datetime, timezone

from app.analytics.exam_analytics import compute_exam_analytics_stats
from app.analytics.student_document import build_numeric_analysis
from app.analytics.weakness import compute_weakness_scores
from app.db.repository import (
    find_course_for_submission,
    find_graded_submissions_for_exam,
    find_rubric_for_submission,
    upsert_exam_analytics,
    upsert_exam_analysis_status,
)
from app.ingestion.student_data import normalize_student_submission
from app.services.student_pipeline import _classify_questions


class ExamNotFound(Exception):
    """Raised when no graded submissions exist for the requested exam."""


async def compute_exam_analytics(
    db, course_code: str, session_name: str,
    year: int | None = None, month: int | None = None, semester: int | None = None,
) -> dict:
    submissions = await find_graded_submissions_for_exam(db, course_code, session_name, year, month, semester)
    if not submissions:
        raise ExamNotFound(f"no graded submissions for {course_code} {session_name}")

    course = None
    rubric = None
    students: list[dict] = []
    for submission in submissions:
        course = await find_course_for_submission(db, submission)
        rubric = await find_rubric_for_submission(db, submission)
        normalized = normalize_student_submission(course or {}, rubric or {}, submission)
        semantics = await _classify_questions(normalized, {})
        numeric = build_numeric_analysis(normalized, semantics)
        students.append(
            {
                "overall": numeric.overall_performance.model_dump(),
                "topic_performance": [topic.model_dump() for topic in numeric.topic_performance],
                "bloom_performance": [bloom.model_dump() for bloom in numeric.bloom_performance],
                "question_performance": [
                    {
                        "question_no": q.question_no,
                        "topic": q.topic,
                        "bloom_level": q.bloom_analysis.level,
                        "score": q.performance.score,
                        "max_score": q.performance.max_score,
                    }
                    for q in numeric.question_performance
                ],
            }
        )

    stats = compute_exam_analytics_stats(students, pass_threshold=0.5)
    # Phase 3: attach weakness scores for recommendation engine (canonical first, raw fallback)
    # weakness computed here is persisted with the document; topic_canonicalization later
    # enriches with canonical_topic_performance -> recalculate if available
    try:
        stats["weakness_scores"] = compute_weakness_scores(
            canonical_topic_performance=None,
            topic_performance=stats.get("topic_performance"),
        )
        stats["weakest_topics"] = [
            t for t, _ in sorted(
                ((k, v["weakness"]) for k, v in stats["weakness_scores"].items()),
                key=lambda kv: kv[1],
                reverse=True,
            )
        ]
    except Exception:
        pass
    total_marks = sum(float(q["max_marks"]) for q in (rubric or {}).get("questions", []))
    question_count = len((rubric or {}).get("questions", []))
    course_name = str((course or {}).get("name") or (course or {}).get("course_name") or "").strip()
    if not course_name:
        course_name = "Database Management Systems" if course_code == "IT2040" else course_code
    subject_name = str((rubric or {}).get("subject_name") or course_name or "").strip() or course_code
    try:
        if year is None:
            year = int((rubric or {}).get("year") or 0)
        if month is None:
            month = int((rubric or {}).get("month") or 0)
        if semester is None:
            semester = int((rubric or {}).get("semester") or 0)
    except (TypeError, ValueError) as exc:
        raise ExamNotFound(f"invalid rubric session identity for {course_code} {session_name}") from exc
    document = {
        "subject_code": course_code,
        "subject_name": subject_name,
        "year": year,
        "month": month,
        "semester": semester,
        "session_name": session_name,
        "exam": {"session_name": session_name, "total_marks": total_marks, "question_count": question_count},
        **stats,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "analytics_version": "1.0",
    }
    await upsert_exam_analytics(db, document)
    await upsert_exam_analysis_status(
        db,
        {
            "subject_code": course_code,
            "subject_name": subject_name,
            "year": year,
            "month": month,
            "semester": semester,
            "session_name": session_name,
            "analyzed": "done",
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return document

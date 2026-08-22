"""Sample runner to demonstrate the lecturer dashboard API.

Shows how app/api/lecturer.py is built:
- GET /api/lecturers/exams/{course_code}/{session_name}/analytics
- GET /api/lecturers/exams/{course_code}/{session_name}/students

Usage (PowerShell, from V2_QuestionExamPredictionEngine):
    .\\.venv\\Scripts\\python.exe run_lec_sample.py [db_name] [course_code] [session_name]

Defaults: db_name=dbms_analytics_test, course_code=IT2040, session_name="Final Examination"
Uses the same sample_data as run_sample.py (app/sample_data/).
"""

import asyncio
import json
import sys

from motor.motor_asyncio import AsyncIOMotorClient

from app.analytics.student_document import performance_status
from app.api import deps
from app.config import settings
from app.db.repository import (
    create_indexes,
    find_exam_analytics,
    find_graded_submissions_for_exam,
    find_student_analytics,
)
from app.main import app
from app.services.exam_analytics import ExamNotFound, compute_exam_analytics
import app.services.exam_analytics as exam_analytics_mod
from run_sample import load_raw_sample_documents, seed_raw_samples


def _print_json(label: str, payload: object) -> None:
    print(f"\n=== {label} ===")
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


async def build_lecturer_student_rows(db, course_code: str, session_name: str) -> list[dict]:
    """Replicate app/api/lecturer.py:32 lecturer_student_list logic."""
    submissions = await find_graded_submissions_for_exam(db, course_code, session_name)
    if not submissions:
        raise ExamNotFound(f"no graded submissions for {course_code} {session_name}")
    rows = []
    for submission in submissions:
        student_id = submission["student_id"]
        evaluation = submission.get("evaluation") or {}
        obtained = evaluation.get("total_score")
        if obtained is None:
            obtained = submission.get("max_marks_paper_total")
        obtained = float(obtained or 0.0)
        maximum = evaluation.get("max_score")
        if maximum is None:
            maximum = submission.get("max_marks_paper_total")
        maximum = float(maximum or 0.0)
        percentage = (obtained / maximum * 100.0) if maximum else 0.0
        cached = await find_student_analytics(db, student_id, course_code, session_name)
        rows.append(
            {
                "student_id": student_id,
                "score": {
                    "obtained": obtained,
                    "maximum": maximum,
                    "percentage": round(percentage, 2),
                },
                "status": performance_status(percentage),
                "analysis_status": "generated" if cached else "pending",
                "submitted_at": submission.get("processed_at"),
            }
        )
    return rows


async def main(db_name: str, course_code: str, session_name: str) -> int:
    print(f"database={db_name}")
    print(f"exam={course_code} / {session_name}")
    print(f"mongodb_uri={settings.mongodb_uri}")

    courses, rubrics, _ = load_raw_sample_documents()
    print(f"sample_data: courses={len(courses)} rubrics={len(rubrics)} (using {course_code}/{session_name})")

    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[db_name]

    try:
        await create_indexes(db)
        counts = await seed_raw_samples(db)
        print(f"seeded courses={counts['courses']} rubrics={counts['rubrics']} submissions={counts['submissions']}")

        # 1. Direct service: exam analytics (app/services/exam_analytics.py:22)
        # For demo, patch _classify_questions to avoid 120s LLM timeout when Ollama is down
        # It will use rule-based classifier instantly (like tests do)
        from app.classifier.rules import classify_by_rules
        from app.llm.roles.student_analysis import QuestionSemantics

        _RULE_CONF = {"high": 0.85, "medium": 0.65, "low": 0.4}

        async def _fast_classify(normalized, cache):
            out: dict[str, QuestionSemantics] = {}
            for q in normalized.questions:
                rules = classify_by_rules(q.question_text)
                dominant = (
                    max(rules.topic_assignments, key=lambda a: a.weight).topic
                    if rules.topic_assignments
                    else "General"
                )
                subtopic = next(
                    (str(c).strip() for c in rules.key_concepts if str(c).strip()),
                    dominant,
                )
                out[q.question_no] = QuestionSemantics(
                    level=rules.bloom_level,
                    topic=dominant,
                    subtopic=subtopic,
                    confidence=_RULE_CONF.get(rules.confidence, 0.4),
                    reason="rule-based fallback (demo)",
                )
            return out

        orig_classify = exam_analytics_mod._classify_questions
        exam_analytics_mod._classify_questions = _fast_classify
        try:
            cached = await find_exam_analytics(db, course_code, session_name)
            if cached:
                _print_json("Cached Exam Analytics (analytics_snapshots)", cached)
                doc = await compute_exam_analytics(db, course_code, session_name)
                _print_json("Recomputed Exam Analytics (compute_exam_analytics - rule fallback)", doc)
            else:
                doc = await compute_exam_analytics(db, course_code, session_name)
                _print_json("Computed Exam Analytics (compute_exam_analytics - rule fallback)", doc)
        except ExamNotFound as exc:
            print(f"ExamNotFound: {exc}")
            return 1
        finally:
            exam_analytics_mod._classify_questions = orig_classify

        # 2. Direct service: lecturer student list
        try:
            rows = await build_lecturer_student_rows(db, course_code, session_name)
            _print_json(f"Lecturer Student List ({len(rows)} rows) - lecturer.py:32", rows)
        except ExamNotFound as exc:
            print(f"ExamNotFound: {exc}")
            return 1

        # 3. HTTP via FastAPI TestClient (no server needed) - mirrors tests/test_api_lecturer.py
        try:
            import httpx

            app.dependency_overrides[deps.get_db] = lambda: db
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client_http:
                r1 = await client_http.get(f"/api/lecturers/exams/{course_code}/{session_name}/analytics")
                _print_json(f"HTTP GET /api/lecturers/exams/{course_code}/{session_name}/analytics -> {r1.status_code}", r1.json() if r1.status_code == 200 else {"error": r1.text})

                r2 = await client_http.get(f"/api/lecturers/exams/{course_code}/{session_name}/students")
                _print_json(f"HTTP GET /api/lecturers/exams/{course_code}/{session_name}/students -> {r2.status_code}", r2.json() if r2.status_code == 200 else {"error": r2.text})
        except Exception as exc:
            print(f"HTTP test skipped: {exc}")
        finally:
            app.dependency_overrides.clear()

        print("\nDone. Lecturer dashboard is wired in app/main.py:7 via app/api/lecturer.py:13.")
        print("To run the real server: .\\.venv\\Scripts\\uvicorn app.main:app --reload")
        print(f"Then: curl \"http://localhost:8000/api/lecturers/exams/{course_code}/{session_name}/analytics\"")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    db_name = sys.argv[1] if len(sys.argv) > 1 else "dbms_analytics_test"
    course_code = sys.argv[2] if len(sys.argv) > 2 else "IT2040"
    session_name = sys.argv[3] if len(sys.argv) > 3 else "Final Examination"
    raise SystemExit(asyncio.run(main(db_name, course_code, session_name)))

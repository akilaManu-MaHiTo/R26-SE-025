import logging

from app.analytics import student as student_analytics
from app.config import settings
from app.db.repository import find_attempts, find_attempts_by_student, latest_run_id
from app.schemas.student import StudentDashboard, StudentStudyAction
from app.services.llm_service import study_actions

logger = logging.getLogger(__name__)


class StudentDashboardNotFound(Exception):
    pass


async def build_student_dashboard(
    db, student_key: str, run_id: str | None = None, include_llm: bool = False
) -> StudentDashboard:
    if run_id is None:
        run_id = await latest_run_id(db)
    if run_id is None:
        raise StudentDashboardNotFound("no analysis run found")

    attempts = await find_attempts_by_student(db, run_id, student_key)
    if not attempts:
        raise StudentDashboardNotFound("no attempts found for student")

    all_attempts = await find_attempts(db, run_id)
    pass_threshold = settings.pass_threshold

    exams = student_analytics.student_exam_performances(attempts, pass_threshold)
    bloom_skills = student_analytics.bloom_skill_profile(attempts, pass_threshold)
    topic_skills = student_analytics.topic_skill_profile(attempts, pass_threshold)
    weakest = student_analytics.rank_weakest_topics(topic_skills)
    recommendations = student_analytics.deterministic_study_actions(weakest)

    if include_llm:
        try:
            result = await study_actions(student_key, weakest[:3], {"weak_topics": weakest[:3]})
            if result.get("status") == "ok":
                recommendations = [
                    StudentStudyAction(**{**action, "source": "llm"})
                    for action in result.get("actions", [])
                ]
        except Exception:
            logger.exception("LLM study actions failed; keeping deterministic")

    return StudentDashboard(
        student_key=student_key,
        course_code=attempts[0]["course_code"],
        run_id=run_id,
        exams=exams,
        bloom_skills=bloom_skills,
        topic_skills=topic_skills,
        weakest_topics=weakest,
        cohort_comparison=student_analytics.cohort_comparison(attempts, all_attempts),
        recommendations=recommendations,
    )
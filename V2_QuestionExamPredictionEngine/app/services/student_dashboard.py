from app.db.repository import (
    find_graded_submission,
    find_student_analytics,
    upsert_student_analytics,
)
from app.schemas.student import StudentAnalyticsDocument
from app.services.student_pipeline import build_student_analytics


class StudentNotFound(Exception):
    pass


async def ensure_student_analytics(
    db,
    student_id: str,
    course_code: str,
    session_name: str,
    year: int | None = None,
    month: int | None = None,
    semester: int | None = None,
    progress_callback=None,
) -> StudentAnalyticsDocument:
    cached = await find_student_analytics(
        db, student_id, course_code, session_name, year, month, semester
    )
    if cached is not None:
        return StudentAnalyticsDocument.model_validate(cached)

    submission = await find_graded_submission(
        db, student_id, course_code, session_name, year, month, semester
    )
    if submission is None:
        raise StudentNotFound("no graded submission found for student")

    document = await build_student_analytics(db, submission, progress_callback=progress_callback)
    await upsert_student_analytics(db, document.model_dump(mode="json"))
    return document

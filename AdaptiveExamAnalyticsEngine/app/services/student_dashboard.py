import asyncio

from app.db.repository import (
    find_graded_submission,
    find_student_analytics,
    upsert_student_analytics,
)
from app.schemas.student import StudentAnalyticsDocument
from app.services.student_pipeline import STUDENT_ANALYSIS_VERSION, build_student_analytics

# shortcut: FIFO is per process and not persistent; use a shared job queue for multiple workers or restart recovery.
_student_analysis_lock = asyncio.Lock()


class StudentNotFound(Exception):
    pass


def is_current_student_analysis(document: dict | None) -> bool:
    return bool(document and document.get("analysis_version") == STUDENT_ANALYSIS_VERSION
                and not document.get("topic_assignment_pending"))


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
    if is_current_student_analysis(cached):
        return StudentAnalyticsDocument.model_validate(cached)

    if _student_analysis_lock.locked() and progress_callback is not None:
        progress_callback("queued")
    async with _student_analysis_lock:
        # A previous queued request may have saved this student's result.
        cached = await find_student_analytics(
            db, student_id, course_code, session_name, year, month, semester
        )
        if is_current_student_analysis(cached):
            return StudentAnalyticsDocument.model_validate(cached)
        if progress_callback is not None:
            progress_callback("started")
        submission = await find_graded_submission(
            db, student_id, course_code, session_name, year, month, semester
        )
        if submission is None:
            raise StudentNotFound("no graded submission found for student")

        document = await build_student_analytics(db, submission, progress_callback=progress_callback)
        await upsert_student_analytics(db, document.model_dump(mode="json"))
        return document

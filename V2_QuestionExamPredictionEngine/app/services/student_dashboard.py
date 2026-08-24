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
) -> StudentAnalyticsDocument:
    # Check if lecturer has analyzed this exam — if not, tell student to wait
    # Check analyzedExams / analytics_snapshots for this course/session/year
    # If year not provided, check any analyzed for this course/session
    try:
        from app.db.repository import find_exam_analysis_status, find_exam_analytics

        status = None
        analytics = None
        if year is not None or month is not None or semester is not None:
            status = await find_exam_analysis_status(db, course_code, session_name, year, month, semester)
            if status is None:
                analytics = await find_exam_analytics(db, course_code, session_name, year, month, semester)
        else:
            # Check any analyzed for this course/session (most recent)
            status = await find_exam_analysis_status(db, course_code, session_name)
            if status is None:
                analytics = await find_exam_analytics(db, course_code, session_name)
        is_analyzed = False
        if status and status.get("analyzed") == "done":
            is_analyzed = True
        elif analytics is not None:
            is_analyzed = True
        if not is_analyzed:
            raise StudentNotFound("Wait for lecture to analyze your data — this exam has not been analyzed yet")
    except StudentNotFound:
        raise
    except Exception:
        # If check fails (e.g., DB error), allow generation to proceed — don't block student
        pass

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

    document = await build_student_analytics(db, submission)
    await upsert_student_analytics(db, document.model_dump(mode="json"))
    return document

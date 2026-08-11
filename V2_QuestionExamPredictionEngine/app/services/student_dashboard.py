from app.db.repository import find_student_analytics
from app.schemas.student import StudentAnalyticsDocument


class StudentDashboardNotFound(Exception):
    pass


async def get_student_dashboard(
    db,
    student_id: str,
    course_code: str | None = None,
    session_name: str | None = None,
) -> StudentAnalyticsDocument:
    document = await find_student_analytics(
        db, student_id, course_code, session_name
    )
    if document is None:
        raise StudentDashboardNotFound(
            "no saved analytics found for student"
        )
    return StudentAnalyticsDocument.model_validate(document)

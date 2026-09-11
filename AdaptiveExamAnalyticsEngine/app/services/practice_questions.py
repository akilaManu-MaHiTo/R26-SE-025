from datetime import datetime, timezone

from app.db.repository import find_course_for_submission, upsert_generated_questions
from app.schemas.student import NextQuestionStrategy
from app.services.llm_service import generate_practice_questions as generate_practice_questions_call


async def generate_practice_questions(
    db, student_id: str, course_code: str, session_name: str, strategy: NextQuestionStrategy
) -> dict:
    target = strategy.model_dump()
    response = await generate_practice_questions_call(target)
    if response["status"] != "ok":
        return response
    document = {
        "student_id": student_id,
        "exam_id": f"{course_code}@{session_name}",
        "course": {"code": course_code, "name": await _resolve_course_name(db, course_code)},
        "request": target,
        "questions": response["questions"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generation_version": "1.0",
    }
    await upsert_generated_questions(db, document)
    return {"status": "ok", "document": document}


async def _resolve_course_name(db, course_code: str) -> str:
    try:
        course = await find_course_for_submission(db, {"course_code": course_code})
        name = (course or {}).get("name")
        if isinstance(name, str) and name.strip():
            return name
    except Exception:
        pass
    return course_code

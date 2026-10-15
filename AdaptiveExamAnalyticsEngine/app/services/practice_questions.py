from datetime import datetime, timezone

from app.db.repository import find_course_for_submission, upsert_generated_questions
from app.schemas.student import NextQuestionStrategy
from app.llm.roles.generate_practice import practice_batch_matches_target
from app.services.llm_service import generate_practice_questions as generate_practice_questions_call

GENERATION_VERSION = "1.1"


async def generate_practice_questions(
    db, student_id: str, course_code: str, session_name: str, strategy: NextQuestionStrategy
) -> dict:
    target = strategy.model_dump()
    response = await generate_practice_questions_call(target)
    if response["status"] != "ok":
        return response
    if not practice_batch_matches_target(response.get("questions"), target):
        return {"status": "degraded", "reason": "target_mismatch"}
    document = {
        "student_id": student_id,
        "exam_id": f"{course_code}@{session_name}",
        "course": {"code": course_code, "name": await _resolve_course_name(db, course_code)},
        "request": target,
        "questions": response["questions"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generation_version": GENERATION_VERSION,
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

"""Student account provisioning on lecturer exam analysis."""

from datetime import datetime, timezone

from app.db.repository import (
    find_graded_submissions_for_exam,
    find_user_by_email,
    find_user_by_student_id,
    upsert_user,
)

EMAIL_DOMAIN = "my.sliit.lk"


def student_email(student_id: str) -> str:
    return f"{student_id.strip().lower()}@{EMAIL_DOMAIN}"


async def ensure_student_account(db, student_id: str) -> dict:
    sid = str(student_id).strip()
    if not sid:
        raise ValueError("student_id required")
    email = student_email(sid)

    existing = await find_user_by_email(db, email)
    if existing is not None:
        return existing

    by_sid = await find_user_by_student_id(db, sid)
    if by_sid is not None:
        return by_sid

    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "student_id": sid,
        "email": email,
        # Student login sets the default password hash on the first successful sign-in.
        "password_hash": "",
        "role": "student",
        "created_at": now,
        "updated_at": now,
    }
    await upsert_user(db, doc)
    return doc


async def provision_student_accounts(
    db,
    course_code: str,
    session_name: str,
    year: int | None = None,
    month: int | None = None,
    semester: int | None = None,
) -> dict:
    submissions = await find_graded_submissions_for_exam(db, course_code, session_name, year, month, semester)
    seen: set[str] = set()
    created = 0
    existed = 0
    for sub in submissions:
        sid = str(sub.get("student_id") or sub.get("student_key") or "").strip()
        if not sid or sid in seen:
            continue
        seen.add(sid)
        email = student_email(sid)
        existing = await find_user_by_email(db, email)
        if existing is not None:
            existed += 1
            continue
        by_sid = await find_user_by_student_id(db, sid)
        if by_sid is not None:
            existed += 1
            continue
        await ensure_student_account(db, sid)
        created += 1
    return {"total": len(seen), "created": created, "existed": existed}

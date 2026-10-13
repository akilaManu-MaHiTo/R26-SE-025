"""Student account provisioning on lecturer exam analysis."""

import hashlib
import secrets
from datetime import datetime, timezone

from app.db.repository import (
    find_graded_submissions_for_exam,
    find_user_by_email,
    find_user_by_student_id,
    upsert_user,
)

DEFAULT_PASSWORD = "Student@123"
EMAIL_DOMAIN = "my.sliit.lk"
ITERATIONS = 100000


def student_email(student_id: str) -> str:
    return f"{student_id.strip().lower()}@{EMAIL_DOMAIN}"


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_hex, hash_hex = stored.split("$")
        # algo is pbkdf2_sha256, iters is numeric string
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iters))
        return dk.hex() == hash_hex
    except Exception:
        return False


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
        "password_hash": hash_password(DEFAULT_PASSWORD),
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
        sid = str(sub.get("student_id") or "").strip()
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

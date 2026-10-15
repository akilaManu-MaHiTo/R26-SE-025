"""Create an account or reset its password. Run from the repository root."""
import argparse
import asyncio
from datetime import datetime, timezone
from getpass import getpass

from Gradex_AI_Server.app.session_auth import close_auth, get_auth_db, hash_password, initialize_auth


async def provision_user(email: str, role: str, password: str, student_id: str | None = None):
    email = email.strip().lower()
    student_id = student_id.strip() if student_id else None
    if email.count("@") != 1 or not all(email.split("@")) or len(email) > 254:
        raise ValueError("Enter a valid email address")
    if role not in {"lecturer", "student"} or (role == "student" and not student_id):
        raise ValueError("Students require --student-id")
    if not 12 <= len(password) <= 1024:
        raise ValueError("Password must contain 12–1024 characters")
    db = get_auth_db()
    existing = await db["users"].find_one({"email": email})
    if existing and (existing.get("role") != role or existing.get("student_id") != student_id):
        raise ValueError("Account identity differs; use its existing role and student ID")
    await initialize_auth()
    now = datetime.now(timezone.utc)
    fields = {"email": email, "role": role, "password_hash": hash_password(password), "updated_at": now}
    if student_id:
        fields["student_id"] = student_id
    await db["users"].update_one(
        {"email": email}, {"$set": fields, "$inc": {"auth_version": 1}, "$setOnInsert": {"created_at": now}}, upsert=True,
    )
    await db["auth_sessions"].delete_many({"email": email})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email")
    parser.add_argument("--role", required=True, choices=["lecturer", "student"])
    parser.add_argument("--student-id")
    args = parser.parse_args()
    password = getpass("Password (at least 12 characters): ")
    if password != getpass("Confirm password: "):
        parser.error("Passwords do not match")
    try:
        asyncio.run(provision_user(args.email, args.role, password, args.student_id))
    except ValueError as exc:
        parser.error(str(exc))
    finally:
        close_auth()
    print("Account saved; previous sessions revoked.")


if __name__ == "__main__":
    main()

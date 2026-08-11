import asyncio
import json
import sys
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient

from app.config import settings
from app.db.repository import create_indexes
from app.services.student_pipeline import materialize_student_analytics

SAMPLE_DIR = Path(__file__).resolve().parent / "app" / "sample_data"


def load_raw_sample_documents() -> tuple[list[dict], list[dict], list[dict]]:
    """Load the checked-in raw MongoDB sample documents."""

    def load(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    courses = [load(SAMPLE_DIR / "courses.json")]
    rubrics = [load(SAMPLE_DIR / "rubricCollection.json")]
    submissions = [load(path) for path in sorted(SAMPLE_DIR.glob("submission*.json"))]
    return courses, rubrics, submissions


async def seed_raw_samples(db) -> dict[str, int]:
    """Idempotently upsert the checked-in raw sample documents."""
    courses, rubrics, submissions = load_raw_sample_documents()

    for course in courses:
        course_document = {key: value for key, value in course.items() if key != "_id"}
        await db["courses"].replace_one(
            {"subject_code": course.get("subject_code", "IT2040")},
            course_document,
            upsert=True,
        )
    for rubric in rubrics:
        rubric_document = {key: value for key, value in rubric.items() if key != "_id"}
        await db["rubricCollection"].replace_one(
            {
                "subject_code": rubric["subject_code"],
                "session_name": rubric["session_name"],
            },
            rubric_document,
            upsert=True,
        )
    for submission in submissions:
        submission_document = {
            key: value for key, value in submission.items() if key != "_id"
        }
        await db["submissions"].replace_one(
            {
                "student_id": submission["student_id"],
                "subject_code": submission["subject_code"],
                "session_name": submission["session_name"],
            },
            submission_document,
            upsert=True,
        )

    return {
        "courses": len(courses),
        "rubrics": len(rubrics),
        "submissions": len(submissions),
    }


async def main(db_name: str) -> int:
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[db_name]
    try:
        print(f"database={db_name}")
        _, _, sample_submissions = load_raw_sample_documents()
        await create_indexes(db)
        counts = await seed_raw_samples(db)
        print(
            "seeded "
            f"courses={counts['courses']} "
            f"rubrics={counts['rubrics']} "
            f"submissions={counts['submissions']}"
        )

        result = await materialize_student_analytics(db, submissions=sample_submissions)
        saved_summary = ", ".join(result.saved) if result.saved else "none"
        print(f"saved student_ids: {saved_summary}")
        print(f"failures: {len(result.failures)}")
        for failure in result.failures:
            print(f"  {failure.student_id}: {failure.reason}")

        sample_analytics_filter = {
            "$or": [
                {
                    "student_id": submission["student_id"],
                    "course.code": submission.get("course_code")
                    or submission["subject_code"],
                    "assessment.session_name": submission["session_name"],
                }
                for submission in sample_submissions
            ]
        }
        saved_count = await db["student_analytics"].count_documents(
            sample_analytics_filter
        )
        print(f"student_analytics count={saved_count}")
        return 1 if result.failures else 0
    finally:
        client.close()


if __name__ == "__main__":
    db_name = sys.argv[1] if len(sys.argv) > 1 else "dbms_analytics_test"
    raise SystemExit(asyncio.run(main(db_name)))

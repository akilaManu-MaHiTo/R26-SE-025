import asyncio
import sys
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient
from bson.json_util import loads
from tqdm import tqdm

from app.config import settings
from app.db.repository import create_indexes
from app.llm.ollama import check_llm_health
from app.services.exam_analytics import compute_exam_analytics
from app.services.student_pipeline import materialize_student_analytics

SAMPLE_DIR = Path(__file__).resolve().parent / "app" / "sample_data"


def load_raw_sample_documents() -> tuple[list[dict], list[dict], list[dict]]:
    """Load the checked-in raw MongoDB sample documents.

    The three folders under app/sample_data/ mirror the courses,
    rubricCollection, and submissions collections. Documents are decoded
    from MongoDB Extended JSON ($oid/$date) into native BSON types.
    """

    def load(path: Path) -> object:
        with open(path, encoding="utf-8") as fh:
            return loads(fh.read())

    courses = load(SAMPLE_DIR / "courses" / "courses.json")
    rubrics = [load(SAMPLE_DIR / "rubricCollection" / "rubricCollection.json")]
    submissions: list[dict] = []
    for path in sorted((SAMPLE_DIR / "submissions").glob("submission*.json")):
        submissions.extend(load(path))
    return courses, rubrics, submissions


def _usable_identity(document: dict) -> object | None:
    """Return the document's _id when it is a usable reference, else None."""
    _id = document.get("_id")
    if _id is None:
        return None
    if isinstance(_id, str) and "..." in _id:
        return None
    return _id


async def _upsert_natural(
    db, collection: str, document: dict, natural_filter: dict
) -> None:
    identity = _usable_identity(document)
    if identity is not None:
        await db[collection].replace_one({"_id": identity}, document, upsert=True)
        return
    replacement = {key: value for key, value in document.items() if key != "_id"}
    await db[collection].replace_one(natural_filter, replacement, upsert=True)


async def seed_raw_samples(db) -> dict[str, int]:
    """Idempotently upsert the checked-in raw sample documents."""
    courses, rubrics, submissions = load_raw_sample_documents()

    for course in courses:
        course_key = course.get("code") or course.get("subject_code") or "IT2040"
        await _upsert_natural(
            db,
            "courses",
            course,
            {"$or": [{"code": course_key}, {"subject_code": course_key}]},
        )
    for rubric in rubrics:
        await _upsert_natural(
            db,
            "rubricCollection",
            rubric,
            {
                "subject_code": rubric["subject_code"],
                "session_name": rubric["session_name"],
            },
        )
    for submission in submissions:
        await _upsert_natural(
            db,
            "submissions",
            submission,
            {
                "student_id": submission["student_id"],
                "subject_code": submission["subject_code"],
                "session_name": submission["session_name"],
            },
        )

    return {
        "courses": len(courses),
        "rubrics": len(rubrics),
        "submissions": len(submissions),
    }


async def main(db_name: str) -> int:
    healthy, detail = await check_llm_health()
    if not healthy:
        print(f"LLM backend unreachable at {settings.llm_base_url}: {detail}")
        print("Every question would silently fall back to rule-based analysis.")
        print("Restart the Colab notebook, copy the printed OLLAMA_BASE_URL and OLLAMA_API_KEY,")
        print("then run: python switch_llm.py colab <new-url> <new-key>")
        return 2

    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[db_name]
    progress_bar: tqdm | None = None

    def on_progress(done: int, total: int, phase: str) -> None:
        nonlocal progress_bar
        if progress_bar is None:
            progress_bar = tqdm(
                total=total,
                desc="analyzing",
                unit="step",
                bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
            )
        progress_bar.set_description(f"analyzing ({phase})")
        progress_bar.n = done
        progress_bar.refresh()

    try:
        print(f"database={db_name}")
        courses, rubrics, sample_submissions = load_raw_sample_documents()
        await create_indexes(db)
        counts = await seed_raw_samples(db)
        print(
            "seeded "
            f"courses={counts['courses']} "
            f"rubrics={counts['rubrics']} "
            f"submissions={counts['submissions']}"
        )

        result = await materialize_student_analytics(
            db,
            submissions=sample_submissions,
            progress_callback=on_progress,
        )
        if progress_bar is not None:
            progress_bar.close()
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
                    "exam_id": f"{submission.get('course_code') or submission['subject_code']}@{submission['session_name']}",
                }
                for submission in sample_submissions
            ]
        }
        saved_count = await db["student_analytics"].count_documents(
            sample_analytics_filter
        )
        print(f"student_analytics count={saved_count}")

        sample_course_code = (
            courses[0].get("code") or courses[0].get("subject_code") or "IT2040"
        )
        sample_session = rubrics[0]["session_name"]
        await compute_exam_analytics(db, sample_course_code, sample_session)
        exam_analytics_count = await db["analytics_snapshots"].count_documents(
            {
                "course.code": sample_course_code,
                "exam_id": f"{sample_course_code}@{sample_session}",
            }
        )
        print(f"exam_analytics count={exam_analytics_count}")
        return 1 if result.failures else 0
    finally:
        if progress_bar is not None:
            progress_bar.close()
        client.close()


if __name__ == "__main__":
    db_name = sys.argv[1] if len(sys.argv) > 1 else "dbms_analytics_test"
    raise SystemExit(asyncio.run(main(db_name)))

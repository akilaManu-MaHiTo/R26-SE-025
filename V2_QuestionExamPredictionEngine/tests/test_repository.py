from app.db.repository import (
    create_indexes,
    find_attempts,
    insert_attempts,
    save_run,
)
from tests.fixtures.fixture_data import expected_attempt_records


async def test_indexes_created(test_db):
    await create_indexes(test_db)
    info = await test_db["question_catalog"].index_information()
    index_keys = [info[name]["key"] for name in info]
    assert any("course_code" in dict(k) for k in index_keys)


async def test_insert_attempts_idempotent(test_db):
    await create_indexes(test_db)
    first = await insert_attempts(test_db, expected_attempt_records[:5])
    second = await insert_attempts(test_db, expected_attempt_records[:5])
    assert first == 5
    assert second == 5
    found = await find_attempts(test_db, "run-fixture")
    assert len(found) == 5


async def test_save_run_upsert(test_db):
    await create_indexes(test_db)
    await save_run(test_db, {"run_id": "r1", "course_code": "SE2032", "exam_id": "e1"})
    await save_run(test_db, {"run_id": "r1", "course_code": "SE2032", "exam_id": "e1", "status": "running"})
    doc = await test_db["analysis_runs"].find_one({"run_id": "r1"})
    assert doc["status"] == "running"


from datetime import datetime, timezone

from app.db.repository import find_attempts_by_student, insert_attempts, latest_run_id, save_run


async def test_find_attempts_by_student_filters_by_student(test_db):
    from tests.fixtures.fixture_data import expected_attempt_records

    await insert_attempts(test_db, expected_attempt_records)
    rows = await find_attempts_by_student(test_db, "run-fixture", "stu-001")
    assert len(rows) == 6
    assert all(r["student_key"] == "stu-001" for r in rows)


async def test_find_attempts_by_student_unknown_returns_empty(test_db):
    rows = await find_attempts_by_student(test_db, "run-fixture", "nobody")
    assert rows == []


async def test_latest_run_id_returns_most_recent(test_db):
    now = datetime.now(timezone.utc)
    await save_run(test_db, {"run_id": "older", "course_code": "SE2032", "exam_id": "e", "status": "ready", "created_at": now.replace(minute=0)})
    await save_run(test_db, {"run_id": "newer", "course_code": "SE2032", "exam_id": "e", "status": "ready", "created_at": now.replace(minute=1)})
    assert await latest_run_id(test_db) == "newer"


async def test_latest_run_id_empty_returns_none(test_db):
    await test_db["analysis_runs"].delete_many({})
    assert await latest_run_id(test_db) is None


from app.db.repository import find_recommendations, save_recommendations


async def test_find_recommendations_returns_sorted_by_priority(test_db):
    await test_db["exam_recommendations"].delete_many({})
    await save_recommendations(
        test_db,
        [
            {
                "recommendation_id": "r-low",
                "run_id": "run-1",
                "course_code": "SE2032",
                "exam_id": "e1",
                "topic": "SQL",
                "bloom_level": "Apply",
                "priority_score": 0.3,
            },
            {
                "recommendation_id": "r-high",
                "run_id": "run-1",
                "course_code": "SE2032",
                "exam_id": "e1",
                "topic": "Schema Refinement",
                "bloom_level": "Analyze",
                "priority_score": 0.9,
            },
        ],
    )
    recs = await find_recommendations(test_db, "run-1")
    assert [r["recommendation_id"] for r in recs] == ["r-high", "r-low"]


async def test_find_recommendations_other_run_returns_empty(test_db):
    await test_db["exam_recommendations"].delete_many({})
    await save_recommendations(
        test_db,
        [
            {
                "recommendation_id": "r-other",
                "run_id": "run-other",
                "course_code": "SE2032",
                "exam_id": "e1",
                "topic": "SQL",
                "bloom_level": "Apply",
                "priority_score": 0.5,
            }
        ],
    )
    assert await find_recommendations(test_db, "run-1") == []
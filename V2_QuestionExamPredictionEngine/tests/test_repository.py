from copy import deepcopy

from app.db import repository
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


def valid_document(
    *,
    student_id: str = "IT22145976",
    course_code: str = "SE3040",
    session_name: str = "Semester 1 Final Exam",
) -> dict:
    return {
        "student_id": student_id,
        "course": {"code": course_code, "name": "Software Engineering"},
        "assessment": {
            "session_name": session_name,
            "rubric_ref": "rubric-task-5",
            "total_score": 6.0,
            "max_score": 10.0,
            "percentage": 60.0,
        },
        "question_analysis": [],
        "topic_performance": [
            {
                "topic": "Testing",
                "questions_attempted": 1,
                "score": 6.0,
                "max_score": 10.0,
                "percentage": 60.0,
                "status": "Needs Improvement",
            }
        ],
        "bloom_performance": [
            {
                "level": "Understand",
                "questions_attempted": 1,
                "average_score": 60.0,
                "status": "Needs Improvement",
            }
        ],
        "learning_analysis": {
            "overall_performance": "Needs Improvement",
            "weak_topics": ["Testing"],
            "strong_topics": [],
            "weak_bloom_levels": ["Understand"],
            "weak_subtopics": ["Unit testing"],
            "learning_gaps": ["Review unit testing."],
        },
        "recommendations": [],
        "next_question_generation": {
            "recommended_bloom_level": "Apply",
            "recommended_difficulty": "Medium",
            "recommended_topics": ["Testing"],
            "number_of_questions": 5,
        },
        "model_metadata": {
            "bloom_model": "qwen3:8b",
            "bloom_model_type": "base",
            "grading_source": "rubric",
            "rag_context_used": False,
        },
    }


async def test_student_analytics_unique_compound_index_is_named(test_db):
    await create_indexes(test_db)
    info = await test_db["student_analytics"].index_information()

    assert info["uniq_student_analytics"]["key"] == [
        ("student_id", 1),
        ("course.code", 1),
        ("assessment.session_name", 1),
    ]
    assert info["uniq_student_analytics"]["unique"] is True


async def test_upsert_student_analytics_is_idempotent(test_db):
    student_id = "IT-TASK-5-IDEMPOTENT"
    document = valid_document(student_id=student_id)
    original = deepcopy(document)
    try:
        await repository.upsert_student_analytics(test_db, document)
        assert document == original

        document["assessment"]["total_score"] = 7.0
        document["assessment"]["percentage"] = 70.0
        await repository.upsert_student_analytics(test_db, document)
        saved = await test_db["student_analytics"].find(
            {"student_id": student_id}
        ).to_list(length=None)

        assert len(saved) == 1
        assert saved[0]["assessment"]["total_score"] == 7.0
        assert "_id" not in document
    finally:
        await test_db["student_analytics"].delete_many({"student_id": student_id})


async def test_find_student_analytics_filters_and_returns_id_free_copy(test_db):
    student_id = "IT-TASK-5-LOOKUP"
    document = valid_document(
        student_id=student_id,
        course_code="T5A101",
        session_name="Task 5 Analytics Session",
    )
    try:
        await repository.upsert_student_analytics(test_db, document)
        found = await repository.find_student_analytics(
            test_db, student_id, "T5A101", "Task 5 Analytics Session"
        )
        stored = await test_db["student_analytics"].find_one(
            {"student_id": student_id}
        )

        assert found["course"]["code"] == "T5A101"
        assert "_id" not in found
        assert "_id" in stored
        assert "_id" not in document
    finally:
        await test_db["student_analytics"].delete_many({"student_id": student_id})


async def test_find_graded_submissions_filters_out_other_statuses(test_db):
    student_ids = ["task-5-graded", "task-5-pending"]
    await test_db["submissions"].insert_many(
        [
            {"student_id": student_ids[0], "status": "graded"},
            {"student_id": student_ids[1], "status": "pending"},
        ]
    )
    try:
        found = await repository.find_graded_submissions(test_db)
        task_documents = [doc for doc in found if doc.get("student_id") in student_ids]

        assert [doc["student_id"] for doc in task_documents] == ["task-5-graded"]
    finally:
        await test_db["submissions"].delete_many({"student_id": {"$in": student_ids}})


async def test_find_course_prefers_exact_course_code(test_db):
    course_ids = ["task-5-course-exact", "task-5-course-fallback"]
    await test_db["courses"].insert_many(
        [
            {
                "_id": course_ids[0],
                "course_code": "T5C101",
                "name": "Exact course",
            },
            {
                "_id": course_ids[1],
                "subject_code": "T5C101",
                "session_name": "Task 5 Session",
                "name": "Fallback course",
            },
        ]
    )
    try:
        found = await repository.find_course_for_submission(
            test_db,
            {
                "course_code": "T5C101",
                "subject_code": "T5C101",
                "session_name": "Task 5 Session",
            },
        )

        assert found["_id"] == course_ids[0]
    finally:
        await test_db["courses"].delete_many({"_id": {"$in": course_ids}})


async def test_find_course_falls_back_to_subject_and_session(test_db):
    course_id = "task-5-course-sample"
    await test_db["courses"].insert_one(
        {
            "_id": course_id,
            "subject_code": "T5C102",
            "session_name": "Task 5 Sample Session",
        }
    )
    try:
        found = await repository.find_course_for_submission(
            test_db,
            {"subject_code": "T5C102", "session_name": "Task 5 Sample Session"},
        )

        assert found["_id"] == course_id
    finally:
        await test_db["courses"].delete_one({"_id": course_id})


async def test_find_rubric_prefers_exact_reference(test_db):
    rubric_ids = ["task-5-rubric-exact", "task-5-rubric-fallback"]
    await test_db["rubricCollection"].insert_many(
        [
            {
                "_id": rubric_ids[0],
                "subject_code": "T5R101",
                "session_name": "Exact session",
            },
            {
                "_id": rubric_ids[1],
                "subject_code": "T5R101",
                "session_name": "Exact session",
            },
        ]
    )
    try:
        found = await repository.find_rubric_for_submission(
            test_db,
            {
                "rubric_ref": rubric_ids[0],
                "subject_code": "T5R101",
                "session_name": "Exact session",
            },
        )

        assert found["_id"] == rubric_ids[0]
    finally:
        await test_db["rubricCollection"].delete_many({"_id": {"$in": rubric_ids}})


async def test_find_rubric_uses_sample_fallback_for_placeholder_reference(test_db):
    placeholder_id = "ObjectId('task-5-...')"
    fallback_id = "task-5-rubric-sample"
    await test_db["rubricCollection"].insert_many(
        [
            {
                "_id": placeholder_id,
                "subject_code": "WRONG",
                "session_name": "Wrong session",
            },
            {
                "_id": fallback_id,
                "subject_code": "T5R102",
                "session_name": "Task 5 Sample Session",
            },
        ]
    )
    try:
        found = await repository.find_rubric_for_submission(
            test_db,
            {
                "rubric_ref": placeholder_id,
                "subject_code": "T5R102",
                "session_name": "Task 5 Sample Session",
            },
        )

        assert found["_id"] == fallback_id
    finally:
        await test_db["rubricCollection"].delete_many(
            {"_id": {"$in": [placeholder_id, fallback_id]}}
        )

import pytest

import run_sample
from app.schemas.student import StudentAnalyticsDocument
from app.services import student_pipeline
from app.services.student_pipeline import (
    MaterializationFailure,
    MaterializationResult,
    materialize_student_analytics,
)
from run_sample import load_raw_sample_documents, seed_raw_samples


async def fake_semantics(_course, _question, _criteria):
    return {
        "status": "ok",
        "semantics": {
            "level": "Understand",
            "topic": "Databases",
            "subtopic": "DBMS Fundamentals",
            "confidence": 0.9,
            "reason": "The question asks for an explanation.",
        },
    }


async def fake_insights(_student_id, _evidence):
    return {"status": "degraded", "reason": "offline_test"}


def test_load_raw_sample_documents_loads_every_submission():
    courses, rubrics, submissions = load_raw_sample_documents()

    assert len(courses) == 1
    assert len(rubrics) == 1
    assert len(submissions) == 5
    assert all(submission["status"] == "graded" for submission in submissions)


def _sample_identity():
    courses, rubrics, submissions = load_raw_sample_documents()
    return {
        "course_codes": [course.get("subject_code", "IT2040") for course in courses],
        "sessions": [rubric["session_name"] for rubric in rubrics],
        "student_ids": [submission["student_id"] for submission in submissions],
    }


async def _clean_sample_documents(db):
    identity = _sample_identity()
    raw_filter = {
        "subject_code": {"$in": identity["course_codes"]},
        "session_name": {"$in": identity["sessions"]},
    }
    await db["courses"].delete_many(
        {"subject_code": {"$in": identity["course_codes"]}}
    )
    await db["rubricCollection"].delete_many(raw_filter)
    await db["submissions"].delete_many(
        {**raw_filter, "student_id": {"$in": identity["student_ids"]}}
    )
    await db["student_analytics"].delete_many(
        {
            "student_id": {"$in": identity["student_ids"]},
            "course.code": {"$in": identity["course_codes"]},
            "assessment.session_name": {"$in": identity["sessions"]},
        }
    )


async def test_seed_raw_samples_idempotently_upserts_sample_documents(test_db):
    await _clean_sample_documents(test_db)
    try:
        expected_counts = {"courses": 1, "rubrics": 1, "submissions": 5}
        assert await seed_raw_samples(test_db) == expected_counts
        assert await seed_raw_samples(test_db) == expected_counts

        identity = _sample_identity()
        assert await test_db["courses"].count_documents(
            {"subject_code": {"$in": identity["course_codes"]}}
        ) == 1
        assert await test_db["rubricCollection"].count_documents(
            {
                "subject_code": {"$in": identity["course_codes"]},
                "session_name": {"$in": identity["sessions"]},
            }
        ) == 1
        assert await test_db["submissions"].count_documents(
            {"student_id": {"$in": identity["student_ids"]}}
        ) == 5
    finally:
        await _clean_sample_documents(test_db)


async def test_seed_and_materialize_samples_saves_one_document_per_submission(
    test_db, monkeypatch
):
    await _clean_sample_documents(test_db)
    try:
        await seed_raw_samples(test_db)
        monkeypatch.setattr(
            student_pipeline, "classify_question_semantics", fake_semantics
        )
        monkeypatch.setattr(
            student_pipeline, "generate_student_insights", fake_insights
        )

        result = await materialize_student_analytics(test_db)
        student_ids = set(_sample_identity()["student_ids"])
        saved = await test_db["student_analytics"].find(
            {"student_id": {"$in": list(student_ids)}}
        ).to_list(length=None)

        assert result.failures == []
        assert len(saved) == 5
        assert {document["student_id"] for document in saved} == student_ids
        assert all(
            StudentAnalyticsDocument.model_validate(document) for document in saved
        )
    finally:
        await _clean_sample_documents(test_db)


class _CountCollection:
    async def count_documents(self, filters):
        assert filters == {}
        return 5


class _RunnerDatabase:
    def __getitem__(self, collection_name):
        assert collection_name == "student_analytics"
        return _CountCollection()


class _RunnerClient:
    def __init__(self, db):
        self.db = db

    def __getitem__(self, _database_name):
        return self.db

    def close(self):
        return None


@pytest.mark.parametrize(
    ("failures", "expected_exit"),
    [
        ([], 0),
        ([MaterializationFailure(student_id="student-2", reason="invalid marks")], 1),
    ],
)
async def test_main_runs_sample_workflow_and_reports_persisted_results(
    monkeypatch, capsys, failures, expected_exit
):
    db = _RunnerDatabase()
    events = []

    async def create_indexes(candidate_db):
        assert candidate_db is db
        events.append("indexes")

    async def seed(candidate_db):
        assert candidate_db is db
        assert events == ["indexes"]
        events.append("seed")
        return {"courses": 1, "rubrics": 1, "submissions": 5}

    async def materialize(candidate_db):
        assert candidate_db is db
        assert events == ["indexes", "seed"]
        events.append("materialize")
        return MaterializationResult(saved=["student-1"], failures=failures)

    monkeypatch.setattr(
        run_sample,
        "AsyncIOMotorClient",
        lambda _uri: _RunnerClient(db),
    )
    monkeypatch.setattr(run_sample, "create_indexes", create_indexes)
    monkeypatch.setattr(run_sample, "seed_raw_samples", seed)
    monkeypatch.setattr(
        run_sample, "materialize_student_analytics", materialize, raising=False
    )

    exit_code = await run_sample.main("sample_test")
    output = capsys.readouterr().out

    assert exit_code == expected_exit
    assert events == ["indexes", "seed", "materialize"]
    assert "database=sample_test" in output
    assert "seeded courses=1 rubrics=1 submissions=5" in output
    assert "saved student_ids: student-1" in output
    assert f"failures: {len(failures)}" in output
    assert "student_analytics count=5" in output
    if failures:
        assert "student-2: invalid marks" in output

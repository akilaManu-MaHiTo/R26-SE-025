import pytest

from app.services import exam_analytics as exam_service
from app.services.topic_canonicalization import canonicalize_topics


async def test_compute_exam_analytics_persists_and_returns_document(test_db, monkeypatch):
    from run_sample import seed_raw_samples
    from tests.test_run_sample import _clean_sample_documents, fake_semantics
    from app.services import student_pipeline

    monkeypatch.setattr(student_pipeline, "classify_question_semantics", fake_semantics)
    monkeypatch.setattr(student_pipeline, "generate_student_insights", lambda *a, **k: {"status": "degraded", "reason": "offline_test"})

    await _clean_sample_documents(test_db)
    await test_db["analytics_snapshots"].delete_many(
        {"subject_code": "IT2040", "session_name": "Final Examination"}
    )
    try:
        await seed_raw_samples(test_db)

        result = await exam_service.compute_exam_analytics(test_db, "IT2040", "Final Examination")

        assert result["subject_code"] == "IT2040"
        assert result["subject_name"] == "Database Management Systems"
        assert result["session_name"] == "Final Examination"
        # File now contains 9 raw rows (5 original + 4 nested duplicates with distinct _id)
        from run_sample import load_raw_sample_documents as _load_raw
        assert result["statistics"]["total_students"] == len(_load_raw()[2])
        saved = await test_db["analytics_snapshots"].find_one(
            {"subject_code": "IT2040", "session_name": "Final Examination"}
        )
        assert saved is not None
        saved_year = saved.get("year")
        saved_month = saved.get("month")
        saved_semester = saved.get("semester")
        status = await test_db["analyzedExams"].find_one(
            {"subject_code": "IT2040", "session_name": "Final Examination",
             "year": saved_year, "month": saved_month, "semester": saved_semester}
        )
        assert status is not None
        assert status["analyzed"] == "done"
        assert status["analyzed_at"]
    finally:
        await _clean_sample_documents(test_db)
        await test_db["analytics_snapshots"].delete_many(
            {"subject_code": "IT2040", "session_name": "Final Examination"}
        )
        await test_db["analyzedExams"].delete_many(
            {"subject_code": "IT2040", "session_name": "Final Examination"}
        )


@pytest.mark.asyncio
async def test_canonical_uses_rubric_max_not_estimation():
    # Rubric Q01 max 10, submissions score 5 each -> avg 50%, is_estimated False
    # Current code estimates via score/pct which fails when pct 0, so new code must use rubric.
    rubric_doc = {
        "_id": "rubric_test_01",
        "subject_code": "IT2040",
        "session_name": "Final Examination",
        "questions": [
            {"question_no": "01", "max_marks": 10, "criteria": [{"point": "c1", "marks": 10}]},
        ],
    }
    submissions = [
        {"student_id": "S1", "evaluation": {"results": [{"q_no": "01", "score": 5.0}]}},
        {"student_id": "S2", "evaluation": {"results": [{"q_no": "01", "score": 5.0}]}},
    ]

    class _FakeSubColl:
        def find(self, query, projection=None):  # noqa: ARG002
            class _Cur:
                async def to_list(self, length=None):  # noqa: ARG002
                    return submissions
            return _Cur()
        async def find_one(self, *a, **kw):  # noqa: ARG002
            return None

    class _FakeRubricColl:
        async def find_one(self, query, projection=None):  # noqa: ARG002
            # Return rubric when subject_code/session_name match
            if query.get("subject_code") == "IT2040" and query.get("session_name") == "Final Examination":
                return rubric_doc
            if query.get("_id") == "rubric_test_01":
                return rubric_doc
            return None
        def find(self, *a, **kw):  # noqa: ARG002
            class _Cur:
                async def to_list(self, length=None):  # noqa: ARG002
                    return []
            return _Cur()

    class _FakeDB(dict):
        def __getitem__(self, key):
            if key == "submissions":
                return _FakeSubColl()
            if key == "rubricCollection":
                return _FakeRubricColl()
            # fallback empty collection
            class _Empty:
                def find(self, *a, **kw):
                    class _Cur:
                        async def to_list(self, length=None):
                            return []
                    return _Cur()
                async def find_one(self, *a, **kw):
                    return None
            return _Empty()

    db_mock = _FakeDB()

    document = {
        "topic_performance": [
            {"topic": "Database Recovery Algorithms", "average_percentage": 0, "status": "Critical"},
        ],
        "question_performance": [
            {"question_id": "Q01", "topic": "Database Recovery Algorithms", "average_percentage": 0},
        ],
    }

    result = await canonicalize_topics(db_mock, document, "IT2040", "Final Examination")

    canonical = result["canonical_topic_performance"]
    assert len(canonical) == 1
    # total_score 10 (5+5), max per student 10 * 2 =20 => 50%
    assert canonical[0]["average_percentage"] == 50.0
    assert canonical[0]["is_estimated"] is False
    assert canonical[0]["student_count"] == 2
    assert canonical[0]["question_count"] == 1


@pytest.mark.asyncio
async def test_canonical_fallback_when_no_rubric():
    # No rubric -> fallback to estimation with is_estimated True
    submissions = [
        {"student_id": "S1", "evaluation": {"results": [{"q_no": "01", "score": 8.0}]}},
    ]

    class _FakeSubColl:
        def find(self, query, projection=None):
            class _Cur:
                async def to_list(self, length=None):
                    return submissions
            return _Cur()
        async def find_one(self, *a, **kw):
            return None

    class _FakeRubricColl:
        async def find_one(self, *a, **kw):
            return None
        def find(self, *a, **kw):
            class _Cur:
                async def to_list(self, length=None):
                    return []
            return _Cur()

    class _FakeDB(dict):
        def __getitem__(self, key):
            if key == "submissions":
                return _FakeSubColl()
            if key == "rubricCollection":
                return _FakeRubricColl()
            class _Empty:
                def find(self, *a, **kw):
                    class _Cur:
                        async def to_list(self, length=None):
                            return []
                    return _Cur()
                async def find_one(self, *a, **kw):
                    return None
            return _Empty()

    db_mock = _FakeDB()
    document = {
        "topic_performance": [
            {"topic": "Database Recovery Algorithms", "average_percentage": 0, "status": "Critical"},
        ],
        "question_performance": [
            {"question_id": "Q01", "topic": "Database Recovery Algorithms", "average_percentage": 80.0},
        ],
    }
    result = await canonicalize_topics(db_mock, document, "IT2040", "Final Examination")
    canonical = result["canonical_topic_performance"]
    assert len(canonical) == 1
    # fallback: q_score 8, pct 80 => est_max 10, avg 80
    assert canonical[0]["average_percentage"] == 80.0
    assert canonical[0]["is_estimated"] is True

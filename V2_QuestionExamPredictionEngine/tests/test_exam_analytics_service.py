from app.services import exam_analytics as exam_service


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
        assert result["statistics"]["total_students"] == 5
        saved = await test_db["analytics_snapshots"].find_one(
            {"subject_code": "IT2040", "session_name": "Final Examination"}
        )
        assert saved is not None
        status = await test_db["analyzedExams"].find_one(
            {"subject_code": "IT2040", "session_name": "Final Examination"}
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

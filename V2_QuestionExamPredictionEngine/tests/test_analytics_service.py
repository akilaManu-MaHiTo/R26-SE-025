from app.services import analytics
from app.services.analytics import run_analytics
from tests.fixtures.fixture_data import course_settings, sample_papers, sample_submissions


def _fake_classify(question_text):
    return {"status": "rules", "rules": {"confidence": "high"}}


async def test_run_analytics_persists_snapshot(test_db, monkeypatch):
    monkeypatch.setattr(analytics, "classify_question", _fake_classify)
    monkeypatch.setattr(analytics, "is_embedding_available", lambda: False)
    run = await run_analytics(
        test_db,
        run_id="run-1",
        course=course_settings(),
        papers=sample_papers,
        submissions=sample_submissions,
    )
    assert run.status == "ready"
    assert run.data_counts["attempts"] == 72
    assert run.data_counts["catalog"] == 6

    snapshot = await test_db["analytics_snapshots"].find_one({"run_id": "run-1"})
    assert snapshot is not None
    assert snapshot["cohort_metrics"]["student_count"] == 12

    recs = await test_db["exam_recommendations"].find({"run_id": "run-1"}).to_list(length=None)
    assert len(recs) > 0

    catalog = await test_db["question_catalog"].find({}).to_list(length=None)
    assert len(catalog) == 6
    assert all(doc.get("model_output", {}).get("status") == "rules" for doc in catalog)
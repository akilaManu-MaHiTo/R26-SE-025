from app.schemas.derived import AnalysisRun, AnalyticsSnapshot, ExamRecommendation
from app.schemas.derived import TopicMetrics


def test_snapshot_requires_published_fields():
    snapshot = AnalyticsSnapshot(
        snapshot_id="s1",
        run_id="r1",
        course_code="SE2032",
        exam_id="e1",
        algorithm_version="analytics-v1",
        cohort_metrics={"mean": 0.6},
        topic_metrics=[TopicMetrics(topic="SQL")],
        topic_bloom_matrix=[],
        evidence_statuses={},
        grade_distribution={},
        record_counts={},
        pass_threshold=0.5,
        min_students=10,
        min_attempts=2,
    )
    assert snapshot.published_at is None
    assert snapshot.created_at is not None


def test_recommendation_default_decision_is_pending():
    rec = ExamRecommendation(
        recommendation_id="rec-1",
        run_id="r1",
        course_code="SE2032",
        exam_id="e1",
        topic="Schema Refinement",
        bloom_level="Apply",
        question_type="problem_solving",
        mark_range=(1.0, 4.0),
        priority_score=0.75,
        component_breakdown={"weakness": 0.5},
        evidence={},
    )
    assert rec.decision == "pending"


def test_analysis_run_round_trip():
    run = AnalysisRun(run_id="r1", course_code="SE2032", exam_id="e1")
    assert run.status == "queued"
    assert run.algorithm_version == "analytics-v1"
    assert run.publication_state == "unpublished"
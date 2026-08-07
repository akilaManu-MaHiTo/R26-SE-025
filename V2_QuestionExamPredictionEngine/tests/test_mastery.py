import statistics

from app.analytics.mastery import (
    compute_cell_metrics,
    compute_mastery,
    compute_topic_bloom_matrix,
    compute_topic_metrics,
    normalized_score,
    topic_weight_for,
)
from app.schemas.derived import CellMetrics, TopicMetrics
from tests.fixtures.fixture_data import expected_attempt_records


def test_normalized_score():
    assert normalized_score(1.0, 2.0) == 0.5
    assert normalized_score(0.0, 2.0) == 0.0


def test_topic_weight_for_missing_topic_is_zero():
    assert topic_weight_for({"topic_assignments": [{"topic": "SQL", "weight": 1.0}]}, "JDBC") == 0.0


def test_compute_mastery_sql_apply():
    sql_apply = [a for a in expected_attempt_records if a["topic_assignments"][0]["topic"] == "SQL"]
    expected = sum(a["normalized_score"] * a["max_marks"] for a in sql_apply) / sum(
        a["max_marks"] for a in sql_apply
    )
    assert compute_mastery(expected_attempt_records, "SQL") == round(expected, 6)


def test_compute_mastery_empty_returns_none():
    assert compute_mastery([], "SQL") is None


def test_compute_cell_metrics_populates_counts():
    cell = compute_cell_metrics(expected_attempt_records, "Schema Refinement", "Analyze")
    assert isinstance(cell, CellMetrics)
    assert cell.attempt_count == 24
    assert cell.student_count == 12
    assert cell.evidence_status == "insufficient_evidence"


def test_compute_topic_metrics():
    tm = compute_topic_metrics(expected_attempt_records, "Logical Database Design")
    assert isinstance(tm, TopicMetrics)
    assert tm.attempt_count == 24


def test_matrix_covers_all_topic_bloom_cells():
    matrix = compute_topic_bloom_matrix(expected_attempt_records)
    filled = {(c.topic, c.bloom_level) for c in matrix if c.attempt_count > 0}
    assert ("SQL", "Apply") in filled
    assert ("Schema Refinement", "Analyze") in filled
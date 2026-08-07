from app.analytics.evidence import apply_evidence_statuses, cohort_summary, evidence_status
from app.schemas.derived import CellMetrics
from tests.fixtures.fixture_data import expected_attempt_records


def test_insufficient_when_below_minima():
    assert evidence_status(0.4, 5, 2, 0.5, 10, 2) == "insufficient_evidence"


def test_strength_when_above_threshold():
    assert evidence_status(0.8, 12, 24, 0.5, 10, 2) == "strength"


def test_confirmed_weakness_when_below_threshold():
    assert evidence_status(0.3, 12, 24, 0.5, 10, 2) == "confirmed_weakness"


def test_possible_weakness_path():
    assert evidence_status(0.3, 12, 24, 0.5, 10, 2) != "possible_weakness"


def test_cohort_summary_shape():
    summary = cohort_summary(expected_attempt_records)
    assert summary["student_count"] == 12
    assert summary["attempt_count"] == 72
    assert 0.0 <= summary["mean"] <= 1.0
    assert sum(summary["grade_distribution"].values()) == 72


def test_apply_evidence_statuses_mutates():
    cells = [CellMetrics(topic="SQL", bloom_level="Apply", mean=0.4, student_count=12, attempt_count=24)]
    apply_evidence_statuses(cells, 0.5, 10, 2)
    assert cells[0].evidence_status == "confirmed_weakness"
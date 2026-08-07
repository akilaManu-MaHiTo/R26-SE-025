import pytest

from app.analytics.recommender import (
    compute_priority,
    rank_recommendations,
    weakness_component,
)
from app.schemas.derived import CellMetrics


def test_weakness_component_high_when_low_mastery():
    assert weakness_component(0.2, 0.8, 0.5) == pytest.approx(0.4 + 0.24 + 0.1)


def test_weakness_component_treats_none_as_zero():
    assert weakness_component(None, None, None) == pytest.approx(0.0)


def test_compute_priority_default_weights():
    priority = compute_priority(1.0, 0.5, 0.5, 1.0)
    assert priority == pytest.approx(0.4 * 1.0 + 0.25 * 0.5 + 0.20 * 0.5 + 0.15 * 1.0)


def test_rank_recommendations_sorts_descending():
    strong = CellMetrics(topic="SQL", bloom_level="Apply", mastery=0.9, failure_rate=0.1,
                         student_count=12, attempt_count=24)
    weak = CellMetrics(topic="SQL", bloom_level="Analyze", mastery=0.2, failure_rate=0.8,
                       student_count=12, attempt_count=24)
    ranked = rank_recommendations([strong, weak])
    assert len(ranked) == 2
    assert ranked[0][0] is weak
    assert ranked[0][2] > ranked[1][2]
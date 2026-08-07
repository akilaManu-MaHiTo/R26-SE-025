from app.analytics.coverage import (
    coverage_gap,
    detect_gaps,
    observed_frequency,
    observed_share,
)
from tests.fixtures.fixture_data import expected_attempt_records


def test_observed_frequency_counts_distinct_questions():
    freq = observed_frequency(expected_attempt_records, "bloom_level")
    assert freq["Apply"] == 2
    assert freq["Analyze"] == 2
    assert freq["Understand"] == 2


def test_observed_share_normalizes():
    share = observed_share({"Apply": 2, "Analyze": 2, "Understand": 2})
    assert sum(share.values()) == 1.0


def test_coverage_gap_none_without_target():
    assert coverage_gap({"Apply": 1.0}, None) is None


def test_coverage_gap_zero_for_matching_target():
    assert coverage_gap({"Apply": 1.0}, {"Apply": 1.0}) == 0.0


def test_coverage_gap_detects_absence():
    gap = coverage_gap({"Apply": 0.5, "Analyze": 0.5}, {"Apply": 0.5, "Analyze": 0.25, "Remember": 0.25})
    assert gap > 0.0


def test_detect_gaps_finds_absent_bloom():
    result = detect_gaps(
        expected_attempt_records,
        topics=["SQL", "Schema Refinement", "Logical Database Design"],
        targets={"bloom": {"Remember": 0.1, "Apply": 0.3, "Analyze": 0.3, "Understand": 0.3}},
    )
    assert any("Remember" in g for g in result["bloom_gaps"])
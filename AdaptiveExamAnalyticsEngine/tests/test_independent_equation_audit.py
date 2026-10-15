"""Independent arithmetic oracles; known defects remain strict expected failures.

Run with --noconftest to avoid database/config fixtures. AST extraction executes
unchanged production function bodies without importing model or DB services.
"""
import ast
from collections import Counter
from datetime import date
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from app.analytics.diagram_analysis import compute_diagram_analysis, _performance_status
from app.analytics.recommendation_score import (
    ScoreWeights, bloom_gap_for_level, priority_from_score, recommendation_score,
)
from app.analytics.weakness import weakness_from_percentage, rank_weak_topics
from app.evaluation.metrics import accuracy, cohen_kappa, macro_f1, ndcg_at_k, precision_at_k


ROOT = Path(__file__).resolve().parents[1]


def isolated_functions(relative_path, names, **namespace):
    """Load actual source bodies, retaining line numbers, with explicit dependencies."""
    path = ROOT / relative_path
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    body = [ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)]
    body.extend(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names)
    assert len(body) == len(names) + 1
    namespace["__file__"] = str(path)
    exec(compile(ast.fix_missing_locations(ast.Module(body=body, type_ignores=[])), str(path), "exec"), namespace)
    return SimpleNamespace(**namespace)


student = isolated_functions(
    "app/analytics/student_document.py", {"percentage", "performance_status", "_topic_performance", "_bloom_performance"},
    STRONG_THRESHOLD=80, DEVELOPING_THRESHOLD=60, IMPROVEMENT_THRESHOLD=40,
    TopicPerformance=lambda **kw: SimpleNamespace(**kw), BloomPerformance=lambda **kw: SimpleNamespace(**kw),
)
exam = isolated_functions(
    "app/analytics/exam_analytics.py",
    {"_load_evidence_thresholds", "_evidence_status", "build_insights", "compute_exam_analytics_stats"},
    performance_status=student.performance_status,
    _ATTENTION_PRIORITY={"Critical": "Critical", "Needs Improvement": "High", "Developing": "Medium"},
)
signals = isolated_functions("app/services/recommendation.py", {"_compute_signals"}, Counter=Counter, date=date, Any=Any)


def normalized(scores, maxima=None, topic="SQL"):
    maxima = maxima or [10] * len(scores)
    return [
        {"overall": {"score": s, "maximum": m, "percentage": 100 * s / m if m else 0},
         "topic_performance": [{"topic": topic, "score": s, "max_score": m}],
         "bloom_performance": [],
         "question_performance": [{"question_no": "01", "topic": topic, "bloom_level": "Apply",
                                   "score": s, "max_score": m}]}
        for s, m in zip(scores, maxima)
    ]


def diagram(scores, maxima, criteria=None):
    return [
        {"student_id": str(i), "evaluation_result": {"total_score": s, "max_score": m,
                                                    "criteria_results": criteria or []}}
        for i, (s, m) in enumerate(zip(scores, maxima))
    ]


@pytest.mark.parametrize("value,status", [(0, "Critical"), (39.99, "Critical"), (40, "Needs Improvement"),
    (59.99, "Needs Improvement"), (60, "Developing"), (79.99, "Developing"), (80, "Strong"), (100, "Strong")])
def test_student_status_boundaries(value, status):
    assert student.performance_status(value) == status


def test_weighted_student_topic_and_bloom_are_ratios_of_marks():
    questions = [SimpleNamespace(topic="SQL", bloom_analysis=SimpleNamespace(level="Apply"),
                                performance=SimpleNamespace(score=s, max_score=m))
                 for s, m in [(1, 1), (0, 9)]]
    assert student._topic_performance(questions)[0].percentage == 10
    assert student._bloom_performance(questions)[0].average_score == 10
    assert student.percentage(1, 3) == 33.33
    with pytest.raises(ValueError):
        student.percentage(1, 0)


def test_exam_moments_pass_rate_and_weighted_aggregates():
    result = exam.compute_exam_analytics_stats(normalized([0, 2, 8, 10]), 0.5)
    assert result["statistics"]["average_percentage"] == 50
    assert result["statistics"]["median_percentage"] == 50
    assert result["statistics"]["std_percentage"] == round(math.sqrt(1700), 2)
    assert result["statistics"]["pass_rate"] == 50
    assert result["statistics"]["iqr_percentage"] == 90  # Exclusive quartiles: 5 and 95.
    result = exam.compute_exam_analytics_stats(normalized([1, 0], [1, 9]), 0.5)
    assert result["statistics"]["average_percentage"] == 50  # Equal students.
    assert result["topic_performance"][0]["average_percentage"] == 10  # Equal marks.
    assert result["bloom_performance"][0]["average_percentage"] == 10
    assert result["topic_bloom_matrix"][0]["average_percentage"] == 10


def test_discrimination_and_missed_criteria_independent_example():
    rows = normalized([0, 2, 8, 10])
    for row in rows:
        row["question_performance"][0]["criteria_performance"] = [
            {"awarded_marks": 1, "max_marks": 2, "achieved": True},
            {"awarded_marks": 2, "max_marks": 2, "achieved": True},
        ]
    question = exam.compute_exam_analytics_stats(rows, 0.5)["question_performance"][0]
    assert question["discrimination"] == 0.8  # (mean(80,100)-mean(0,20))/100.
    assert question["p_value"] == 50  # Percentage ease index, not a statistical p-value.
    assert question["missed_criterion_rate"] == 0.5


def test_weakness_convex_default_score_and_gap_boundaries():
    assert weakness_from_percentage(50) == 0.5
    assert weakness_from_percentage(50, 0.4, 0.2) == 0.43
    assert weakness_from_percentage(-10) == 1
    assert weakness_from_percentage(110) == 0
    assert recommendation_score(0.5, 1, 0, 1, 0.5) == 0.6
    assert recommendation_score(1, 1, 1, 1, 1) == 1
    assert recommendation_score(0, 0, 0, 0, 0) == 0
    assert bloom_gap_for_level("Apply", {"Apply": 0.1}, {"Apply": 0.4}) == 0.75
    assert bloom_gap_for_level("Create", {}, {"Create": 0}) == 0
    assert [priority_from_score(s) for s in [0.3999, 0.4, 0.6499, 0.65]] == ["Low", "Medium", "Medium", "High"]


def test_valid_classification_and_ranking_metrics():
    assert accuracy(["A", "B", "A", "B"], ["A", "A", "A", "B"]) == 0.75
    assert macro_f1(["A", "B", "A", "B"], ["A", "A", "A", "B"]) == pytest.approx(11 / 15)
    assert cohen_kappa(["A", "B", "A", "B"], ["A", "A", "A", "B"]) == 0.5
    assert precision_at_k([True, False, True], 2) == 0.5
    assert ndcg_at_k([False, True], 2) == pytest.approx(1 / math.log2(3))


def test_diagram_equal_maxima_rates_and_detection_counts():
    rows = diagram([0, 10], [10, 10])
    for row, status, marks in zip(rows, ["fail", "pass"], [0, 5]):
        row["evaluation_result"]["criteria_results"] = [
            {"criterion_id": 1, "criterion": "Keys", "awarded_marks": marks, "max_marks": 5, "status": status}]
    markings = [{"diagram_marks": marks, "diagram_details": {"entity_count": entities,
                 "relationship_count": 1, "label_count": 3, "detections": ["box"]}}
                for marks, entities in [(2, 2), (4, 4)]]
    result = compute_diagram_analysis(rows, markings)
    assert result["statistics"]["average_percentage"] == 50
    assert result["statistics"]["pass_rate"] == 50
    assert result["statistics"]["median_percentage"] == 50
    assert result["statistics"]["std_percentage"] == 50
    assert result["criterion_performance"][0]["fail_rate"] == 0.5
    assert result["criterion_performance"][0]["average_percentage"] == 50
    assert result["detection_summary"] == {"avg_entity_count": 3, "avg_relationship_count": 1,
           "avg_label_count": 3, "total_detections": 2, "avg_marking_score": 3}
    assert compute_diagram_analysis([], []) is None


def test_diagram_pass_rate_respects_each_students_denominator():
    result = compute_diagram_analysis(diagram([6, 60], [10, 100]), [])
    assert result["statistics"]["pass_rate"] == 100  # Both earned 60%.


def test_zero_diagram_maximum_has_defined_output():
    assert compute_diagram_analysis(diagram([0], [0]), [])["statistics"]["pass_rate"] == 0


def test_partial_diagram_criterion_uses_authoritative_maximum():
    criteria = [{"criterion_id": 1, "criterion": "Keys", "awarded_marks": 2, "max_marks": 5, "status": "partial"}]
    result = compute_diagram_analysis(diagram([2, 2], [5, 5], criteria), [])
    assert result["criterion_performance"][0]["average_percentage"] == 40


@pytest.mark.parametrize("pct", [40, 49.99, 60, 64.99])
@pytest.mark.xfail(strict=True, reason="EQ-04 diagram status diverges from student/config thresholds")
def test_diagram_status_matches_shared_performance_scale(pct):
    assert _performance_status(pct) == student.performance_status(pct)


@pytest.mark.xfail(strict=True, reason="EQ-05 negative weights pass sum validation and break [0,1] guarantee")
def test_negative_weights_cannot_produce_out_of_range_scores():
    weights = ScoreWeights(weakness=2, lecture_coverage=-1, tutorial_evidence=0, exam_relevance=0, bloom_gap=0)
    assert not weights.validates()


@pytest.mark.xfail(strict=True, reason="EQ-06 NDCG ideal must be drawn from all candidate relevance before truncation")
def test_ndcg_ideal_uses_relevant_candidates_below_cutoff():
    assert ndcg_at_k([True, False, True], 2) == pytest.approx(1 / (1 + 1 / math.log2(3)))


@pytest.mark.xfail(strict=True, reason="EQ-07 zero cutoff treated as full list by k or len")
def test_ndcg_zero_cutoff_is_zero():
    assert ndcg_at_k([True], 0) == 0


@pytest.mark.xfail(strict=True, reason="EQ-08 topic sorting divides by zero before guarded percentage calculation")
def test_exam_zero_maximum_does_not_crash_before_guard():
    assert exam.compute_exam_analytics_stats(normalized([0], [0]), 0.5)["topic_performance"][0]["average_percentage"] == 0


def test_topic_attempts_are_question_evidence_not_student_count():
    rows = normalized([0] * 10)
    result = exam.compute_exam_analytics_stats(rows, 0.5)
    assert result["topic_performance"][0]["evidence_status"] == "insufficient_evidence"  # Only one distinct question.


@pytest.mark.xfail(strict=True, reason="EQ-10 tutorial signal contradicts documented one-question endpoint 0.6")
def test_tutorial_one_practice_endpoint_matches_its_contract():
    result = signals._compute_signals([{"canonical_topic": "SQL", "source_type": "tutorial"}], 2026)
    assert result["tutorial_evidence"]["SQL"] == 0.6


@pytest.mark.xfail(strict=True, reason="EQ-11 accuracy silently drops unmatched labels")
def test_accuracy_rejects_unpaired_observations():
    with pytest.raises(ValueError):
        accuracy(["A"], ["A", "B"])


@pytest.mark.xfail(strict=True, reason="EQ-12 zero limit is treated as no limit")
def test_weak_topic_zero_limit_returns_no_rows():
    assert rank_weak_topics({"SQL": {"weakness": 0.9}}, limit=0) == []


def test_cosine_similarity_reference_vectors_without_model():
    tree = ast.parse((ROOT / "app/embeddings/embedder.py").read_text(encoding="utf-8"))
    method = next(node for cls in tree.body if isinstance(cls, ast.ClassDef) and cls.name == "Embedder"
                  for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "similarity")
    namespace = {"np": np}
    exec(compile(ast.Module(body=[method], type_ignores=[]), "embedder.py", "exec"), namespace)
    similarity = namespace["similarity"]
    assert similarity(None, [3, 4], [3, 4]) == pytest.approx(1)
    assert similarity(None, [1, 0], [0, 1]) == 0
    assert similarity(None, [1, 0], [-1, 0]) == -1
    assert similarity(None, [0, 0], [1, 0]) == 0  # Explicit implementation convention.

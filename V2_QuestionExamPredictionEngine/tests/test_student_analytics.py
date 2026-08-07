from app.analytics.student import (
    bloom_skill_profile,
    question_performance,
    rank_weakest_topics,
    student_exam_performances,
    topic_skill_profile,
)
from app.schemas.student import QuestionPerformance, StudentExamPerformance
from tests.fixtures.fixture_data import expected_attempt_records


def _stu1():
    return [a for a in expected_attempt_records if a["student_key"] == "stu-001"]


def test_student_exam_performances_groups_by_exam_and_grades():
    exams = student_exam_performances(_stu1(), 0.5)
    assert isinstance(exams, list) and all(isinstance(e, StudentExamPerformance) for e in exams)
    by_id = {e.exam_id: e for e in exams}
    assert set(by_id) == {"exam-2023", "exam-2024"}
    e2023 = by_id["exam-2023"]
    assert e2023.total_awarded == 6.0
    assert e2023.total_max == 6.0
    assert e2023.percentage == 100.0
    assert e2023.grade == "A"
    assert e2023.attempt_count == 3
    e2024 = by_id["exam-2024"]
    assert e2024.total_awarded == 5.0
    assert e2024.total_max == 6.0
    assert e2024.grade == "B"
    assert e2024.percentage == round(5.0 / 6.0 * 100.0, 4)


def test_question_performance_populates_fields():
    attempt = next(a for a in _stu1() if a["question_id"] == "exam-2023-01a")
    qp = question_performance(attempt, 0.5)
    assert isinstance(qp, QuestionPerformance)
    assert qp.topic == "SQL"
    assert qp.bloom_level == "Apply"
    assert qp.normalized_score == 1.0
    assert qp.passed is True
    assert qp.missed_criteria == []


def test_question_performance_reports_missed_criteria_and_fail():
    attempt = {
        "question_id": "exam-2023-01b",
        "question_number": "01",
        "part": "b",
        "question_text": "Find the primary key.",
        "topic_assignments": [{"topic": "Schema Refinement", "weight": 1.0}],
        "bloom_level": "Analyze",
        "question_type": "problem_solving",
        "awarded_marks": 1.0,
        "max_marks": 3.0,
        "normalized_score": round(1.0 / 3.0, 6),
        "feedback": "fix it",
        "criteria_breakdown": [
            {"criterion": "Closure", "awarded_marks": 0.0, "max_marks": 2.0, "met": False},
            {"criterion": "Declare key", "awarded_marks": 1.0, "max_marks": 1.0, "met": True},
        ],
    }
    qp = question_performance(attempt, 0.5)
    assert qp.passed is False
    assert [m.criterion for m in qp.missed_criteria] == ["Closure"]
    assert qp.missed_criteria[0].max_marks == 2.0
    assert qp.feedback == "fix it"


def test_bloom_skill_profile_per_bloom():
    skills = {s.bloom_level: s for s in bloom_skill_profile(_stu1(), 0.5)}
    assert skills["Apply"].mastery == 1.0
    assert skills["Apply"].attempt_count == 2
    assert skills["Analyze"].attempt_count == 2
    assert skills["Analyze"].mastery == round(5.0 / 6.0, 6)
    assert skills["Understand"].mastery == 1.0


def test_topic_skill_profile_ranks_weakest_first():
    profile = topic_skill_profile(_stu1(), 0.5)
    names = [s.topic for s in profile]
    assert names[0] == "Schema Refinement"
    by_topic = {s.topic: s for s in profile}
    assert by_topic["Schema Refinement"].rank == 1
    assert by_topic["Schema Refinement"].priority_score > 0.0
    assert by_topic["SQL"].mastery == 1.0
    assert by_topic["SQL"].attempt_count == 2


def test_rank_weakest_topics_returns_weakest_first():
    profile = topic_skill_profile(_stu1(), 0.5)
    ranked = rank_weakest_topics(profile)
    assert ranked[0] == "Schema Refinement"
    assert set(ranked) >= {"Schema Refinement", "SQL"}


import pytest

from app.analytics.student import cohort_comparison, deterministic_study_actions


def test_deterministic_study_actions_shape():
    actions = deterministic_study_actions(["Schema Refinement", "SQL"])
    assert len(actions) == 2
    assert actions[0].topic == "Schema Refinement"
    assert actions[0].source == "deterministic"
    assert actions[0].practice_topics == ["Schema Refinement", "SQL"]


def test_deterministic_study_actions_caps_at_three():
    actions = deterministic_study_actions(["A", "B", "C", "D"])
    assert len(actions) == 3


def test_cohort_comparison_percentile_and_delta():
    comparison = cohort_comparison(_stu1(), expected_attempt_records)
    sql = comparison["topics"]["SQL"]
    assert sql["student_mastery"] == 1.0
    assert sql["cohort_mastery"] == pytest.approx(round(8.5 / 12.0, 6))
    assert sql["delta"] == pytest.approx(round(1.0 - 8.5 / 12.0, 6))
    assert sql["percentile"] == pytest.approx(10 / 12)
    assert "Apply" in comparison["blooms"]
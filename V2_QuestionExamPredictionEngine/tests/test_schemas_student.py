from datetime import datetime, timezone

from app.schemas.student import (
    MissedCriterion,
    QuestionPerformance,
    StudentBloomSkill,
    StudentDashboard,
    StudentExamPerformance,
    StudentStudyAction,
    StudentTopicSkill,
)


def test_student_dashboard_shape():
    dash = StudentDashboard(
        student_key="stu-001",
        course_code="SE2032",
        run_id="run-1",
        generated_at=datetime.now(timezone.utc),
        exams=[
            StudentExamPerformance(
                exam_id="exam-2023",
                total_awarded=6.0,
                total_max=6.0,
                percentage=100.0,
                grade="A",
                attempt_count=3,
                question_performances=[
                    QuestionPerformance(
                        question_id="q1",
                        question_number="01",
                        part="a",
                        question_text="Write a SQL SELECT.",
                        topic="SQL",
                        bloom_level="Apply",
                        question_type="problem_solving",
                        awarded_marks=2.0,
                        max_marks=2.0,
                        normalized_score=1.0,
                        passed=True,
                        feedback="ok",
                        missed_criteria=[
                            MissedCriterion(criterion="JOIN", awarded_marks=0.0, max_marks=1.0)
                        ],
                    )
                ],
            )
        ],
        bloom_skills=[
            StudentBloomSkill(bloom_level="Apply", mastery=1.0, mean=1.0, attempt_count=1, evidence_status="strength")
        ],
        topic_skills=[
            StudentTopicSkill(topic="SQL", mastery=1.0, mean=1.0, attempt_count=1, evidence_status="strength", rank=1, priority_score=0.0)
        ],
        weakest_topics=["SQL"],
        cohort_comparison={"topics": {"SQL": {"student_mastery": 1.0, "cohort_mastery": 0.7, "delta": 0.3, "percentile": 0.5}}},
        recommendations=[
            StudentStudyAction(action="Review core concepts", topic="SQL", rationale="weak", practice_topics=["SQL"], source="deterministic")
        ],
    )
    assert dash.student_key == "stu-001"
    assert dash.exams[0].question_performances[0].missed_criteria[0].criterion == "JOIN"
    assert dash.recommendations[0].source == "deterministic"


def test_study_action_source_restricted_to_llm_or_deterministic():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        StudentStudyAction(action="a", topic="SQL", rationale="r", practice_topics=[], source="unsupported")
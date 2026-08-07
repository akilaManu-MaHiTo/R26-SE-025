import pydantic
import pytest

from app.schemas.catalog import CriteriaEvidence, QuestionAttempt, QuestionCatalog, TopicAssignment


def make_attempt() -> dict:
    return {
        "attempt_id": "att-1",
        "analysis_run_id": "run-1",
        "course_code": "SE2032",
        "exam_id": "exam-2023",
        "student_key": "stu-001",
        "question_id": "q-1",
        "question_number": "02",
        "part": "b",
        "question_text": "Find the primary key using attribute closure.",
        "topic_assignments": [
            {"topic": "Schema Refinement", "weight": 0.8},
            {"topic": "Logical Database Design", "weight": 0.2},
        ],
        "bloom_level": "Analyze",
        "question_type": "problem_solving",
        "key_concepts": ["functional dependency", "attribute closure"],
        "awarded_marks": 1.0,
        "max_marks": 2.0,
        "normalized_score": 0.5,
        "criteria_breakdown": [],
        "answer_text": "...",
        "feedback": "...",
        "classification_status": "model_suggested",
        "classification_confidence": "medium",
        "algorithm_version": "analytics-v1",
    }


def test_topic_weights_must_sum_to_one():
    with pytest.raises(pydantic.ValidationError):
        QuestionCatalog(
            **{**make_attempt(), "question_id": "q-1", "student_key": None,
               "topic_assignments": [{"topic": "SQL", "weight": 0.7}]}
        )


def test_normalized_score_must_be_between_zero_and_one():
    with pytest.raises(pydantic.ValidationError):
        QuestionAttempt(**{**make_attempt(), "normalized_score": 1.5})


def test_criteria_evidence_round_trip():
    ev = CriteriaEvidence(criterion="c", awarded_marks=0.5, max_marks=2.0, met=False, evidence="e")
    assert ev.met is False
    assert ev.awarded_marks == 0.5


def test_question_attempt_requires_attempt_id():
    with pytest.raises(pydantic.ValidationError):
        QuestionAttempt(**{**make_attempt(), "attempt_id": None})
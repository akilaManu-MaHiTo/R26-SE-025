import pytest
from pydantic import ValidationError

from app.schemas.student import StudentAnalyticsDocument


def valid_document() -> dict:
    return {
        "student_id": "IT22145976",
        "course": {"code": "SE3040", "name": "Software Engineering"},
        "assessment": {"session_name": "Semester 1 Final Exam", "rubric_ref": "rubric-001", "total_score": 6.0, "max_score": 10.0, "percentage": 60.0},
        "question_analysis": [{"question_no": "01", "question": "Explain unit testing.", "topic": "Testing", "subtopic": "Unit testing", "bloom_analysis": {"level": "Understand", "confidence": 0.9, "reason": "It asks for an explanation."}, "performance": {"score": 6.0, "max_score": 10.0, "percentage": 60.0}, "criteria_performance": [{"criterion": "Defines unit testing", "max_marks": 4.0, "awarded_marks": 2.0, "achieved": True}, {"criterion": "Explains its purpose", "max_marks": 6.0, "awarded_marks": 4.0, "achieved": True}]}],
        "topic_performance": [{"topic": "Testing", "question_count": 1, "score": 6.0, "max_score": 10.0, "percentage": 60.0, "status": "Needs Improvement"}],
        "bloom_performance": [{"level": "Understand", "question_count": 1, "average_score": 60.0, "status": "Needs Improvement"}],
        "learning_analysis": {"overall_performance": "Needs Improvement", "weak_topics": ["Testing"], "strong_topics": [], "weak_bloom_levels": ["Understand"], "weak_subtopics": ["Unit testing"], "learning_gaps": ["Review why unit tests isolate behavior."]},
        "recommendations": [{"priority": "High", "topic": "Testing", "bloom_level": "Understand", "action": "Practice explaining unit-test purposes."}],
        "next_question_generation": {"recommended_bloom_level": "Apply", "recommended_difficulty": "Medium", "recommended_topics": ["Testing", "Unit testing"], "number_of_questions": 5},
        "model_metadata": {"bloom_model": "qwen3:8b", "bloom_model_type": "base", "grading_source": "rubric", "rag_context_used": False},
    }


def test_student_analytics_serializes_exact_top_level_contract():
    document = StudentAnalyticsDocument(**valid_document())
    assert set(document.model_dump(mode="json")) == {"student_id", "course", "assessment", "question_analysis", "topic_performance", "bloom_performance", "learning_analysis", "recommendations", "next_question_generation", "model_metadata"}
    assert document.assessment.percentage == 60.0
    assert document.question_analysis[0].criteria_performance[1].achieved is True
    metadata = document.model_dump(mode="json")["model_metadata"]
    assert set(metadata) == {"bloom_model", "bloom_model_type", "grading_source", "rag_context_used"}
    assert "bloom_model_name" not in metadata
    assert "model_type" not in metadata


def test_student_analytics_rejects_invalid_performance_percentage():
    data = valid_document()
    data["assessment"]["percentage"] = 101.0
    with pytest.raises(ValidationError):
        StudentAnalyticsDocument(**data)


def test_student_analytics_rejects_unknown_bloom_level():
    data = valid_document()
    data["question_analysis"][0]["bloom_analysis"]["level"] = "Guess"
    with pytest.raises(ValidationError):
        StudentAnalyticsDocument(**data)


@pytest.mark.parametrize(("path", "value"), [(("assessment", "total_score"), 11.0), (("question_analysis", 0, "performance", "score"), 11.0), (("question_analysis", 0, "criteria_performance", 0, "awarded_marks"), 5.0)])
def test_student_analytics_rejects_scores_above_their_maximum(path, value):
    data = valid_document()
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValidationError):
        StudentAnalyticsDocument(**data)

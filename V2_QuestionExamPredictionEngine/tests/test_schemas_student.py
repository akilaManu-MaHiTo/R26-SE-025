import pytest
from pydantic import ValidationError

from app.schemas.student import StudentAnalyticsDocument


def valid_document() -> dict:
    return {
        "student_id": "IT22145976",
        "subject_code": "IT2040",
        "subject_name": "Database Management Systems",
        "year": 2021,
        "month": 7,
        "semester": 1,
        "session_name": "Final Examination 2021",
        "overall_performance": {"score": 65.0, "maximum": 100.0, "percentage": 65.0, "status": "Needs Improvement"},
        "question_performance": [
            {
                "question_id": "Q01",
                "question_no": "01",
                "question_text": "Explain conceptual design.",
                "topic": "DBMS Design",
                "subtopic": "Conceptual design",
                "bloom_analysis": {"level": "Understand", "confidence": 0.9, "reason": "It asks for an explanation."},
                "performance": {"score": 6.0, "max_score": 8.0, "percentage": 75.0},
                "criteria_performance": [
                    {"criterion": "Explains Conceptual Design", "max_marks": 4.0, "awarded_marks": 3.0, "achieved": True},
                ],
            }
        ],
        "topic_performance": [
            {"topic": "JDBC", "questions_attempted": 2, "score": 19.0, "max_score": 25.0, "percentage": 76.0, "status": "Strong"}
        ],
        "bloom_performance": [
            {"level": "Understand", "questions_attempted": 1, "average_score": 75.0, "status": "Developing"}
        ],
        "learning_analysis": {
            "overall_performance": "Needs Improvement",
            "strong_topics": ["JDBC"],
            "developing_topics": ["DBMS Design"],
            "weak_topics": ["Database Programming"],
            "critical_topics": ["SQL"],
            "learning_gaps": [
                {"topic": "SQL", "subtopic": "Authentication and Authorization", "priority": "Critical"}
            ],
        },
        "recommendations": [
            {"topic": "SQL", "priority": "Critical", "action": "Review SQL Server authentication."}
        ],
        "next_question_strategy": {
            "recommended_topics": ["SQL", "Database Programming"],
            "recommended_bloom_levels": ["Understand", "Apply"],
            "recommended_difficulty": "Medium",
            "number_of_questions": 5,
        },
        "model_metadata": {
            "bloom_model": "qwen3:8b", "bloom_model_type": "base",
            "grading_source": "colab", "rag_context_used": True,
        },
        "generated_at": "2026-08-12T00:00:00Z",
        "analysis_version": "1.0",
    }


def test_student_analytics_serializes_exact_top_level_contract():
    document = StudentAnalyticsDocument(**valid_document())
    assert set(document.model_dump(mode="json")) == {
        "student_id", "subject_code", "subject_name", "year", "month",
        "semester", "session_name", "overall_performance",
        "question_performance", "topic_performance", "bloom_performance",
        "learning_analysis", "recommendations", "next_question_strategy",
        "model_metadata", "generated_at", "analysis_version",
    }
    assert document.overall_performance.percentage == 65.0
    assert document.question_performance[0].criteria_performance[0].achieved is True
    assert document.next_question_strategy.recommended_bloom_levels == ["Understand", "Apply"]


def test_student_analytics_rejects_invalid_percentage():
    data = valid_document()
    data["overall_performance"]["percentage"] = 101.0
    with pytest.raises(ValidationError):
        StudentAnalyticsDocument(**data)


def test_student_analytics_rejects_unknown_bloom_level():
    data = valid_document()
    data["question_performance"][0]["bloom_analysis"]["level"] = "Guess"
    with pytest.raises(ValidationError):
        StudentAnalyticsDocument(**data)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("overall_performance", "score"), 101.0),
        (("question_performance", 0, "performance", "score"), 9.0),
        (("question_performance", 0, "criteria_performance", 0, "awarded_marks"), 5.0),
    ],
)
def test_student_analytics_rejects_scores_above_their_maximum(path, value):
    data = valid_document()
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValidationError):
        StudentAnalyticsDocument(**data)

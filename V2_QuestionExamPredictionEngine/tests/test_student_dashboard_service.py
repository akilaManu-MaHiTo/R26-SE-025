from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.schemas.student import StudentAnalyticsDocument
from app.services import student_dashboard
from app.services.student_dashboard import (
    StudentDashboardNotFound,
    get_student_dashboard,
)


def valid_document() -> dict:
    return {
        "student_id": "IT22145976",
        "course": {"code": "SE3040", "name": "Software Engineering"},
        "assessment": {
            "session_name": "Semester 1 Final Exam",
            "rubric_ref": "rubric-001",
            "total_score": 6.0,
            "max_score": 10.0,
            "percentage": 60.0,
        },
        "question_analysis": [],
        "topic_performance": [
            {
                "topic": "Testing",
                "questions_attempted": 1,
                "score": 6.0,
                "max_score": 10.0,
                "percentage": 60.0,
                "status": "Needs Improvement",
            }
        ],
        "bloom_performance": [
            {
                "level": "Understand",
                "questions_attempted": 1,
                "average_score": 60.0,
                "status": "Needs Improvement",
            }
        ],
        "learning_analysis": {
            "overall_performance": "Needs Improvement",
            "weak_topics": ["Testing"],
            "strong_topics": [],
            "weak_bloom_levels": ["Understand"],
            "weak_subtopics": ["Unit testing"],
            "learning_gaps": ["Review unit testing."],
        },
        "recommendations": [],
        "next_question_generation": {
            "recommended_bloom_level": "Apply",
            "recommended_difficulty": "Medium",
            "recommended_topics": ["Testing"],
            "number_of_questions": 5,
        },
        "model_metadata": {
            "bloom_model": "qwen3:8b",
            "bloom_model_type": "base",
            "grading_source": "rubric",
            "rag_context_used": False,
        },
    }


async def test_get_student_dashboard_returns_persisted_contract(monkeypatch):
    find = AsyncMock(return_value=valid_document())
    monkeypatch.setattr(student_dashboard, "find_student_analytics", find)
    db = object()

    result = await get_student_dashboard(
        db, "IT22145976", "SE3040", None
    )

    assert isinstance(result, StudentAnalyticsDocument)
    assert result.student_id == "IT22145976"
    assert result.topic_performance[0].questions_attempted == 1
    find.assert_awaited_once_with(db, "IT22145976", "SE3040", None)


async def test_get_student_dashboard_forwards_session_filter(monkeypatch):
    find = AsyncMock(return_value=valid_document())
    monkeypatch.setattr(student_dashboard, "find_student_analytics", find)
    db = object()

    await get_student_dashboard(
        db, "IT22145976", None, "Semester 1 Final Exam"
    )

    find.assert_awaited_once_with(
        db, "IT22145976", None, "Semester 1 Final Exam"
    )


async def test_get_student_dashboard_raises_when_no_document_exists(monkeypatch):
    monkeypatch.setattr(
        student_dashboard,
        "find_student_analytics",
        AsyncMock(return_value=None),
    )

    with pytest.raises(
        StudentDashboardNotFound,
        match="no saved analytics found for student",
    ):
        await get_student_dashboard(object(), "missing-student")


async def test_get_student_dashboard_validates_the_persisted_document(monkeypatch):
    invalid = valid_document()
    invalid["topic_performance"][0]["questions_attempted"] = -1
    monkeypatch.setattr(
        student_dashboard,
        "find_student_analytics",
        AsyncMock(return_value=invalid),
    )

    with pytest.raises(ValidationError):
        await get_student_dashboard(object(), "IT22145976")

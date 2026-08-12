from unittest.mock import AsyncMock

import pytest

from app.schemas.student import StudentAnalyticsDocument
from app.services import student_dashboard


def valid_document() -> dict:
    return {
        "student_id": "IT22145976",
        "exam_id": "IT2040@Final Examination 2021",
        "course": {"code": "IT2040", "name": "Database Management Systems"},
        "overall_performance": {
            "score": 65.0,
            "maximum": 100.0,
            "percentage": 65.0,
            "status": "Needs Improvement",
        },
        "question_performance": [],
        "topic_performance": [
            {
                "topic": "JDBC",
                "questions_attempted": 1,
                "score": 19.0,
                "max_score": 25.0,
                "percentage": 76.0,
                "status": "Strong",
            }
        ],
        "bloom_performance": [],
        "learning_analysis": {
            "overall_performance": "Needs Improvement",
            "strong_topics": [],
            "developing_topics": [],
            "weak_topics": [],
            "critical_topics": [],
            "learning_gaps": [],
        },
        "recommendations": [],
        "next_question_strategy": {
            "recommended_topics": [],
            "recommended_bloom_levels": [],
            "recommended_difficulty": "Medium",
            "number_of_questions": 5,
        },
        "model_metadata": {
            "bloom_model": "qwen3:8b",
            "bloom_model_type": "base",
            "grading_source": "colab",
            "rag_context_used": True,
        },
        "generated_at": "2026-08-12T00:00:00Z",
        "analysis_version": "1.0",
    }


async def test_ensure_loads_cached_analysis_without_generating(monkeypatch):
    find = AsyncMock(return_value=valid_document())
    build = AsyncMock()
    monkeypatch.setattr(student_dashboard, "find_student_analytics", find)
    monkeypatch.setattr(student_dashboard, "build_student_analytics", build)

    result = await student_dashboard.ensure_student_analytics(
        object(), "IT22145976", "IT2040", "Final Examination 2021"
    )

    assert isinstance(result, StudentAnalyticsDocument)
    build.assert_not_awaited()
    find.assert_awaited_once()


async def test_ensure_generates_and_saves_when_missing(monkeypatch):
    find = AsyncMock(return_value=None)
    built = StudentAnalyticsDocument.model_validate(valid_document())
    build = AsyncMock(return_value=built)
    save = AsyncMock()
    submission = AsyncMock(return_value={"student_id": "IT22145976"})
    monkeypatch.setattr(student_dashboard, "find_student_analytics", find)
    monkeypatch.setattr(student_dashboard, "find_graded_submission", submission)
    monkeypatch.setattr(student_dashboard, "build_student_analytics", build)
    monkeypatch.setattr(student_dashboard, "upsert_student_analytics", save)

    result = await student_dashboard.ensure_student_analytics(
        object(), "IT22145976", "IT2040", "Final Examination 2021"
    )

    build.assert_awaited_once()
    save.assert_awaited_once()
    assert result == built


async def test_ensure_raises_when_no_submission_exists(monkeypatch):
    find = AsyncMock(return_value=None)
    submission = AsyncMock(return_value=None)
    build = AsyncMock()
    monkeypatch.setattr(student_dashboard, "find_student_analytics", find)
    monkeypatch.setattr(student_dashboard, "find_graded_submission", submission)
    monkeypatch.setattr(student_dashboard, "build_student_analytics", build)

    with pytest.raises(
        student_dashboard.StudentNotFound, match="no graded submission"
    ):
        await student_dashboard.ensure_student_analytics(
            object(), "IT22145976", "IT2040", "Final Examination 2021"
        )

    build.assert_not_awaited()

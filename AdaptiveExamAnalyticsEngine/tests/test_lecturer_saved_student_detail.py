from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.api import lecturer
from app.db import repository


async def test_saved_detail_returns_existing_diagram_without_analysis(monkeypatch):
    monkeypatch.setattr(lecturer, "find_student_analytics", AsyncMock(return_value=None))
    generate = AsyncMock(side_effect=AssertionError("must not run analysis"))
    monkeypatch.setattr(lecturer, "ensure_student_analytics", generate)
    monkeypatch.setattr(repository, "find_diagram_evaluation_for_student", AsyncMock(return_value={
        "student_id": "IT21230101", "year": 2022, "month": 6, "semester": 1,
        "evaluation_result": {"total_score": 16, "max_score": 20},
    }))
    monkeypatch.setattr(repository, "find_diagram_marking_for_student", AsyncMock(return_value=None))
    monkeypatch.setattr(repository, "find_graded_submission", AsyncMock(return_value={"student_id": "IT21230101"}))

    detail = await lecturer.lecturer_student_detail(
        "IT2040", "Final Examination", "IT21230101",
        year=2022, month=6, semester=1, include_ai_tips=False, auto_analyze=False, db=object(),
    )

    assert detail["overall_performance"]["score"] == 16
    assert detail["diagram"]["evaluation"]["student_id"] == "IT21230101"
    assert detail["analysis_status"] == "diagram_only"
    generate.assert_not_awaited()


async def test_saved_detail_without_analysis_or_diagram_still_returns_423(monkeypatch):
    monkeypatch.setattr(lecturer, "find_student_analytics", AsyncMock(return_value=None))
    monkeypatch.setattr(repository, "find_diagram_evaluation_for_student", AsyncMock(return_value=None))
    monkeypatch.setattr(repository, "find_diagram_marking_for_student", AsyncMock(return_value=None))
    monkeypatch.setattr(repository, "find_graded_submission", AsyncMock(return_value={"student_id": "IT21230101"}))
    with pytest.raises(HTTPException) as error:
        await lecturer.lecturer_student_detail(
            "IT2040", "Final Examination", "IT21230101",
            year=2022, month=6, semester=1, include_ai_tips=False, auto_analyze=False, db=object(),
        )
    assert error.value.status_code == 423


def test_sample_v4_submissions_supply_required_analysis_metadata():
    from load_sample_v4 import COLLECTION_FILES, load_documents
    for submission in load_documents(COLLECTION_FILES["submissions"]):
        assert submission["evaluation"].get("grading_source") == "sample-v4-evaluator"
        assert submission["evaluation"].get("rag_context_used") is False

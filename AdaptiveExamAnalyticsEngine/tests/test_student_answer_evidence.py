from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from app.api import deps
from app.api.lecturer import router

app = FastAPI()
app.include_router(router, prefix="/api")


@pytest.mark.parametrize("result,transcript,answer,source", [
    ({"q_no": "1", "answer_excerpt": "Saved student answer", "slice_source": "regex"}, "", "Saved student answer", "regex"),
    ({"q_no": "01"}, "Q1\nLegacy OCR answer\nQ2\nOther answer", "Legacy OCR answer", "ocr"),
    ({"q_no": "01", "answer_excerpt": "", "slice_source": "empty"}, "Q1\nDo not replace grading evidence", None, "empty"),
    ({"q_no": "01"}, "No question headings", None, None),
])
async def test_question_evidence_uses_saved_answer_or_labelled_legacy_excerpt(result, transcript, answer, source):
    result = {**result, "feedback": "Missing dependency explanation", "justification": "Partial credit",
              "criteria_breakdown": [{"point": "Explain dependency", "awarded_marks": 1, "reason": "Incomplete"}]}
    collection = AsyncMock()
    collection.find_one.return_value = {"evaluation": {"results": [result]}, "cleaned_ocr_transcript": transcript,
                                        "raw_ocr_transcript": "PRIVATE OTHER ANSWERS"}
    async def database():
        return {"submissions": collection}
    app.dependency_overrides[deps.get_db] = database
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/lecturers/exams/IT2040/Final/student/S1/questions/01?year=2026&month=7&semester=1")
        assert response.status_code == 200
        evidence = response.json()
        assert evidence["answer_excerpt"] == answer
        assert evidence["slice_source"] == source
        assert evidence["feedback"] == "Missing dependency explanation"
        assert evidence["criteria_breakdown"][0]["reason"] == "Incomplete"
        assert "PRIVATE OTHER ANSWERS" not in response.text
        collection.find_one.assert_awaited_once_with({
            "student_id": "S1", "subject_code": "IT2040", "session_name": "Final",
            "year": 2026, "month": 7, "semester": 1, "status": "graded", "archived_at": None,
        }, sort=[("_id", -1)])
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("submission", [None, {"evaluation": {"results": [{"q_no": "02"}]}}])
async def test_missing_submission_or_question_does_not_return_other_evidence(submission):
    collection = AsyncMock()
    collection.find_one.return_value = submission
    async def database():
        return {"submissions": collection}
    app.dependency_overrides[deps.get_db] = database
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/lecturers/exams/IT2040/Final/student/S1/questions/01?year=2026&month=7&semester=1")
            assert response.status_code == 404
            incomplete = await client.get("/api/lecturers/exams/IT2040/Final/student/S1/questions/01")
            assert incomplete.status_code == 422
    finally:
        app.dependency_overrides.clear()

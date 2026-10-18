import asyncio
import json
from unittest.mock import AsyncMock

import pytest

from app.schemas.student import StudentAnalyticsDocument
from app.services import student_dashboard


def valid_document() -> dict:
    return {
        "student_id": "IT22145976",
        "subject_code": "IT2040",
        "subject_name": "Database Management Systems",
        "year": 2021,
        "month": 7,
        "semester": 1,
        "session_name": "Final Examination 2021",
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
        "analysis_version": student_dashboard.STUDENT_ANALYSIS_VERSION,
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


async def test_student_analysis_queue_is_fifo_and_reuses_saved_result(monkeypatch):
    saved = {}
    started = []
    release = asyncio.Event()
    first_started = asyncio.Event()
    waiting = asyncio.Event()
    progress = []

    async def find(_db, student_id, *_args):
        return saved.get(student_id)

    async def build(_db, submission, progress_callback=None):
        student_id = submission["student_id"]
        started.append(student_id)
        if student_id == "A":
            first_started.set()
            await release.wait()
        return StudentAnalyticsDocument.model_validate({**valid_document(), "student_id": student_id})

    async def save(_db, document):
        saved[document["student_id"]] = document

    def report(message):
        progress.append(message)
        if message == "queued":
            waiting.set()

    monkeypatch.setattr(student_dashboard, "find_student_analytics", find)
    monkeypatch.setattr(student_dashboard, "find_graded_submission", AsyncMock(side_effect=lambda _db, sid, *_args: {"student_id": sid}))
    monkeypatch.setattr(student_dashboard, "build_student_analytics", build)
    monkeypatch.setattr(student_dashboard, "upsert_student_analytics", save)

    first = asyncio.create_task(student_dashboard.ensure_student_analytics(None, "A", "IT2040", "Final"))
    await asyncio.wait_for(first_started.wait(), 1)
    second = asyncio.create_task(student_dashboard.ensure_student_analytics(None, "B", "IT2040", "Final", progress_callback=report))
    duplicate = asyncio.create_task(student_dashboard.ensure_student_analytics(None, "A", "IT2040", "Final"))
    try:
        await asyncio.wait_for(waiting.wait(), 1)
        assert started == ["A"]
    finally:
        release.set()
        await asyncio.gather(first, second, duplicate)
    assert started == ["A", "B"]
    assert progress[:2] == ["queued", "started"]
    assert set(saved) == {"A", "B"}


async def test_failed_analysis_releases_queue_for_next_student(monkeypatch):
    entered = asyncio.Event()
    release = asyncio.Event()

    async def build(_db, submission, progress_callback=None):
        if submission["student_id"] == "A":
            entered.set()
            await release.wait()
            raise RuntimeError("model failed")
        return StudentAnalyticsDocument.model_validate({**valid_document(), "student_id": "B"})

    monkeypatch.setattr(student_dashboard, "find_student_analytics", AsyncMock(return_value=None))
    monkeypatch.setattr(student_dashboard, "find_graded_submission", AsyncMock(side_effect=lambda _db, sid, *_args: {"student_id": sid}))
    monkeypatch.setattr(student_dashboard, "build_student_analytics", build)
    monkeypatch.setattr(student_dashboard, "upsert_student_analytics", AsyncMock())
    first = asyncio.create_task(student_dashboard.ensure_student_analytics(None, "A", "IT2040", "Final"))
    await asyncio.wait_for(entered.wait(), 1)
    second = asyncio.create_task(student_dashboard.ensure_student_analytics(None, "B", "IT2040", "Final"))
    release.set()
    with pytest.raises(RuntimeError, match="model failed"):
        await first
    assert (await asyncio.wait_for(second, 1)).student_id == "B"


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


async def test_student_stream_reports_queue_without_advancing_analysis_progress(monkeypatch):
    from app.api import lecturer

    async def ensure(*_args, progress_callback):
        for message in ("queued", "started", "classify q1", "insights A"):
            progress_callback(message)
            await asyncio.sleep(0)
        return valid_document()

    monkeypatch.setattr(lecturer, "find_student_analytics", AsyncMock(return_value=None))
    monkeypatch.setattr(lecturer, "find_graded_submission", AsyncMock(return_value={"evaluation": {"results": [{}]}}))
    monkeypatch.setattr(lecturer, "ensure_student_analytics", ensure)
    response = await lecturer.lecturer_student_detail_stream(
        "IT2040", "Final", "A", year=2026, month=7, semester=1, include_ai_tips=True, db={},
    )
    events = [json.loads(chunk.split("data: ", 1)[1]) async for chunk in response.body_iterator if chunk.startswith("event: progress")]
    assert all(event["progress"] == 0 for event in events if event["phase"] == "queued")
    started = next(event for event in events if event["phase"] == "analyzing")
    assert started["progress"] == 0
    classified = next(event for event in events if event["message"] == "classify q1")
    assert classified["stepsDone"] == 1
    assert events[-1]["progress"] == 100

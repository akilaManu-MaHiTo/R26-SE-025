"""Offline audit probes. Known privacy defects are strict expected failures.

Run with dotenv loading disabled before importing app.config; no real DB is used.
"""
from unittest.mock import AsyncMock

import httpx
import pytest

from app.api import dashboard, deps, lecturer
from app.main import app
from app.services.teaching_actions import _validate_llm_output


def _complete_without_io(coroutine):
    # Mocks and ASGI finish immediately; avoid Windows event-loop socket setup.
    try:
        coroutine.send(None)
    except StopIteration as completed:
        return completed.value
    finally:
        coroutine.close()
    raise RuntimeError("Audit coroutine unexpectedly suspended for real I/O")


async def _fake_db():
    return object()


async def _get(path):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://audit") as client:
        return await client.get(path)


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="DASH-01: anonymous caller can read another student's profile")
def test_anonymous_student_profile_requires_authentication(monkeypatch):
    monkeypatch.setattr(dashboard, "list_exams_for_student", AsyncMock(return_value=[]))
    monkeypatch.setattr("app.db.repository.find_user_by_student_id", AsyncMock(
        return_value={"email": "private@example.invalid"}))
    app.dependency_overrides[deps.get_db] = _fake_db
    try:
        response = _complete_without_io(_get("/api/students/OTHER-STUDENT/profile"))
        assert response.status_code in (401, 403)
    finally:
        app.dependency_overrides.pop(deps.get_db, None)


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="DASH-01: lecturer exam inventory is readable anonymously")
def test_anonymous_lecturer_inventory_requires_authentication(monkeypatch):
    monkeypatch.setattr(lecturer, "list_all_exams", AsyncMock(return_value=[]))
    app.dependency_overrides[deps.get_db] = _fake_db
    try:
        response = _complete_without_io(_get("/api/lecturers/exams"))
        assert response.status_code in (401, 403)
    finally:
        app.dependency_overrides.pop(deps.get_db, None)


def test_teaching_advice_cannot_invent_numeric_evidence():
    actual = _validate_llm_output([
        {"topic": "SQL", "priority": "Low", "performance_percentage": 99,
         "actions": ["Try a worked example"]},
        {"topic": "Invented topic", "actions": ["Invented action"]},
    ], [{"topic": "SQL", "priority": "High", "average_percentage": 45}], None)
    assert len(actual) == 1
    assert actual[0]["topic"] == "SQL"
    assert actual[0]["priority"] == "High"
    assert actual[0]["performance_percentage"] == 45

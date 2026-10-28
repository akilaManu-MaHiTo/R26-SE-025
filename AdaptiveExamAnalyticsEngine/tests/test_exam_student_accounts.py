"""Exam analysis provisions accounts without resetting existing credentials."""
from copy import deepcopy
from unittest.mock import AsyncMock

import pytest

from app.llm.roles.student_analysis import QuestionSemantics
from app.services import exam_analytics, student_accounts
from app.taxonomy import normalizer
from tests.test_exam_paper import immediate
from tests.test_lecturer_integrity_cleanup import Collection, Database, IDENTITY
from tests.test_student_data_ingestion import minimal_course, minimal_rubric, minimal_submission


@pytest.fixture(params=["student_id", "student_key"])
def analyzed_exam(monkeypatch, request):
    submission = {**minimal_submission("01", 3, 5), **IDENTITY}
    if request.param == "student_key":
        submission["student_key"] = submission.pop("student_id")
    submissions = AsyncMock(return_value=[submission])
    monkeypatch.setattr(exam_analytics, "find_graded_submissions_for_exam", submissions)
    monkeypatch.setattr(student_accounts, "find_graded_submissions_for_exam", submissions)
    monkeypatch.setattr(exam_analytics, "find_course_for_submission", AsyncMock(return_value=minimal_course()))
    monkeypatch.setattr(exam_analytics, "find_rubric_for_submission", AsyncMock(return_value={**minimal_rubric(), **IDENTITY}))
    monkeypatch.setattr(exam_analytics._student_pipeline, "_classify_questions", AsyncMock(return_value={
        "01": QuestionSemantics(level="Remember", topic="SQL", subtopic="SQL", confidence=0.9, reason="test")}))
    monkeypatch.setattr(normalizer, "load_taxonomy", AsyncMock(return_value={"sql": {"canonical_topic": "SQL", "aliases": []}}))
    monkeypatch.setattr(exam_analytics, "find_diagram_evaluations_for_exam", AsyncMock(return_value=[]))

    def analyze(db):
        return immediate(exam_analytics.compute_exam_analytics(db, "IT2040", "Final Examination", 2025, 4, 1))

    return analyze


def test_exam_analysis_creates_student_account_and_reanalysis_keeps_it(analyzed_exam):
    db = Database()
    analyzed_exam(db)
    account = immediate(db["users"].find_one({"email": "it21001234@my.sliit.lk"}))
    assert account is not None
    assert account["student_id"] == "IT21001234"
    assert account["role"] == "student"
    # Empty hashes use Student@123 at first login (covered by the server auth tests).
    assert account["password_hash"] == ""
    analyzed_exam(db)
    assert db["users"].docs == [account]


@pytest.mark.parametrize("email", ["it21001234@my.sliit.lk", "custom@example.edu"])
def test_exam_analysis_preserves_existing_student_password(analyzed_exam, email):
    account = {"email": email, "student_id": "IT21001234", "role": "student", "password_hash": "custom-hash"}
    db = Database(users=Collection([deepcopy(account)]))
    analyzed_exam(db)
    assert db["users"].docs == [account]


def test_provisioning_failure_does_not_mark_exam_done(analyzed_exam, monkeypatch):
    db = Database()
    monkeypatch.setattr(student_accounts, "ensure_student_account", AsyncMock(side_effect=RuntimeError("account write failed")))
    with pytest.raises(RuntimeError, match="account write failed"):
        analyzed_exam(db)
    assert not db["analyzedExams"].docs

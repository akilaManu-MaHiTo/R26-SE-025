from copy import deepcopy
from unittest.mock import AsyncMock

import pytest

from app.api import lecturer
from tests.test_exam_paper import fixture, immediate, ReadOnlyDatabase


def sources_with_pending_students():
    sources = fixture(essays=5, students=("S1", "S2", "S3", "S4", "S5"))
    sources["submissions"][2].update(status="processing", evaluation=None)
    for row in sources["submissions"][3:]:
        row.update(status="not_started", evaluation=None)
    sources["submissions"][0]["evaluation"]["results"][0]["criteria_breakdown"][0]["point"] = "Conflicting criterion"
    return sources


def student_rows(sources, monkeypatch):
    monkeypatch.setattr(lecturer, "find_student_analytics", AsyncMock(return_value=None))
    return immediate(lecturer.lecturer_student_list("IT2040", "Final Examination", year=2025, month=4, semester=1, db=ReadOnlyDatabase(sources)))


def test_all_five_students_have_separate_grading_statuses(monkeypatch):
    rows = student_rows(sources_with_pending_students(), monkeypatch)
    assert len(rows) == 5
    assert [r["grading_status"] for r in rows] == ["needs_review", "complete", "pending", "pending", "pending"]
    assert [r["components"]["essay"]["status"] for r in rows] == ["graded", "graded", "processing", "not_started", "not_started"]
    assert all(r["components"]["diagram"]["status"] == "graded" for r in rows)
    assert rows[2]["score"]["obtained"] is None
    assert rows[2]["score"]["percentage"] is None
    assert rows[2]["components"]["diagram"]["obtained"] == 12
    assert rows[2]["analysis_status"] == "diagram_only"
    assert rows[0]["review_reasons"]


def test_roster_student_without_either_submission_is_included(monkeypatch):
    sources = sources_with_pending_students()
    sources["submissions"] = sources["submissions"][:-1]
    sources["diagram_evaluations"] = sources["diagram_evaluations"][:-1]
    row = student_rows(sources, monkeypatch)[-1]
    assert row["student_id"] == "S5"
    assert row["components"]["essay"]["status"] == "missing_submission"
    assert row["components"]["diagram"]["status"] == "missing_submission"
    assert row["grading_status"] == "pending"
    assert row["score"]["obtained"] is None


def test_student_list_does_not_include_different_exam_or_regrade(monkeypatch):
    sources = sources_with_pending_students()
    other = deepcopy(sources["submissions"][0])
    other.update(_id="another-paper", student_id="OTHER", examKey="OTHER-EXAM", year=2027)
    sources["submissions"].append(other)
    monkeypatch.setattr(lecturer, "ensure_student_analytics", AsyncMock(side_effect=AssertionError("No analysis")))
    assert len(student_rows(sources, monkeypatch)) == 5
    lecturer.ensure_student_analytics.assert_not_awaited()


def test_duplicate_attempt_is_flagged_instead_of_presented_as_complete(monkeypatch):
    sources = sources_with_pending_students()
    duplicate = deepcopy(sources["submissions"][1]); duplicate["_id"] = "duplicate"
    sources["submissions"].append(duplicate)
    row = student_rows(sources, monkeypatch)[1]
    assert row["grading_status"] == "needs_review"
    assert row["components"]["essay"]["status"] == "needs_review"
    assert row["score"]["obtained"] is None


def test_duplicate_exam_key_reports_conflict_instead_of_zero_students(monkeypatch):
    from fastapi import HTTPException
    sources = sources_with_pending_students()
    other = deepcopy(sources["examkeys"][0]); other.update(_id="other-exam", examYear=2027)
    sources["examkeys"].append(other)
    with pytest.raises(HTTPException) as error:
        student_rows(sources, monkeypatch)
    assert error.value.status_code == 409

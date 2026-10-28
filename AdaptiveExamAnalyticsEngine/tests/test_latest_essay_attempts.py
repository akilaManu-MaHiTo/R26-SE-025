from copy import deepcopy

import pytest

from app.db import repository as repo
from app.services.lecturer_grading import build_lecturer_grading_rows
from app.services.exam_paper_definition import load_exam_paper_definition
from tests.test_exam_paper import fixture, immediate, ReadOnlyDatabase


def replacement_sources():
    sources = fixture(essays=1, diagram=False, students=("S1",))
    old = sources["submissions"][0]
    old["processed_at"] = "2026-10-20T10:00:00Z"
    new = deepcopy(old)
    new.update(_id="new-attempt", rubric_ref="new-rubric", processed_at="2026-10-20T11:00:00+00:00")
    new["evaluation"]["total_score"] = 4
    new["evaluation"]["results"][0]["score"] = 4
    new["evaluation"]["results"][0]["criteria_breakdown"][0]["awarded_marks"] = 4
    rubric = deepcopy(sources["rubrics"][0])
    rubric["_id"] = "new-rubric"
    sources["rubrics"].append(rubric)
    sources["submissions"].append(new)
    return sources


def test_latest_graded_attempt_and_linked_rubric_are_used_without_modifying_history():
    sources = replacement_sources()
    original = deepcopy(sources)
    loaded = immediate(repo.load_exam_paper_sources(ReadOnlyDatabase(sources), sources["examkeys"][0]["examKey"]))
    rows = build_lecturer_grading_rows(sources["examkeys"][0]["examKey"], loaded)
    assert rows[0]["grading_status"] == "complete"
    assert rows[0]["score"]["obtained"] == 4
    assert [r["_id"] for r in loaded["rubrics"]] == ["new-rubric"]
    assert sources == original
    preview = immediate(load_exam_paper_definition(ReadOnlyDatabase(sources), sources["examkeys"][0]))
    assert len(preview["essay_questions"]) == 1


@pytest.mark.parametrize("status", ["failed", "processing", "not_started"])
def test_newer_unfinished_attempt_does_not_replace_successful_grade(status):
    sources = replacement_sources()
    sources["submissions"][-1].update(status=status, evaluation=None)
    loaded = immediate(repo.load_exam_paper_sources(ReadOnlyDatabase(sources), sources["examkeys"][0]["examKey"]))
    rows = build_lecturer_grading_rows(sources["examkeys"][0]["examKey"], loaded)
    assert rows[0]["grading_status"] == "complete"
    assert rows[0]["score"]["obtained"] == 3


@pytest.mark.parametrize("reader", ["single", "exam", "student", "all"])
def test_analytics_readers_use_same_latest_grade(reader):
    sources = replacement_sources()
    db = ReadOnlyDatabase(sources)
    if reader == "single":
        rows = [immediate(repo.find_graded_submission(db, "S1", "IT2040", "Final Examination", 2025, 4, 1))]
    elif reader == "exam":
        rows = immediate(repo.find_graded_submissions_for_exam(db, "IT2040", "Final Examination", 2025, 4, 1))
    elif reader == "student":
        rows = immediate(repo.find_graded_submissions_for_student(db, "S1"))
    else:
        rows = immediate(repo.find_graded_submissions(db))
    assert [r["_id"] for r in rows] == ["new-attempt"]


@pytest.mark.parametrize("timestamp", [None, "invalid", "2026-10-20T10:00:00Z"])
def test_missing_invalid_or_tied_timestamps_still_require_review(timestamp):
    sources = replacement_sources()
    sources["submissions"][-1]["processed_at"] = timestamp
    loaded = immediate(repo.load_exam_paper_sources(ReadOnlyDatabase(sources), sources["examkeys"][0]["examKey"]))
    rows = build_lecturer_grading_rows(sources["examkeys"][0]["examKey"], loaded)
    assert rows[0]["grading_status"] == "needs_review"


def test_latest_selection_does_not_hide_different_exams():
    sources = replacement_sources()
    sources["submissions"][-1].update(year=2024, examKey="OTHER-EXAM")
    rows = immediate(repo.find_graded_submissions_for_student(ReadOnlyDatabase(sources), "S1"))
    assert len(rows) == 2


def test_students_can_use_different_rubric_versions_in_same_exam():
    sources = replacement_sources()
    second = deepcopy(sources["submissions"][0])
    second.update(_id="essay-S2", student_id="S2")
    sources["submissions"].append(second)
    loaded = immediate(repo.load_exam_paper_sources(ReadOnlyDatabase(sources), sources["examkeys"][0]["examKey"]))
    rows = build_lecturer_grading_rows(sources["examkeys"][0]["examKey"], loaded)
    assert [(r["student_id"], r["score"]["obtained"], r["grading_status"]) for r in rows] == [
        ("S1", 4, "complete"), ("S2", 3, "complete")]


def test_superseded_rubric_still_preserves_roster_only_students():
    sources = replacement_sources()
    sources["rubrics"][0]["exam_roster"]["students"].append({"student_id": "S2"})
    loaded = immediate(repo.load_exam_paper_sources(ReadOnlyDatabase(sources), sources["examkeys"][0]["examKey"]))
    rows = build_lecturer_grading_rows(sources["examkeys"][0]["examKey"], loaded)
    assert [r["student_id"] for r in rows] == ["S1", "S2"]
    assert rows[1]["components"]["essay"]["status"] == "missing_submission"


def test_archived_only_rubric_remains_available_for_roster_and_questions():
    sources = replacement_sources()
    sources["submissions"] = sources["submissions"][:1]
    sources["rubrics"] = sources["rubrics"][:1]
    sources["submissions"][0]["archived_reason"] = "superseded_by_new_batch"
    loaded = immediate(repo.load_exam_paper_sources(ReadOnlyDatabase(sources), sources["examkeys"][0]["examKey"]))
    rows = build_lecturer_grading_rows(sources["examkeys"][0]["examKey"], loaded)
    assert rows[0]["components"]["essay"]["status"] == "missing_submission"
    assert rows[0]["components"]["essay"]["maximum"] == 5


def test_conflicting_submission_on_old_roster_does_not_break_mixed_rubric_rows():
    sources = replacement_sources()
    sources["rubrics"][0]["exam_roster"]["students"].append({"student_id": "S2"})
    old_student = deepcopy(sources["submissions"][0])
    old_student.update(_id="essay-S3", student_id="S3")
    conflicting = deepcopy(sources["submissions"][-1])
    conflicting.update(_id="essay-S2", student_id="S2", year=2024)
    sources["submissions"].extend([old_student, conflicting])
    loaded = immediate(repo.load_exam_paper_sources(ReadOnlyDatabase(sources), sources["examkeys"][0]["examKey"]))
    rows = build_lecturer_grading_rows(sources["examkeys"][0]["examKey"], loaded)
    second = next(r for r in rows if r["student_id"] == "S2")
    assert second["grading_status"] == "needs_review"
    assert second["score"]["obtained"] is None

"""Offline regression cases found while auditing the lecturer dashboard."""
from copy import deepcopy
from unittest.mock import AsyncMock

import pytest

from app.db import repository as repo
from app.ingestion.student_data import StudentDataError, normalize_student_submission
from tests.test_exam_paper import immediate, ReadOnlyCollection
from tests.test_student_data_ingestion import minimal_course, minimal_rubric, minimal_submission


class Collection(ReadOnlyCollection):
    def find(self, query, projection=None):
        cursor = super().find(query, projection)
        cursor.sort = lambda *args, **kwargs: cursor
        return cursor

    async def replace_one(self, query, document, upsert=False):
        self.queries.append(query)
        self.docs = [d for d in self.docs if not all(d.get(k) == v for k, v in query.items())]
        self.docs.append(deepcopy(document))


class Database(dict):
    async def list_collection_names(self):
        return list(self)

    def __missing__(self, name):
        self[name] = Collection([])
        return self[name]


IDENTITY = dict(subject_code="IT2040", session_name="Final Examination", year=2025, month=4, semester=1)


def test_requested_exam_never_falls_back_to_another_year_or_archived_paper():
    db = Database(submissions=Collection([
        {**IDENTITY, "student_id": "S1", "status": "graded", "year": 2024},
        {**IDENTITY, "student_id": "S1", "status": "graded", "archived_at": "old"},
    ]))
    assert immediate(repo.find_graded_submission(db, "S1", "IT2040", "Final Examination", 2025, 4, 1)) is None


def test_duplicate_active_student_attempts_are_not_silently_selected():
    row = {**IDENTITY, "student_id": "S1", "status": "graded"}
    with pytest.raises(StudentDataError, match="Ambiguous"):
        immediate(repo.find_graded_submission(Database(submissions=Collection([row, row])), "S1", "IT2040", "Final Examination", 2025, 4, 1))


def test_class_request_without_dates_cannot_merge_exam_years(monkeypatch):
    from app.services import exam_analytics as service
    monkeypatch.setattr(service, "find_graded_submissions_for_exam", AsyncMock(return_value=[
        {**IDENTITY, "year": 2024}, {**IDENTITY, "year": 2025}]))
    with pytest.raises(StudentDataError, match="Select an exact exam"):
        immediate(service.compute_exam_analytics(Database(), "IT2040", "Final Examination"))


def test_student_analytics_for_two_years_do_not_replace_each_other():
    db = Database()
    for year in (2024, 2025):
        immediate(repo.upsert_student_analytics(db, {**IDENTITY, "student_id": "S1", "year": year}))
    for name in ("student_analytics", "studentExamAnalysis"):
        assert len(db[name].docs) == 2
        assert {"year", "month", "semester"} <= {k for k, _ in repo._UNIQUE_INDEXES[name]}


@pytest.mark.parametrize("reference, rubric", [
    ("missing", {"_id": "other", **IDENTITY}),
    ("r1", {"_id": "r1", **IDENTITY, "year": 2024}),
])
def test_rubric_reference_cannot_be_replaced_or_cross_exam(reference, rubric):
    db = Database(rubricCollection=Collection([rubric]))
    assert immediate(repo.find_rubric_for_submission(db, {**IDENTITY, "rubric_ref": reference})) is None


def test_numeric_rubric_reference_does_not_match_a_string_identifier():
    db = Database(rubricCollection=Collection([{"_id": "1", **IDENTITY}]))
    assert immediate(repo.find_rubric_for_submission(db, {**IDENTITY, "rubric_ref": 1})) is None


@pytest.mark.parametrize("evaluation", ["broken", ["wrong"], 42])
def test_malformed_saved_evaluation_is_unavailable(evaluation):
    from app.ingestion.student_data import saved_total_score
    assert saved_total_score({"evaluation": evaluation})["obtained"] is None


@pytest.mark.parametrize("score", [0, None])
def test_exam_inventory_never_turns_zero_or_missing_marks_into_full_marks(monkeypatch, score):
    db = Database(rubricCollection=Collection([{**IDENTITY, "questions": [{"max_marks": 35}]}]),
                  submissions=Collection([{**IDENTITY, "status": "graded", "student_id": "S1",
                      "evaluation": {"total_score": score, "max_score": 35}, "max_marks_paper_total": 35}]))
    monkeypatch.setattr(repo, "find_diagram_evaluations_for_exam", AsyncMock(return_value=[]))
    result = immediate(repo.list_all_exams(db))[0]
    assert result["average_percentage"] == (0 if score == 0 else None)


def test_other_year_snapshot_does_not_mark_exam_analyzed(monkeypatch):
    db = Database(rubricCollection=Collection([{**IDENTITY, "questions": []}]),
                  analytics_snapshots=Collection([{**IDENTITY, "year": 2024, "generated_at": "old"}]))
    monkeypatch.setattr(repo, "find_diagram_evaluations_for_exam", AsyncMock(return_value=[]))
    assert immediate(repo.list_all_exams(db))[0]["analyzed"] is False


@pytest.mark.parametrize("change", ["wrong_label", "missing_award", "duplicate", "mismatched_total", "nonfinite", "missing_question_number"])
def test_normalization_rejects_unverifiable_grading_evidence(change):
    rubric, submission = minimal_rubric(), minimal_submission("01", 3, 5)
    row = submission["evaluation"]["results"][0]
    criterion = row["criteria_breakdown"][0]
    if change == "wrong_label": criterion["point"] = "Different criterion"
    elif change == "missing_award": criterion.pop("awarded_marks")
    elif change == "duplicate": row["criteria_breakdown"].append(deepcopy(criterion))
    elif change == "mismatched_total": row["score"] = 5
    elif change == "nonfinite": criterion["awarded_marks"] = float("inf")
    else: rubric["questions"][0].pop("question_no"); row.pop("q_no")
    with pytest.raises((StudentDataError, ValueError)):
        normalize_student_submission(minimal_course(), rubric, submission)


@pytest.mark.parametrize("invalid_reference", [False, True])
def test_class_analytics_reports_bad_evidence_and_uses_each_students_rubric(monkeypatch, invalid_reference):
    from app.services import exam_analytics as service
    from app.llm.roles.student_analysis import QuestionSemantics
    from app.taxonomy import normalizer
    valid, invalid = minimal_submission("01", 3, 5), minimal_submission("01", 3, 5)
    valid.update(**IDENTITY, student_id="S1")
    invalid.update(**IDENTITY, student_id="S2", rubric_ref="missing" if invalid_reference else "rubric-1")
    rubric = {**minimal_rubric(), **IDENTITY}
    monkeypatch.setattr(service, "find_graded_submissions_for_exam", AsyncMock(return_value=[valid, invalid]))
    monkeypatch.setattr(service, "find_course_for_submission", AsyncMock(return_value=minimal_course()))
    monkeypatch.setattr(service, "find_rubric_for_submission", AsyncMock(side_effect=[rubric, None if invalid_reference else rubric]))
    monkeypatch.setattr(service._student_pipeline, "_classify_questions", AsyncMock(return_value={
        "01": QuestionSemantics(level="Remember", topic="SQL", subtopic="SQL", confidence=0.9, reason="test")}))
    monkeypatch.setattr(normalizer, "load_taxonomy", AsyncMock(return_value={"sql": {"canonical_topic": "SQL", "aliases": []}}))
    monkeypatch.setattr(service, "find_diagram_evaluations_for_exam", AsyncMock(return_value=[]))
    monkeypatch.setattr(service, "upsert_exam_analytics", AsyncMock())
    monkeypatch.setattr(service, "upsert_exam_analysis_status", AsyncMock())
    result = immediate(service.compute_exam_analytics(Database(), "IT2040", "Final Examination", 2025, 4, 1))
    assert result["statistics"]["total_students"] == (1 if invalid_reference else 2)
    assert result["canonical_topic_performance"][0]["average_percentage"] == 60
    assert result["canonical_topic_performance"][0]["is_estimated"] is False
    assert result["excluded_submissions"] == ([{"student_id": "S2", "reason": "Missing or conflicting essay rubric"}] if invalid_reference else [])


def test_failed_refresh_is_explicitly_labelled_stale(monkeypatch):
    from app.api import lecturer
    from tests.test_exam_analytics import exam_document
    monkeypatch.setattr(lecturer, "find_exam_analytics", AsyncMock(return_value=exam_document()))
    monkeypatch.setattr(lecturer, "compute_exam_analytics", AsyncMock(side_effect=StudentDataError("bad evidence")))
    async def no_diagram(db, doc, *args): return doc
    monkeypatch.setattr(lecturer, "_refresh_diagram_analysis", no_diagram)
    result = immediate(lecturer.lecturer_exam_analytics("IT2040", "Final Examination", 2022, 7, 1, object()))
    assert result.snapshot_status == "stale"
    assert "outdated" in result.refresh_warning


def test_current_version_alone_does_not_make_a_malformed_snapshot_complete():
    from app.api.lecturer import _is_complete_snapshot
    from app.services.exam_analytics import ANALYTICS_VERSION
    assert not _is_complete_snapshot({"analytics_version": ANALYTICS_VERSION,
        "canonical_topic_performance": [], "canonical_insights": [], "statistics": {}})


def test_teaching_actions_do_not_turn_objects_or_missing_text_into_advice():
    from app.services.teaching_actions import _validate_llm_output
    result = _validate_llm_output([{"topic": "SQL", "actions": [None, {"x": 1}, " Practice joins "]}],
        [{"topic": "SQL", "priority": "High", "average_percentage": 40}], None)
    assert result[0]["actions"] == ["Practice joins"]

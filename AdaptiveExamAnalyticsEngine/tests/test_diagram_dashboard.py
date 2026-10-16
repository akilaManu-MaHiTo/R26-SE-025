from copy import deepcopy

import pytest

from app.analytics.diagram_analysis import compute_diagram_analysis
from app.ingestion.diagram_data import normalize_diagram_evaluation
from tests.test_exam_paper import fixture, immediate, ReadOnlyDatabase, ReadOnlyCollection


def test_actual_agent_schema_becomes_dashboard_scores_and_criterion_results():
    sources = fixture()
    raw = sources["diagram_evaluations"][0]
    original = deepcopy(raw)
    value = normalize_diagram_evaluation(raw, sources["diagram_marking"][0])
    result = value["evaluation_result"]
    assert result["total_score"] == 12
    assert result["max_score"] == 20
    assert result["criteria_results"][0] == {
        "criterion_id": 1, "criterion": "Correct diagram", "awarded_marks": 12,
        "max_marks": 20, "status": "partial", "remarks": "Partial"}
    assert result["overall_feedback"] == "Review links"
    assert raw == original


def test_class_diagram_panel_uses_saved_agent_grades_and_evaluation_detections():
    sources = fixture()
    for record in sources["diagram_evaluations"]:
        record["diagram_details"].update(entity_count=2, relationship_count=1, label_count=5, detections=[{}])
    result = compute_diagram_analysis(sources["diagram_evaluations"], sources["diagram_marking"])
    assert result["statistics"]["total_students"] == 2
    assert result["statistics"]["average_score"] == 12
    assert result["statistics"]["average_percentage"] == 60
    assert result["criterion_performance"][0]["max_marks"] == 20
    assert result["detection_summary"]["avg_entity_count"] == 2
    assert result["detection_summary"]["avg_marking_score"] == 12


@pytest.mark.parametrize("score", [None, -1, 21, float("nan")])
def test_missing_or_invalid_agent_score_never_defaults_to_zero(score):
    sources = fixture()
    sources["diagram_evaluations"][0]["evaluation_result"]["agent_grading"]["agent_marks"] = score
    with pytest.raises(ValueError):
        normalize_diagram_evaluation(sources["diagram_evaluations"][0], sources["diagram_marking"][0])


def test_unrelated_guideline_is_never_used_as_marking_rubric():
    sources = fixture()
    sources["diagram_marking"][0]["_id"] = "WRONG"
    with pytest.raises(ValueError, match="guideline"):
        normalize_diagram_evaluation(sources["diagram_evaluations"][0], sources["diagram_marking"][0])


def test_legacy_result_schema_is_preserved():
    raw = {"student_id": "S1", "evaluation_result": {"total_score": 3, "max_score": 5, "criteria_results": []}}
    assert normalize_diagram_evaluation(raw, None) == raw


def test_repository_uses_plural_collection_and_exact_guideline_reference():
    from app.db.repository import find_diagram_evaluation_for_student, find_diagram_marking_for_student
    from bson import ObjectId
    sources = fixture()
    gid = ObjectId("6a945ccb9be219a81d49cf9c")
    sources["diagram_marking"][0]["_id"] = gid
    for record in sources["diagram_evaluations"]:
        record["guideline_object_id"] = str(gid)
        record["evaluation_result"]["guideline_object_id"] = str(gid)
    db = ReadOnlyDatabase(sources)
    evaluation = immediate(find_diagram_evaluation_for_student(db, "S1", "IT2040", "Final Examination", 2025, 4, 1))
    assert evaluation["evaluation_result"]["total_score"] == 12
    marking = immediate(find_diagram_marking_for_student(db, "S1", "IT2040", "Final Examination", 2025, 4, 1))
    assert marking["totalMarks"] == 20
    assert "student_id" not in db["diagram_marking"].queries[0]


def test_student_diagram_lookup_never_falls_back_to_a_different_exam_year():
    from app.db.repository import find_diagram_evaluation_for_student
    db = ReadOnlyDatabase(fixture())
    assert immediate(find_diagram_evaluation_for_student(db, "S1", "IT2040", "Final Examination", 2027, 4, 1)) is None


def test_cached_analytics_are_enriched_without_regrading(monkeypatch):
    from app.api import lecturer
    from unittest.mock import AsyncMock
    sources = fixture()
    monkeypatch.setattr(lecturer, "find_diagram_evaluations_for_exam", AsyncMock(return_value=sources["diagram_evaluations"]))
    monkeypatch.setattr(lecturer, "find_diagram_markings_for_exam", AsyncMock(return_value=sources["diagram_marking"]))
    cached = {"diagram_analysis": None, "statistics": {"total_students": 2}}
    refreshed = immediate(lecturer._refresh_diagram_analysis({}, cached, "IT2040", "Final Examination", 2025, 4, 1))
    assert refreshed["diagram_analysis"]["statistics"]["total_students"] == 2
    assert refreshed["diagram_analysis"]["statistics"]["average_percentage"] == 60


def cached_route_fixture(monkeypatch):
    from app.api import lecturer
    from tests.test_exam_analytics import exam_document
    from unittest.mock import AsyncMock
    sources = fixture()
    cached = exam_document()
    cached.update(year=2025, month=4, analytics_version=lecturer.ANALYTICS_VERSION,
                  canonical_topic_performance=[], canonical_insights=[], diagram_analysis=None)
    monkeypatch.setattr(lecturer, "find_exam_analytics", AsyncMock(return_value=cached))
    monkeypatch.setattr(lecturer, "find_diagram_evaluations_for_exam", AsyncMock(return_value=sources["diagram_evaluations"]))
    monkeypatch.setattr(lecturer, "find_diagram_markings_for_exam", AsyncMock(return_value=sources["diagram_marking"]))
    compute = AsyncMock(side_effect=AssertionError("Must not reclassify/regrade cached exam"))
    monkeypatch.setattr(lecturer, "compute_exam_analytics", compute)
    return lecturer, compute


def test_cached_http_analytics_route_returns_diagram_panel_without_regrading(monkeypatch):
    lecturer, compute = cached_route_fixture(monkeypatch)
    result = immediate(lecturer.lecturer_exam_analytics("IT2040", "Final Examination", year=2025, month=4, semester=1, db={}))
    assert result.diagram_analysis.statistics.average_percentage == 60
    compute.assert_not_awaited()


def test_cached_stream_also_refreshes_diagram_panel_without_regrading(monkeypatch):
    lecturer, compute = cached_route_fixture(monkeypatch)
    response = immediate(lecturer.lecturer_exam_analytics_stream("IT2040", "Final Examination", year=2025, month=4, semester=1, db={}))
    progress = immediate(response.body_iterator.__anext__())
    result = immediate(response.body_iterator.__anext__())
    assert "cached" in progress
    assert '"diagram_analysis"' in result
    assert '"average_percentage": 60.0' in result
    immediate(response.body_iterator.aclose())
    compute.assert_not_awaited()


def test_failed_agent_result_is_not_presented_as_a_successful_score():
    sources = fixture()
    sources["diagram_evaluations"][0]["evaluation_result"]["status"] = "error"
    with pytest.raises(ValueError, match="successful"):
        normalize_diagram_evaluation(sources["diagram_evaluations"][0], sources["diagram_marking"][0])


def test_explicit_conflicting_exam_key_is_rejected_despite_matching_metadata():
    from app.db.repository import find_diagram_evaluations_for_exam
    sources = fixture()
    sources["diagram_evaluations"][0]["examKey"] = "OTHER-EXAM"
    with pytest.raises(ValueError, match="exam"):
        immediate(find_diagram_evaluations_for_exam(ReadOnlyDatabase(sources), "IT2040", "Final Examination", 2025, 4, 1))


def test_same_student_with_two_guidelines_is_not_counted_twice():
    from app.db.repository import find_diagram_evaluations_for_exam
    sources = fixture()
    second = deepcopy(sources["diagram_evaluations"][0])
    second.update(_id="duplicate", guideline_object_id="different-guide")
    sources["diagram_evaluations"].append(second)
    with pytest.raises(ValueError, match="[Dd]uplicate|[Mm]ultiple"):
        immediate(find_diagram_evaluations_for_exam(ReadOnlyDatabase(sources), "IT2040", "Final Examination", 2025, 4, 1))


def test_class_analysis_does_not_merge_criterion_ids_from_different_rubrics():
    sources = fixture()
    other = deepcopy(sources["diagram_marking"][0]); other["_id"] = "other-guide"
    sources["diagram_marking"].append(other)
    sources["diagram_evaluations"][1]["guideline_object_id"] = "other-guide"
    sources["diagram_evaluations"][1]["evaluation_result"]["guideline_object_id"] = "other-guide"
    with pytest.raises(ValueError, match="rubric"):
        compute_diagram_analysis(sources["diagram_evaluations"], sources["diagram_marking"])

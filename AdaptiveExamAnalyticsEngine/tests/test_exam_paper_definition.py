from copy import deepcopy
import json

import pytest
from fastapi import HTTPException

from app.services.exam_paper_definition import load_exam_paper_definition
from tests.test_exam_paper import fixture, immediate, ReadOnlyDatabase


def preview(sources):
    return immediate(load_exam_paper_definition(ReadOnlyDatabase(sources), sources["examkeys"][0]))


def test_exam_preview_contains_questions_and_rubrics_without_student_data():
    sources = fixture(essays=5, students=("PRIVATE-STUDENT",))
    sources["rubrics"][0]["exam_roster"]["students"][0]["name"] = "PRIVATE-NAME"
    result = preview(sources)
    assert len(result["essay_questions"]) == 5
    assert len(result["diagram_rubrics"]) == 1
    assert result["maximum_marks"] == 45
    assert result["essay_questions"][0]["question_text"] == "Explain concept 1."
    assert result["essay_questions"][0]["criteria"][0]["point"] == "Criterion 1"
    assert result["diagram_rubrics"][0]["criteria"][0]["criterion"] == "Correct diagram"
    assert "PRIVATE" not in repr(result)
    assert "answer_excerpt" not in repr(result)
    assert "student_id" not in repr(result)
    assert result["validation"]["status"] == "incomplete"
    assert any("original diagram question" in m.lower() for m in result["validation"]["messages"])


def test_preview_does_not_require_essay_grading():
    sources = fixture(essays=5)
    sources["submissions"] = []
    assert len(preview(sources)["essay_questions"]) == 5


def test_keyless_metadata_supports_verified_string_and_month_name_formats():
    sources = fixture(essays=5)
    for record in sources["rubrics"] + sources["diagram_evaluations"]:
        record.pop("examKey")
        record.update(year="2025", month="April", semester="1")
    assert preview(sources)["maximum_marks"] == 45


def test_nonfinite_criteria_are_serializable_and_not_shown_as_valid_marks():
    sources = fixture(essays=5)
    sources["rubrics"][0]["questions"][0]["criteria"][0]["marks"] = float("nan")
    sources["diagram_marking"][0]["guideLines"][0]["expected"] = {"bad": float("inf")}
    result = preview(sources)
    json.dumps(result, allow_nan=False)
    assert result["essay_questions"][0]["criteria"][0]["marks"] is None
    assert result["maximum_marks"] is None


def test_canonical_identity_alias_does_not_allow_ambiguous_metadata_fallback():
    sources = fixture(essays=5)
    other = deepcopy(sources["examkeys"][0])
    other.update(_id="other", examKey="other-key", session="Final Examination")
    sources["examkeys"].append(other)
    with pytest.raises(ValueError, match="ambiguous"):
        preview(sources)


def test_endpoint_uses_exact_exam_session_and_returns_not_found_for_other_year():
    from app.api.lecturer import lecturer_exam_paper
    db = ReadOnlyDatabase(fixture(essays=5))
    result = immediate(lecturer_exam_paper("IT2040", "Final Examination", 2025, 4, 1, db))
    assert len(result["essay_questions"]) == 5
    with pytest.raises(HTTPException) as error:
        immediate(lecturer_exam_paper("IT2040", "Final Examination", 2027, 4, 1, db))
    assert error.value.status_code == 404


def test_endpoint_rejects_exam_identity_alias_collision():
    from app.api.lecturer import lecturer_exam_paper
    sources = fixture(essays=5)
    other = deepcopy(sources["examkeys"][0])
    other.update(_id="other", examKey="other-key", session="Final Examination")
    sources["examkeys"].append(other)
    with pytest.raises(HTTPException) as error:
        immediate(lecturer_exam_paper("IT2040", "Final Examination", 2025, 4, 1, ReadOnlyDatabase(sources)))
    assert error.value.status_code == 409


def test_conflicting_exam_key_does_not_attach_a_diagram_rubric():
    sources = fixture(essays=5)
    for record in sources["diagram_evaluations"]:
        record["examKey"] = "DIFFERENT-EXAM"
    result = preview(sources)
    assert not result["diagram_rubrics"]
    assert result["maximum_marks"] is None
    assert result["validation"]["status"] == "incomplete"


def test_invalid_rubric_marks_do_not_become_a_zero_maximum():
    sources = fixture(essays=5)
    sources["rubrics"][0]["questions"][0]["criteria"][0]["marks"] = None
    result = preview(sources)
    assert result["essay_questions"][0]["max_marks"] is None
    assert result["maximum_marks"] is None


def test_unrelated_diagram_guideline_is_not_used_when_no_reference_exists():
    sources = fixture(essays=5)
    sources["diagram_evaluations"] = []
    assert not preview(sources)["diagram_rubrics"]


def test_duplicate_question_definition_is_reported_without_adding_marks_twice():
    sources = fixture(essays=5)
    sources["rubrics"][0]["questions"].append(deepcopy(sources["rubrics"][0]["questions"][0]))
    result = preview(sources)
    assert result["maximum_marks"] is None
    assert result["validation"]["status"] == "incomplete"


def test_duplicate_canonical_exam_key_is_rejected():
    sources = fixture(essays=5)
    other = deepcopy(sources["examkeys"][0]); other.update(_id="duplicate-exam", examYear=2027)
    sources["examkeys"].append(other)
    with pytest.raises(ValueError, match="exam"):
        preview(sources)

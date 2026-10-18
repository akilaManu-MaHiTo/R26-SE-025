"""Criterion matching tolerates an unmatched terminal bracket, never different words."""
from copy import deepcopy

import pytest

from app.ingestion.student_data import normalize_student_submission, StudentDataError
from app.ingestion.criterion_labels import criterion_label_key
from app.services.exam_paper import reconstruct_exam_paper
from tests.test_exam_paper import fixture
from tests.test_student_data_ingestion import minimal_course, minimal_rubric, minimal_submission


LABEL = "Explains ternary relationships with an attribute (e.g., quantity) shared by all entities"


def test_internal_bullet_parenthesis_does_not_remove_a_balanced_suffix():
    label = "a) Explain entities (e.g. Course)"
    assert criterion_label_key(label) == label.casefold()
    assert criterion_label_key(label) != criterion_label_key(label[:-1])


def test_normalized_duplicate_labels_remain_ambiguous():
    rubric, submission = minimal_rubric(), minimal_submission("01", 3, 5)
    submission["evaluation"]["results"][0]["criteria_breakdown"].append({"point": "Correct answer)", "awarded_marks": 0})
    with pytest.raises(StudentDataError, match="duplicate criterion labels"):
        normalize_student_submission(minimal_course(), rubric, submission)


def test_extra_unmatched_terminal_parenthesis_does_not_exclude_an_essay():
    rubric, submission = minimal_rubric(), minimal_submission("01", 3, 5)
    rubric["questions"][0]["criteria"][0]["point"] = LABEL + ")"
    submission["evaluation"]["results"][0]["criteria_breakdown"][0]["point"] = LABEL
    assert normalize_student_submission(minimal_course(), rubric, submission).questions[0].score == 3


def test_combined_grade_uses_the_same_label_rule_without_changing_source_records():
    sources = fixture(essays=5)
    sources["rubrics"][0]["questions"][0]["criteria"][0]["point"] = LABEL + ")"
    for sub in sources["submissions"]:
        sub["evaluation"]["results"][0]["criteria_breakdown"][0]["point"] = LABEL
    before = deepcopy(sources)
    paper = reconstruct_exam_paper(sources["examkeys"][0]["examKey"], sources)
    assert all(s["grading"]["status"] == "complete" for s in paper["students"])
    assert sources == before


@pytest.mark.parametrize("different", ["Explains binary relationships", LABEL.replace("quantity", "price"), LABEL.replace("(e.g., quantity)", "e.g., quantity")])
def test_real_label_differences_still_require_review(different):
    rubric, submission = minimal_rubric(), minimal_submission("01", 3, 5)
    rubric["questions"][0]["criteria"][0]["point"] = LABEL
    submission["evaluation"]["results"][0]["criteria_breakdown"][0]["point"] = different
    with pytest.raises(StudentDataError, match="Question 01.*criterion labels"):
        normalize_student_submission(minimal_course(), rubric, submission)

from copy import deepcopy

import pytest

from app.db import repository as repo
from tests.test_exam_paper import fixture, immediate
from tests.test_lecturer_integrity_cleanup import Collection, Database


@pytest.mark.parametrize("essay", [True, False])
def test_duplicate_diagrams_do_not_block_exam_inventory(essay):
    sources = fixture()
    duplicate = deepcopy(sources["diagram_evaluations"][0])
    duplicate["_id"] = "duplicate"
    db = Database({name: Collection(rows) for name, rows in sources.items()})
    db["rubricCollection"] = Collection(sources["rubrics"])
    db["diagram_evaluations"].docs.append(duplicate)
    if not essay:
        db["submissions"] = Collection([])
    healthy = {**sources["rubrics"][0], "subject_code": "HEALTHY", "examKey": "EXAM-HEALTHY"}
    db["rubricCollection"].docs.append(healthy)

    exams = immediate(repo.list_all_exams(db))

    assert len(exams) == 2
    exam = next(row for row in exams if row["course_code"] == "IT2040")
    if essay:
        assert exam["average_percentage"] == 60
        assert exam["student_count"] == 2
        assert exam["score_basis"] == "Essay"
        assert exam.get("grading_warning") is None
    else:
        assert exam["average_percentage"] is None
        assert exam["student_count"] is None
        assert exam["graded_student_count"] is None
        assert "Duplicate" in exam["grading_warning"]
    # Inventory availability must not weaken grade validation.
    with pytest.raises(ValueError, match="Duplicate"):
        immediate(repo.find_diagram_evaluations_for_exam(db, "IT2040", "Final Examination", 2025, 4, 1))


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("timestamps", [(100, 200), (200, 200), (None, None)])
def test_inventory_uses_latest_rubric_per_exam_key(reverse, timestamps):
    rubric = fixture()["rubrics"][0]
    old = {**rubric, "_id": "001", "parsed_at": timestamps[0], "questions": []}
    latest = {**rubric, "_id": "002", "parsed_at": timestamps[1]}
    rows = [old, latest]
    if reverse:
        rows.reverse()
    db = Database(rubricCollection=Collection(rows))

    exams = immediate(repo.list_all_exams(db))

    assert len(exams) == 1
    assert exams[0]["question_count"] == 4
    assert exams[0]["total_marks"] == 20
    assert db["rubricCollection"].docs == rows


@pytest.mark.parametrize("key", [None, ""])
def test_inventory_keeps_rubrics_without_exam_keys_separate(key):
    rubric = {**fixture()["rubrics"][0], "examKey": key}
    db = Database(rubricCollection=Collection([
        {**rubric, "_id": "001"}, {**rubric, "_id": "002", "year": 2024},
    ]))
    assert len(immediate(repo.list_all_exams(db))) == 2

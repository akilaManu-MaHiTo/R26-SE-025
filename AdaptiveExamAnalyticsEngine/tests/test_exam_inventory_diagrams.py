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
    healthy = {**sources["rubrics"][0], "subject_code": "HEALTHY"}
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

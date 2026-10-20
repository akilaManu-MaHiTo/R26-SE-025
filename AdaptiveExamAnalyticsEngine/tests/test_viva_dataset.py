"""The viva export must pass the lecturer's complete-grade rules, not just ingestion."""
from collections import Counter
import json

from bson import json_util

from app.services.lecturer_grading import build_lecturer_grading_rows
from scripts.build_viva_dataset import EXAM_KEY, build_dataset


def test_all_fifty_viva_grades_are_complete_with_separate_essay_and_diagram_totals():
    docs = json_util.loads(json.dumps(build_dataset()))
    sources = {
        "examkeys": [{"_id": "synthetic-registry", "examKey": EXAM_KEY,
                      "subjectCode": "IT2040", "examYear": 2022, "examMonth": "June",
                      "examSemester": 1, "session": "Final",
                      "examStructure": ["Essay"] * 4 + ["Diagram"]}],
        "rubrics": docs["rubricCollection"], "submissions": docs["submissions"],
        "diagram_marking": docs["diagram_marking"],
        "diagram_evaluations": docs["diagram_evaluation"],
    }
    rows = build_lecturer_grading_rows(EXAM_KEY, sources)
    assert len(rows) == 50
    assert Counter(r["grading_status"] for r in rows) == {"complete": 50}
    for row in rows:
        essay, diagram = row["components"]["essay"], row["components"]["diagram"]
        assert essay["status"] == diagram["status"] == "graded"
        assert essay["maximum"] == 80 and diagram["maximum"] == 20
        assert row["score"]["obtained"] == essay["obtained"] + diagram["obtained"]
        assert row["score"]["maximum"] == 100

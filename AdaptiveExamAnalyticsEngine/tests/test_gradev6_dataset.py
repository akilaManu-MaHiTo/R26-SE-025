from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from xml.etree import ElementTree

import pytest

from scripts.seed_gradev6 import build_dataset, validate_dataset, require_empty_target, load_full_sources
from tests.test_exam_paper import fixture, immediate, ReadOnlyDatabase


def source_fixture():
    source = fixture(essays=5, students=tuple(f"REAL-{i}" for i in range(5)))
    source["rubrics"][0]["subject_name"] = "DBMS"
    limits = [[4, 3, 3], [3, 2, 2], [2, 2, 1, 1], [2, 2, 2], [3, 3]]
    for q, marks in zip(source["rubrics"][0]["questions"], limits):
        q.update(max_marks=sum(marks), criteria=[{"point": f"{q['question_no']} criterion {i}", "marks": m} for i, m in enumerate(marks)])
    source["rubrics"][0]["exam_roster"]["row_count"] = 5
    guide = source["diagram_marking"][0]
    guide["guideLines"] = [{"id": i, "criterion": f"Criterion {i}", "marks": 2 if i < 10 else 1} for i in range(1, 12)]
    for index, sub in enumerate(source["submissions"]):
        if index > 1:
            sub.update(status="processing" if index == 2 else "not_started", evaluation=None, cleaned_ocr_transcript=None)
            continue
        sub["cleaned_ocr_transcript"] = f"Original real answer {index}"
        sub["evaluation"].update(total_score=35, max_score=35)
        for q, row in zip(source["rubrics"][0]["questions"], sub["evaluation"]["results"]):
            row.update(score=q["max_marks"], criteria_breakdown=[{"point": c["point"], "awarded_marks": c["marks"]} for c in q["criteria"]])
    for doc in source["diagram_evaluations"]:
        rows = [{"id": c["id"], "marks": c["marks"], "reason": "Original saved evaluation"} for c in guide["guideLines"]]
        doc.update(agent_marks=20)
        doc["evaluation_result"].update(agent_marks=20, agent_grading={"agent_marks": 20, "max_marks": 20, "criterion_results": rows})
    return source


def dataset():
    return build_dataset(source_fixture(), generated_at=datetime(2026, 10, 16, tzinfo=timezone.utc))


def test_twenty_students_with_preserved_real_records_and_labelled_synthetic_papers():
    source = source_fixture()
    before = deepcopy(source)
    docs = build_dataset(source, generated_at=datetime(2026, 10, 16, tzinfo=timezone.utc))
    assert source == before
    assert len(docs["submissions"]) == len(docs["diagram_evaluations"]) == 20
    assert len(docs["rubricCollection"][0]["exam_roster"]["students"]) == 20
    for original in source["submissions"] + source["diagram_evaluations"]:
        collection = "submissions" if original in source["submissions"] else "diagram_evaluations"
        copied = next(d for d in docs[collection] if d["_id"] == original["_id"])
        assert {k: v for k, v in copied.items() if k != "dataset_provenance"} == original
    synthetic = [s for s in docs["submissions"] if s["dataset_provenance"]["kind"] == "synthetic"]
    assert len(synthetic) == 15
    assert len({s["cleaned_ocr_transcript"] for s in synthetic}) == 15
    assert all(s["evaluation"]["grading_source"] == "synthetic-fixture-not-model-graded" for s in synthetic)
    assert all(len(s["evaluation"]["results"]) == 5 for s in synthetic)
    summary = validate_dataset(docs)
    assert summary["complete_students"] == 17
    assert summary["pending_students"] == 3
    assert summary["maximum_marks"] == 55


def test_synthetic_diagrams_have_linked_svg_and_consistent_rubric_grades():
    docs = dataset()
    rows = [d for d in docs["diagram_evaluations"] if d["dataset_provenance"]["kind"] == "synthetic"]
    assert len({r["agent_marks"] for r in rows}) >= 5
    for row in rows:
        assert row["submitted_artifact"]["content_type"] == "image/svg+xml"
        assert "<svg" in row["submitted_artifact"]["content"]
        ElementTree.fromstring(row["submitted_artifact"]["content"])
        details = row["diagram_details"]
        connections = {(c["from"], c["to"]) for c in details["connections"]}
        for entity in details["entities"]:
            owner = "1" if entity["entity_name"] == "Student" else "2"
            for attribute in entity["attributes"]:
                detection = next(d for d in details["detections"] if d["text"] == attribute)
                assert (owner, detection["id"]) in connections
        assert row["guideline_object_id"] == str(docs["diagram_marking"][0]["_id"])
        grade = row["evaluation_result"]["agent_grading"]
        assert sum(c["marks"] for c in grade["criterion_results"]) == grade["agent_marks"]


def test_missing_real_essay_answers_remain_missing():
    docs = dataset()
    for sub in docs["submissions"][:5][2:]:
        assert sub["evaluation"] is None
        assert sub["status"] in ("processing", "not_started")
        assert not sub.get("cleaned_ocr_transcript")


def test_validation_rejects_mixed_student_and_exam_references():
    docs = dataset()
    docs["diagram_evaluations"][-1]["examKey"] = "OTHER-EXAM"
    with pytest.raises(ValueError):
        validate_dataset(docs)


def test_existing_target_data_is_never_overwritten():
    class Existing:
        name = "gradev6"
        async def list_collection_names(self): return ["submissions"]
        def __getitem__(self, name): return self
        async def count_documents(self, query): return 1
    with pytest.raises(ValueError, match="not empty"):
        immediate(require_empty_target(Existing()))


def test_source_loader_restores_raw_answers_and_roster_fields_before_copy(monkeypatch):
    source = source_fixture()
    source["submissions"][0]["raw_ocr_transcript"] = "Original raw OCR must survive"
    source["rubrics"][0]["exam_roster"]["students"][0].update(name="Original name", date="2025-04-01")
    projected = deepcopy(source)
    projected["submissions"][0].pop("raw_ocr_transcript")
    for row in projected["rubrics"][0]["exam_roster"]["students"]:
        row.pop("name", None); row.pop("date", None)
    monkeypatch.setattr("scripts.seed_gradev6.load_exam_paper_sources", AsyncMock(return_value=projected))
    full = immediate(load_full_sources(ReadOnlyDatabase(source)))
    assert full["submissions"][0]["raw_ocr_transcript"] == "Original raw OCR must survive"
    assert full["rubrics"][0]["exam_roster"]["students"][0]["name"] == "Original name"
    docs = build_dataset(full, generated_at=datetime(2026, 10, 16, tzinfo=timezone.utc))
    assert docs["submissions"][0]["raw_ocr_transcript"] == "Original raw OCR must survive"
    assert docs["rubricCollection"][0]["exam_roster"]["students"][0]["date"] == "2025-04-01"

"""Export the existing synthetic IT2040 fixtures as four essays + one diagram.

Run from AdaptiveExamAnalyticsEngine: python scripts/build_viva_dataset.py
Writes local JSON only; never connects to MongoDB.
"""
from collections import Counter
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bson import json_util
from app.ingestion.student_data import normalize_student_submission
from app.ingestion.diagram_data import normalize_diagram_evaluation

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "app/sample_data/sample_data_v4"
EXAM_KEY = "EXAM-IT2040-2022-S1-Jun-FINAL"
OUTPUT = ROOT / "app/sample_data" / f"{EXAM_KEY}-synthetic-50"
PROVENANCE = {
    "kind": "synthetic", "dataset_id": f"{EXAM_KEY}-synthetic-50-v1",
    "source": "Adapted from repository sample_data_v4",
    "limitations": "Simulated answers, marks and diagram detections; not real students, model predictions or independently verified grades.",
}


def identifier(collection, student="shared"):
    return sha256(f"{EXAM_KEY}:{collection}:{student}:synthetic-v1".encode()).hexdigest()[:24]


def build_dataset():
    docs = {name: json.loads((SOURCE / name / f"{name}.json").read_text(encoding="utf-8"))
            for name in ("courses", "rubricCollection", "submissions", "diagram_evaluation", "diagram_marking")}
    docs["courses"] = [c for c in docs["courses"] if c["code"] == "IT2040"]
    rubric = docs["rubricCollection"][0]
    diagram_question = deepcopy(rubric["questions"][4])
    rubric["questions"] = rubric["questions"][:4]
    rubric.pop("guideLines", None)
    rubric["max_marks"] = 80
    rubric["filename"] = "SYNTHETIC adapted IT2040 2022 exam - not an original paper.pdf"
    roster = [{"student_id": s["student_id"], "name": f"Synthetic Student {i:02d}"}
              for i, s in enumerate(docs["submissions"], 1)]
    rubric["exam_roster"] = {"students": roster, "row_count": 50, "duplicate_roster_ids": []}
    identity = {k: rubric[k] for k in ("subject_code", "subject_name", "year", "month", "semester", "session_name")}
    guide_id = identifier("diagram_marking")
    guide = {**identity, "_id": {"$oid": guide_id}, "examKey": EXAM_KEY,
             "question_no": "05", "question_text": diagram_question["question_text"],
             "bloom_level": "Create", "totalMarks": 20}
    guide["guideLines"] = [{"id": i, "criterion": c["point"], "marks": c["marks"]}
                          for i, c in enumerate(diagram_question["criteria"], 1)]
    details_by_student = {d["student_id"]: d for d in docs["diagram_marking"]}
    rubric_id = identifier("rubricCollection")
    for sub in docs["submissions"]:
        sub["rubric_ref"] = rubric_id
        sub["paper_key"] = EXAM_KEY
        sub["max_marks_per_question"] = sub["max_marks_per_question"][:4]
        sub["max_marks_paper_total"] = 80
        evaluation = sub["evaluation"]
        evaluation["results"] = evaluation["results"][:4]
        evaluation.update(total_score=sum(r["score"] for r in evaluation["results"]),
                          max_score=80, grading_source="synthetic-fixture-not-model-graded")
        transcript = re.split(r"(?m)^(?:Question 5|Q5)\s*$", sub["raw_ocr_transcript"])[0].strip()
        sub["raw_ocr_transcript"] = sub["cleaned_ocr_transcript"] = "SYNTHETIC DEMO ANSWERS\n" + transcript
        for row in evaluation["results"]:
            row["q_no"] = row["question_no"]
            for criterion in row["criteria_breakdown"]:
                criterion["reason"] = "Simulated rubric award for demonstration; not independently graded."
    for diagram in docs["diagram_evaluation"]:
        diagram["rubric_ref"] = rubric_id
        diagram["guideline_object_id"] = guide_id
        original = details_by_student[diagram["student_id"]]
        for key in ("diagram_details", "diagram_entity_relations", "diagram_relations"):
            diagram[key] = deepcopy(original[key])
        result = diagram["evaluation_result"]
        result["grading_source"] = "synthetic-fixture-not-model-graded"
        result["overall_feedback"] = "Synthetic demonstration: " + result["overall_feedback"]
    docs["diagram_marking"] = [guide]
    for collection, records in docs.items():
        for record in records:
            record["_id"] = {"$oid": identifier(collection, record.get("student_id", "shared"))}
            record["dataset_provenance"] = deepcopy(PROVENANCE)
            record["examKey"] = EXAM_KEY
            for key in ("examCode", "exam_code"):
                if key in record:
                    record[key] = EXAM_KEY
    # Correct the source fixture's B closure: the question explicitly gives B -> E.
    docs = json.loads(json.dumps(docs).replace("B+ = {B}", "B+ = {B, E}"))
    return docs


def validate_dataset(docs):
    """Check the exported BSON forms through the actual analytics normalizers."""
    data = json_util.loads(json.dumps(docs))
    assert {k: len(v) for k, v in data.items()} == {
        "courses": 1, "rubricCollection": 1, "submissions": 50,
        "diagram_evaluation": 50, "diagram_marking": 1}
    rubric, guide = data["rubricCollection"][0], data["diagram_marking"][0]
    assert len(rubric["questions"]) == 4 and guide["question_no"] == "05"
    essays = {s["student_id"]: s for s in data["submissions"]}
    diagrams = {d["student_id"]: d for d in data["diagram_evaluation"]}
    assert len(essays) == len(diagrams) == 50 and essays.keys() == diagrams.keys()
    assert {s["student_id"] for s in rubric["exam_roster"]["students"]} == essays.keys()
    assert sum(c["marks"] for c in guide["guideLines"]) == guide["totalMarks"] == 20
    ids = [str(r["_id"]) for records in data.values() for r in records]
    assert len(ids) == len(set(ids))
    summary = []
    for sid, sub in essays.items():
        assert sub["rubric_ref"] == str(rubric["_id"])
        normalized = normalize_student_submission(data["courses"][0], rubric, sub)
        assert len(normalized.questions) == 4
        diagram = normalize_diagram_evaluation(diagrams[sid], guide)
        assert diagram["guideline_object_id"] == str(guide["_id"])
        result = diagram["evaluation_result"]
        assert len(result["criteria_results"]) == len(guide["guideLines"])
        for row, criterion in zip(result["criteria_results"], guide["guideLines"]):
            assert row["criterion_id"] == criterion["id"]
            assert row["criterion"] == criterion["criterion"]
            assert 0 <= row["awarded_marks"] <= row["max_marks"] == criterion["marks"]
        assert sum(c["awarded_marks"] for c in result["criteria_results"]) == result["total_score"]
        assert result["max_score"] == 20
        total = sub["evaluation"]["total_score"] + result["total_score"]
        assert 0 <= total <= 100
        summary.append({"student_id": sid, "essay_marks": sub["evaluation"]["total_score"],
                        "diagram_marks": result["total_score"], "total_out_of_100": total,
                        "question_marks": {q.question_no: q.score for q in normalized.questions}})
    assert len({s["raw_ocr_transcript"] for s in essays.values()}) == 50
    for records in data.values():
        assert all(r["examKey"] == EXAM_KEY and r["dataset_provenance"]["kind"] == "synthetic" for r in records)
    return sorted(summary, key=lambda r: r["total_out_of_100"], reverse=True)


if __name__ == "__main__":
    dataset = build_dataset()
    summary = validate_dataset(dataset)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name, rows in dataset.items():
        (OUTPUT / f"{name}.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (OUTPUT / "student_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    distribution = Counter("80-100" if r["total_out_of_100"] >= 80 else "60-79" if r["total_out_of_100"] >= 60
                           else "40-59" if r["total_out_of_100"] >= 40 else "0-39" for r in summary)
    print(json.dumps({"output": str(OUTPUT), "collections": {k: len(v) for k, v in dataset.items()},
                      "score_range": [summary[-1]["total_out_of_100"], summary[0]["total_out_of_100"]],
                      "mean": round(sum(r["total_out_of_100"] for r in summary) / 50, 2),
                      "score_distribution": distribution}, indent=2))

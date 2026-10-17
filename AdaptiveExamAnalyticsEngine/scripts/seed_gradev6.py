"""Build a labelled 20-student demo from gradev5. Dry-run unless --apply is given."""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bson import ObjectId, json_util
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings
from app.db.repository import load_exam_paper_sources
from app.ingestion.diagram_data import normalize_diagram_evaluation
from app.ingestion.student_data import normalize_student_submission
from app.services.exam_paper import reconstruct_exam_paper

SOURCE_DB, TARGET_DB = "gradev5", "gradev6"
EXAM_KEY = "EXAM-2025-S1-Apr"
DATASET_ID = "gradev6-20-students-v1"
SYNTHETIC_SOURCE = "synthetic-fixture-not-model-graded"

# Each entry contains full-credit, partial-credit and incorrect demo answer text.
# These are authored examples, not a new grading of any source student's answer.
ANSWERS = [
    [
        ("First collect requirements, then make the conceptual ER design, map it to a logical schema, refine the schema using normalization, choose physical storage/indexes, and design security permissions.", "Collect requirements, draw an ER model and convert it into tables. I have not explained refinement, storage or security.", "Database design starts by inserting data and adding indexes; requirements and conceptual design are unnecessary."),
        ("A weak entity needs an owner for identification. Its partial key combines with the owner's key; the identifying relationship is 1:N and the weak entity participates totally.", "A weak entity depends on an owner, but I have not explained its identifying key or participation.", "A weak entity has its own independent key and does not require an owner."),
        ("A ternary relationship connects three entity sets together. For example a quantity for Supplier, Part and Project depends on that three-way combination, so three independent binary relationships can lose its meaning.", "A ternary relationship involves three entity sets; I have not explained the shared attribute or why binary relationships are insufficient.", "A ternary relationship is three separate binary links and never has attributes of its own."),
    ],
    [
        ("By reflexivity A determines A. Starting with A -> B, use transitivity with B -> C and B -> D to obtain A -> C and A -> D.", "A determines B and B determines C. I have not derived the dependency on D.", "Reverse B -> C to get C -> B; dependencies always work in both directions."),
        ("Taking the union of these dependencies gives A+ = {A, B, C, D}.", "My closure is {A, B, C}; the step adding D is missing.", "A+ = {A} because a closure never contains dependent attributes."),
        ("A+ contains every attribute in R(A,B,C,D), so A is a key. Its only proper subset is empty, which cannot determine R.", "A seems to be a key because it determines B, but I have not checked all attributes.", "A is not a key even though its closure contains all attributes."),
    ],
    [
        ("Schema refinement uses functional dependencies and normal-form tests to reduce redundant facts and insertion, deletion and update anomalies.", "Normalization reduces repeated data; I have not explained the normal-form tests.", "Schema refinement duplicates department facts in every employee row to avoid joins."),
        ("In an employee-department table, a department without employees cannot be inserted if EID must be non-null; each new employee can also repeat the department details.", "Adding an employee can repeat department data. I have not explained storing a department with no employees.", "An insertion anomaly means that a SELECT statement cannot read a row."),
        ("Deleting a department's last employee can also remove the only stored facts about that department.", "Deleting an employee can lose other information; I have not identified the department case.", "Deletion anomalies are only caused by removing a table index."),
        ("Changing a department location requires changing every employee row that repeats it; missing a row leaves inconsistent locations.", "Department changes can require several updates, but I have not identified the repeated location.", "Updating one employee row automatically changes all duplicated department facts."),
    ],
    [
        ("A view is a virtual table defined by a SELECT over base tables, for example CREATE VIEW PublicStaff AS SELECT EID, Name FROM Employee.", "A view is a saved query that can be queried like a table; I have not given CREATE VIEW syntax.", "Every view is an independent physical copy of all base-table data."),
        ("Views improve security by exposing only permitted rows or columns and simplify repeated joins by providing one queryable interface.", "Views can hide sensitive columns; I have not explained query simplification.", "Views automatically grant every user access to every underlying column."),
        ("Aggregate views are generally not updatable. Join views can have ambiguous target rows, so DBMSs restrict updates and simple single-table views are the safest update case.", "Some complex views cannot be updated, but I have not explained aggregates or ambiguous joins.", "All views, including aggregate and multi-table join views, can always be updated without restrictions."),
    ],
    [
        ("At server scope create a Windows or SQL-authenticated login, assign suitable server roles, and GRANT or DENY the required server permissions using least privilege.", "Create a server login and assign a role; server-level GRANT and DENY are not explained.", "Creating a database table automatically creates a server login with administrator access."),
        ("Inside the database create a user mapped to that login, assign fixed or custom database roles, and GRANT or DENY permissions on database/schema objects such as SELECT on a table.", "Map the login to a database user; I have not assigned database roles or object permissions.", "A server login never needs a database user; database and schema permissions are irrelevant."),
    ],
]


def object_id(collection, student):
    return ObjectId(sha256(f"{DATASET_ID}:{collection}:{student}".encode()).hexdigest()[:24])


def synthetic_essay(student, rubric, identity, timestamp, ability, rng):
    results, transcript = [], []
    for question, fragments in zip(rubric["questions"], ANSWERS):
        rows, paragraphs = [], []
        for criterion, variants in zip(question["criteria"], fragments):
            draw = rng.random()
            fraction = 1 if draw < ability else 0.5 if draw < min(1, ability + 0.25) else 0
            paragraphs.append(variants[0 if fraction == 1 else 1 if fraction else 2])
            rows.append({"point": criterion["point"], "awarded_marks": criterion["marks"] * fraction,
                "reason": f"Synthetic fixture: {'full' if fraction == 1 else 'partial' if fraction else 'no'} criterion credit; not independently graded."})
        answer = " ".join(paragraphs)
        no = question["question_no"]
        transcript.append(f"Question {no}\n{answer}")
        results.append({"q_no": no, "score": sum(r["awarded_marks"] for r in rows), "criteria_breakdown": rows,
            "answer_excerpt": answer, "slice_source": "split", "grading_source": SYNTHETIC_SOURCE,
            "feedback": "Synthetic demonstration result, not an independently verified student grade.", "error": None})
    full_text = f"SYNTHETIC DEMO PAPER {student}\n\n" + "\n\n".join(transcript)
    return {"_id": object_id("submissions", student), **identity, "student_id": student,
        "rubric_ref": rubric["_id"], "paper_key": EXAM_KEY, "status": "graded", "error": None,
        "raw_ocr_transcript": full_text, "cleaned_ocr_transcript": full_text,
        "max_marks_paper_total": 35, "max_marks_per_question": [{"question_no": q["question_no"], "max_marks": q["max_marks"]} for q in rubric["questions"]],
        "evaluation": {"results": results, "total_score": sum(r["score"] for r in results), "max_score": 35,
            "grading_source": SYNTHETIC_SOURCE, "rag_context_used": False,
            "feedback": "Authored synthetic answer and simulated marking fixture; not a real student."},
        "created_at": timestamp, "updated_at": timestamp, "processed_at": timestamp}


def synthetic_diagram(student, guideline, identity, timestamp, ability, rng):
    # Chen-notation artifacts and their extracted structures are generated together.
    states = {i: (2 if rng.random() < ability else 1 if rng.random() < 0.6 else 0) for i in range(1, 9)}
    states[1] = 2
    states[2] = 2 if ability >= 0.45 else 0
    for cid in (6, 7, 8):
        if not states[2]: states[cid] = 0
    positions = {1: (180, 190), 2: (520, 190), 3: (65, 65), 4: (180, 50), 5: (295, 65),
                 6: (465, 65), 7: (600, 65), 8: (350, 190)}
    labels = {1: "Student", 2: "Course", 3: "S_ID", 4: "Name", 5: "Email", 6: "C_ID", 7: "Title", 8: "Joins"}
    for cid, alternate in ((4, "StudentName"), (5, "Contact"), (7, "CourseName"), (8, "Enrolls")):
        if states[cid] == 1: labels[cid] = alternate
    nodes, edges, entities, detections = [], [], {}, []
    for cid in range(1, 9):
        if not states[cid]: continue
        x, y = positions[cid]
        kind = "entity" if cid in (1, 2) else "relationship" if cid == 8 else "attribute"
        if kind == "entity":
            nodes.append(f'<rect x="{x-50}" y="{y-22}" width="100" height="44" fill="white" stroke="black"/>')
            entities[labels[cid]] = {"attributes": [], "primary_keys": []}
        elif kind == "relationship":
            nodes.append(f'<polygon points="{x-48},{y} {x},{y-28} {x+48},{y} {x},{y+28}" fill="white" stroke="black"/>')
        else:
            nodes.append(f'<ellipse cx="{x}" cy="{y}" rx="55" ry="23" fill="white" stroke="black"/>')
        underline = ' text-decoration="underline"' if cid in (3, 6) and states[cid] == 2 else ""
        nodes.append(f'<text x="{x}" y="{y+5}" text-anchor="middle"{underline}>{escape(labels[cid])}</text>')
        detections.append({"id": str(cid), "label": kind, "bbox": [x-55, y-25, x+55, y+25],
            "text": labels[cid], "source": "synthetic-generated-geometry"})
    expected_edges = [(1, 3), (1, 4), (1, 5), (2, 6), (2, 7), (1, 8), (8, 2)]
    actual_edges = [(a, b) for a, b in expected_edges if states[a] and states[b]]
    if ability < 0.6 and actual_edges: actual_edges = actual_edges[:-1]
    for a, b in actual_edges:
        x1, y1 = positions[a]; x2, y2 = positions[b]
        edges.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="black"/>')
    for cid in (3, 4, 5, 6, 7):
        owner = "Student" if cid <= 5 else "Course"
        owner_id = 1 if cid <= 5 else 2
        if states[cid] and owner in entities and (owner_id, cid) in actual_edges:
            entities[owner]["attributes"].append(labels[cid])
            if cid in (3, 6) and states[cid] == 2: entities[owner]["primary_keys"].append(labels[cid])
    participants = (["Student"] if (1, 8) in actual_edges else []) + (["Course"] if (8, 2) in actual_edges else [])
    relationships = [{"name": labels[8], "entities": participants}] if states[8] else []
    correct_edges = sum(labels[a] in ("Student", "Course", "Joins") and labels[b] in ("S_ID", "Name", "Email", "C_ID", "Title", "Joins", "Course") for a, b in actual_edges)
    awards = {i: (2 if i in (1, 2) and states[i] else states[i]) for i in range(1, 9)}
    for cid in (3, 4, 5, 6, 7):
        if states[cid] and (1 if cid <= 5 else 2, cid) not in actual_edges:
            awards[cid] = min(1, awards[cid])
    if states[8] and len(participants) != 2: awards[8] = min(1, awards[8])
    awards[9] = 2 if correct_edges == 7 else 1 if correct_edges >= 4 else 0
    awards[10] = 0.5 if any(states[i] == 1 for i in (3, 6)) else 1
    awards[11] = 1 if all(awards[i] == 2 for i in range(1, 10)) else 0.5 if sum(awards.values()) >= 13 else 0
    criteria = [{"id": c["id"], "marks": awards[c["id"]],
        "reason": f"Synthetic fixture: {awards[c['id']]}/{c['marks']} based on generated nodes, labels and connections; not model graded."} for c in guideline["guideLines"]]
    total = sum(awards.values())
    structure = {"entities": entities, "relationships": relationships}
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="700" height="300" viewBox="0 0 700 300"><title>Synthetic ER answer</title><rect width="700" height="300" fill="white"/>' + "".join(edges + nodes) + '</svg>'
    details = {"label_count": len(detections), "entity_count": len(entities), "relationship_count": len(relationships),
        "connections": [{"from": str(a), "to": str(b)} for a, b in actual_edges],
        "detections": detections, "entities": [{"entity_name": k, **v} for k, v in entities.items()],
        "relationships": [{"relation_name": r["name"], "entities": r["entities"], "attributes": []} for r in relationships],
        "structure": structure, "ocr_error": None}
    return {"_id": object_id("diagram_evaluations", student), **identity, "student_id": student,
        "guideline_object_id": str(guideline["_id"]), "diagram_details": details, "agent_marks": total,
        "diagram_marks": total, "source": SYNTHETIC_SOURCE,
        "submitted_artifact": {"content_type": "image/svg+xml", "content": svg, "synthetic": True},
        "evaluation_result": {"status": "ok", "guideline_object_id": str(guideline["_id"]), "structure": structure,
            "agent_marks": total, "agent_grading": {"agent_marks": total, "max_marks": 20, "criterion_results": criteria,
                "feedback": "Synthetic generated ER diagram with simulated criterion marks; not an independently evaluated image."}},
        "created_at": timestamp.isoformat(), "updated_at": timestamp.isoformat()}


def build_dataset(sources, *, generated_at):
    if len(sources["examkeys"]) != 1 or len(sources["rubrics"]) != 1 or len(sources["diagram_marking"]) != 1:
        raise ValueError("Expected one canonical source exam and one rubric for each component")
    if len(sources["submissions"]) != 5 or len(sources["diagram_evaluations"]) != 5:
        raise ValueError("Expected exactly five source students with one record per component")
    docs = {"examkeys": deepcopy(sources["examkeys"]), "rubricCollection": deepcopy(sources["rubrics"]),
        "diagram_marking": deepcopy(sources["diagram_marking"]), "submissions": deepcopy(sources["submissions"]),
        "diagram_evaluations": deepcopy(sources["diagram_evaluations"])}
    rubric, guide = docs["rubricCollection"][0], docs["diagram_marking"][0]
    if [q.get("question_no") for q in rubric.get("questions", [])] != ["01", "02", "03", "04", "05"] or [len(q.get("criteria", [])) for q in rubric["questions"]] != [3, 3, 4, 3, 2]:
        raise ValueError("Source essay rubric does not match the authored fixture bank")
    if sorted(c.get("id") for c in guide.get("guideLines", [])) != list(range(1, 12)):
        raise ValueError("Source diagram rubric does not match the fixture generator")
    snapshot = {k: sources[k] for k in ("examkeys", "rubrics", "diagram_marking", "submissions", "diagram_evaluations")}
    fingerprint = sha256(json_util.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    for name, records in docs.items():
        for record in records:
            record["dataset_provenance"] = {"dataset_id": DATASET_ID, "kind": "original_real_copy" if name in ("submissions", "diagram_evaluations") else "copied_definition",
                "source_database": SOURCE_DB, "source_collection": record.pop("_source_collection", name),
                "source_record_id": str(record["_id"]), "source_snapshot_sha256": fingerprint}
    identity = {k: rubric[k] for k in ("examKey", "subject_code", "subject_name", "session_name", "year", "month", "semester")}
    rng = random.Random(20261016)
    roster = rubric["exam_roster"]["students"]
    for index in range(1, 16):
        student = f"SYNTH-V6-{index:03}"
        ability = 0.15 + (index - 1) * 0.8 / 14
        for name, record in (("submissions", synthetic_essay(student, rubric, identity, generated_at, ability, rng)),
                ("diagram_evaluations", synthetic_diagram(student, guide, identity, generated_at, ability, rng))):
            record["dataset_provenance"] = {"dataset_id": DATASET_ID, "kind": "synthetic", "source_database": SOURCE_DB,
                "source_exam_key": EXAM_KEY, "source_snapshot_sha256": fingerprint,
                "note": "Authored demo answer and simulated marks. Not a real student or independent grading result."}
            docs[name].append(record)
        roster.append({"student_id": student, "name": f"Synthetic Student {index:02}", "date": generated_at.date().isoformat(), "synthetic": True})
    rubric["exam_roster"]["row_count"] = len(roster)
    docs["examkeys"][0]["dataset_metadata"] = {"dataset_id": DATASET_ID, "real_students": 5, "synthetic_students": 15,
        "note": "Mixed demonstration dataset; retain original pending essays. Not 20 independent real observations.",
        "diagram_question_prompt": "Original prompt unavailable; generated diagrams follow the saved marking rubric."}
    validate_dataset(docs)
    return docs


def validate_dataset(docs):
    exam, rubric, guide = docs["examkeys"][0], docs["rubricCollection"][0], docs["diagram_marking"][0]
    if exam["examKey"] != EXAM_KEY or exam["examStructure"] != ["Essay"] * 5 + ["Diagram"]:
        raise ValueError("Unexpected exam identity or structure")
    ids = [s["student_id"] for s in docs["submissions"]]
    if len(ids) != 20 or len(set(ids)) != 20 or Counter(ids) != Counter(d["student_id"] for d in docs["diagram_evaluations"]) or Counter(ids) != Counter(s["student_id"] for s in rubric["exam_roster"]["students"]):
        raise ValueError("Student identifiers are missing, duplicated or mixed")
    for sub in docs["submissions"]:
        if sub.get("examKey") != EXAM_KEY or str(sub.get("rubric_ref")) != str(rubric["_id"]):
            raise ValueError("Invalid essay exam/rubric reference")
        if sub.get("status") == "graded": normalize_student_submission({}, rubric, sub)
    for diagram in docs["diagram_evaluations"]:
        if diagram.get("examKey") != EXAM_KEY: raise ValueError("Invalid diagram exam reference")
        normalize_diagram_evaluation(diagram, guide)
    paper = reconstruct_exam_paper(EXAM_KEY, {"examkeys": docs["examkeys"],
        "rubrics": [{**rubric, "_source_collection": "rubricCollection"}], "submissions": docs["submissions"],
        "diagram_marking": docs["diagram_marking"], "diagram_evaluations": docs["diagram_evaluations"]})
    statuses = Counter(s["grading"]["status"] for s in paper["students"])
    if paper["grading"]["maximumMarks"] != 55 or statuses != {"complete": 17, "pending": 3}:
        raise ValueError("Unexpected rubric maxima, incomplete fixtures or ambiguous reconstructed grades")
    return {"students": len(ids), "real_students": 5, "synthetic_students": 15, "complete_students": statuses["complete"],
        "pending_students": statuses["pending"], "maximum_marks": 55,
        "question_paper_status": paper["validation"]["questionPaperStatus"],
        "essay_score_range": [min(s["evaluation"]["total_score"] for s in docs["submissions"] if s.get("status") == "graded"), max(s["evaluation"]["total_score"] for s in docs["submissions"] if s.get("status") == "graded")]}


async def require_empty_target(db):
    if db.name != TARGET_DB: raise ValueError("Only gradev6 is an allowed target")
    for name in await db.list_collection_names():
        if await db[name].count_documents({}): raise ValueError("gradev6 is not empty; refusing to overwrite records")


async def load_full_sources(db):
    # The reconstruction reader projects private fields out; a faithful copy needs exact full records.
    matched = await load_exam_paper_sources(db, EXAM_KEY)
    for name in ("examkeys", "rubrics", "submissions", "diagram_marking", "diagram_evaluations"):
        full_records = []
        for reference in matched[name]:
            collection = reference["_source_collection"] if name == "rubrics" else name
            record = await db[collection].find_one({"_id": reference["_id"]})
            if record is None: raise ValueError("A matched source record disappeared during preparation")
            if name == "rubrics": record["_source_collection"] = collection
            full_records.append(record)
        matched[name] = full_records
    return matched


async def main(apply=False):
    client = AsyncIOMotorClient(settings.effective_mongodb_uri, serverSelectionTimeoutMS=5000, tz_aware=True)
    try:
        source, target = client[SOURCE_DB], client[TARGET_DB]
        await require_empty_target(target)
        sources = await load_full_sources(source)
        timestamp = datetime.now(timezone.utc)
        timestamp = timestamp.replace(microsecond=timestamp.microsecond // 1000 * 1000)
        docs = build_dataset(sources, generated_at=timestamp)
        for name in ("courses", "course_taxonomies"):
            records = await source[name].find({"$or": [{"course_code": "IT2040"}, {"code": "IT2040"}, {"subject_code": "IT2040"}]}).to_list(length=None)
            if records: docs[name] = records
        report = {"source_database": SOURCE_DB, "target_database": TARGET_DB, "mode": "apply" if apply else "dry_run",
            "collections": {k: len(v) for k, v in docs.items()}, "validation": validate_dataset(docs)}
        print(json.dumps(report))
        if not apply: return
        await require_empty_target(target)
        for name in ("submissions", "diagram_evaluations"):
            await target[name].create_index([("examKey", 1), ("student_id", 1)], unique=True, name="uniq_exam_student")
        await target["examkeys"].create_index("examKey", unique=True, name="uniq_exam_key")
        for name, records in docs.items():
            if records: await target[name].insert_many(records)
        stored = {name: await target[name].find({}).to_list(length=None) for name in docs}
        if any({d["_id"]: d for d in stored[name]} != {d["_id"]: d for d in records} for name, records in docs.items()):
            raise ValueError("Read-back differs from prepared records; do not overwrite or rerun")
        print(json.dumps({"written": True, "readback_validation": validate_dataset(stored)}))
    finally:
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write only to an empty gradev6 database")
    args = parser.parse_args()
    try:
        asyncio.run(main(args.apply))
    except Exception as exc:
        # Avoid printing connection strings or source answers in connection/validation failures.
        print(f"Dataset seed failed ({type(exc).__name__}); no source records were modified.", file=sys.stderr)
        raise SystemExit(1)

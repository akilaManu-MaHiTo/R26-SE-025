"""Read-only question/rubric preview. Never returns student submissions."""

from collections import Counter
from calendar import month_name
from math import isfinite

from app.db.repository import _find_diagram_guideline
from app.services.exam_paper import _identity, _maximum, _qno, _ref


def _json_safe(value):
    if isinstance(value, float) and not isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


async def load_exam_paper_definition(db, exam):
    key = exam.get("examKey")
    canonical = await db["examkeys"].find({"examKey": key}).to_list(length=2)
    if len(canonical) != 1 or canonical[0].get("_id") != exam.get("_id"):
        raise ValueError("Missing or ambiguous canonical exam")
    identity = _identity(exam, canonical=True)
    if None in identity or not isinstance(exam.get("examStructure"), list):
        raise ValueError("Incomplete canonical exam metadata")
    subject, year, month, semester, session = identity
    metadata = {"subject_code": subject, "year": {"$in": [year, str(year)]},
                "month": {"$in": [month, str(month), month_name[month]]},
                "semester": {"$in": [semester, str(semester)]},
                "session_name": {"$in": ["Final", "Final Examination"] if session == "Final" else [session]}}
    peers = await db["examkeys"].find({"subjectCode": subject,
        "examYear": metadata["year"], "examMonth": metadata["month"],
        "examSemester": metadata["semester"], "session": metadata["session_name"]}).to_list(length=2)
    if len(peers) != 1 or peers[0].get("_id") != exam.get("_id"):
        raise ValueError("The canonical exam identity is ambiguous")
    query = {"$or": [{"examKey": key}, metadata]}
    result = {"exam_key": key, "subject_code": subject, "subject_name": exam.get("subjectName", subject),
              "year": year, "month": month, "semester": semester, "session_name": session,
              "expected_structure": exam["examStructure"], "essay_questions": [], "diagram_rubrics": [],
              "maximum_marks": None, "validation": {"status": "available", "messages": []}}
    messages = result["validation"]["messages"]
    problems = {"issues": []}

    def matches(document):
        actual = _identity(document)
        fields = ("subject_code", "year", "month", "semester", "session_name")
        if (document.get("examKey") not in (None, "", key)
                or any(f in document and document[f] is not None and actual[i] != identity[i] for i, f in enumerate(fields))):
            messages.append("Conflicting exam metadata was excluded from this preview.")
            return False
        return document.get("examKey") == key or actual == identity

    projection = {"_id": 1, "examKey": 1, **{k: 1 for k in metadata}, "questions": 1}
    collections = await db.list_collection_names()
    for collection in ("rubricCollection", "rubicCollection"):
        if collection not in collections:
            continue
        rubrics = await db[collection].find(query, projection).to_list(length=None)
        for rubric in rubrics:
            if not matches(rubric):
                continue
            questions = rubric.get("questions")
            if not isinstance(questions, list):
                messages.append("An essay rubric has no readable question definitions.")
                continue
            for i, question in enumerate(questions):
                if not isinstance(question, dict):
                    messages.append("An essay question definition is unreadable.")
                    continue
                criteria = question.get("criteria")
                maximum = _maximum(criteria, "marks", question.get("max_marks"), problems, _ref(collection, rubric, f"questions.{i}"), "paper")
                result["essay_questions"].append({"question_no": _qno(question.get("question_no")),
                    "question_text": question.get("question_text"), "max_marks": maximum,
                    "criteria": [{"point": c.get("point"), "marks": c.get("marks")} for c in criteria if isinstance(c, dict)] if isinstance(criteria, list) else []})

    # Only reference/identity fields are read: no answers, grades, names or student IDs.
    refs = await db["diagram_evaluations"].find(query, {
        "_id": 0, "examKey": 1, **{k: 1 for k in metadata}, "guideline_object_id": 1,
    }).to_list(length=None)
    seen = set()
    for record in refs:
        if not matches(record):
            continue
        gid = record.get("guideline_object_id")
        if str(gid) in seen:
            continue
        seen.add(str(gid))
        guideline = await _find_diagram_guideline(db, gid)
        if guideline is None:
            messages.append("A referenced diagram marking rubric is missing.")
            continue
        criteria = guideline.get("guideLines")
        maximum = _maximum(criteria, "marks", guideline.get("totalMarks"), problems, _ref("diagram_marking", guideline), "paper")
        result["diagram_rubrics"].append({"rubric_id": str(guideline["_id"]), "exam_code": guideline.get("examCode"),
            "total_marks": maximum, "criteria": [{k: c.get(k) for k in ("id", "criterion", "description", "marks", "expected")}
                for c in criteria if isinstance(c, dict)] if isinstance(criteria, list) else []})

    questions, diagrams = result["essay_questions"], result["diagram_rubrics"]
    structure = exam["examStructure"]
    expected_essays = {str(i).zfill(2) for i, kind in enumerate(structure, 1) if kind == "Essay"}
    numbers = Counter(q["question_no"] for q in questions)
    definitions_match = set(numbers) == expected_essays and all(n == 1 for n in numbers.values())
    if not definitions_match:
        messages.append("Essay questions are missing, duplicated or inconsistent with the exam structure.")
    if len(diagrams) != structure.count("Diagram") or len(diagrams) > 1:
        messages.append("The diagram marking rubrics cannot be uniquely matched to the expected diagram section.")
    if problems["issues"]:
        messages.append("Some rubric maximum marks are missing or inconsistent.")
    maxima = [q["max_marks"] for q in questions] + [d["total_marks"] for d in diagrams]
    if definitions_match and len(diagrams) == structure.count("Diagram") and len(diagrams) <= 1 and maxima and all(m is not None for m in maxima) and not messages:
        result["maximum_marks"] = sum(maxima)
    if any(not isinstance(q["question_text"], str) or not q["question_text"].strip() for q in questions):
        messages.append("Some original essay question wording is missing.")
    if "Diagram" in structure:
        messages.append("The original diagram question wording and its recorded question number are not saved. The marking rubric is shown separately.")
    if any(kind not in ("Essay", "Diagram") for kind in structure):
        messages.append("This exam contains a question type not supported by this preview.")
        result["maximum_marks"] = None
    result["essay_questions"].sort(key=lambda q: q["question_no"] or "")
    result["validation"] = {"status": "incomplete" if messages else "available", "messages": list(dict.fromkeys(messages))}
    return _json_safe(result)

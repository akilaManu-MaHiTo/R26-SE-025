"""Read-only reconstruction from verified source links, without regrading.

gradev5 has no numbered diagram question/prompt. Such results are retained as
unresolved rubric-level evidence; a singleton diagram slot is not a question ID.
"""

from calendar import month_name
from collections import Counter, defaultdict
from copy import deepcopy
import math

from bson import ObjectId
from app.ingestion.criterion_labels import criterion_label_key


def _identifier(value):
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, str) and value.strip():
        return str(ObjectId(value)) if ObjectId.is_valid(value) else value
    return None


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _integer(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isascii() and value.isdigit() and str(int(value)) == value:
        return int(value)
    return None


def _month(value):
    if isinstance(value, str) and value in month_name:
        return list(month_name).index(value) or None
    number = _integer(value)
    return number if number is not None and 1 <= number <= 12 else None


def _session(value):
    # These two spellings are verified in examkeys and both grading pipelines.
    return {"Final Examination": "Final", "Final": "Final", "Mid Term": "Mid Term"}.get(value) if isinstance(value, str) else None


def _identity(document, *, canonical=False):
    fields = ("subjectCode", "examYear", "examMonth", "examSemester", "session") if canonical else (
        "subject_code", "year", "month", "semester", "session_name")
    values = [document.get(field) for field in fields]
    return (values[0], _integer(values[1]), _month(values[2]), _integer(values[3]), _session(values[4]))


def _qno(value):
    number = int(value) if isinstance(value, str) and value.isascii() and value.isdigit() else _integer(value)
    return str(number).zfill(2) if number is not None and number > 0 else None


def _ref(collection, document, path=None):
    result = {"collection": collection, "id": _identifier(document.get("_id"))}
    if path is not None:
        result["path"] = path
    return result


def _issue(target, code, *, source=None, question=None, scope="record"):
    item = {"code": code, "scope": scope}
    if source is not None:
        item["source"] = source
    if question is not None:
        item["questionNumber"] = question
    if item not in target["issues"]:
        target["issues"].append(item)


def _maximum(criteria, field, declared, target, source, scope):
    if not isinstance(criteria, list):
        _issue(target, "invalid_rubric_marks", source=source, scope=scope)
        return None
    values = [c.get(field) for c in criteria if isinstance(c, dict)]
    if not criteria or len(values) != len(criteria) or any(not _number(v) or v < 0 for v in values):
        _issue(target, "invalid_rubric_marks", source=source, scope=scope)
        return None
    maximum = sum(values)
    if maximum <= 0:
        _issue(target, "invalid_rubric_marks", source=source, scope=scope)
        return None
    if declared is not None and (not _number(declared) or not math.isclose(declared, maximum, rel_tol=0, abs_tol=0.001)):
        _issue(target, "rubric_maximum_mismatch", source=source, scope=scope)
        return None
    return maximum


def _check_marks(score, maximum, target, source):
    if not _number(score) or maximum is None or score < 0 or score > maximum:
        _issue(target, "invalid_marks", source=source)


def _criteria_check(rows, rubric_rows, *, key, score_key, max_key, target, source, score):
    def label(row):
        value = row.get(key)
        if key == "point":
            return criterion_label_key(value)
        return _integer(value)

    rubric_rows = rubric_rows if isinstance(rubric_rows, list) else []
    expected = [label(r) for r in rubric_rows if isinstance(r, dict)]
    actual = [label(r) for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []
    if (not expected or None in expected or "" in expected or len(set(expected)) != len(expected)
            or Counter(actual) != Counter(expected)):
        _issue(target, "criterion_mismatch", source=source)
    limits = {label(r): r.get(max_key) for r in rubric_rows if isinstance(r, dict)}
    awards = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            _issue(target, "criterion_mismatch", source=source)
            continue
        award, limit = row.get(score_key), limits.get(label(row))
        if not _number(award) or not _number(limit) or award < 0 or award > limit:
            _issue(target, "invalid_criterion_marks", source=source)
        awards.append(award)
    if _number(score) and awards and all(_number(a) for a in awards) and not math.isclose(sum(awards), score, rel_tol=0, abs_tol=0.001):
        _issue(target, "score_criterion_mismatch", source=source)


def _add_combined_grades(paper, essays, diagrams):
    """Combine existing component marks independently of prompt/artifact recovery."""
    structure = paper["exam"]["examStructure"]
    essay_questions = [q for q in paper["questions"] if q["questionType"] == "Essay"]
    essay_maximum = None
    if len(essay_questions) == structure.count("Essay") and all(_number(q["maximumMarks"]) for q in essay_questions):
        essay_maximum = sum(q["maximumMarks"] for q in essay_questions)
    diagram_rubrics = [r for r in paper["rubrics"] if r["kind"] == "Diagram"]
    grading = {"maximumMarks": None, "componentMaximumMarks": {}, "issues": []}
    if "Essay" in structure:
        grading["componentMaximumMarks"]["essay"] = essay_maximum
    if "Diagram" in structure:
        diagram_maximum = None
        if structure.count("Diagram") == 1 and len(diagram_rubrics) == 1:
            definition = diagram_rubrics[0]["definition"]
            diagram_maximum = _maximum(definition.get("guideLines"), "marks", definition.get("totalMarks"),
                grading, diagram_rubrics[0]["source"], "grading")
        elif len(diagram_rubrics) > 1 or structure.count("Diagram") > 1:
            _issue(grading, "ambiguous_diagram_maximum", scope="grading")
        grading["componentMaximumMarks"]["diagram"] = diagram_maximum
    maxima = grading["componentMaximumMarks"]
    if paper["validation"]["examDefinitionStatus"] == "valid" and maxima and all(_number(v) and v > 0 for v in maxima.values()):
        grading["maximumMarks"] = sum(maxima.values())
    paper["grading"] = grading
    review_codes = {
        "invalid_marks", "invalid_criterion_marks", "criterion_mismatch", "score_criterion_mismatch",
        "evaluation_total_mismatch", "evaluation_maximum_mismatch", "duplicate_submission",
        "duplicate_evaluation", "duplicate_roster_student", "ambiguous_rubric", "missing_rubric",
        "conflicting_rubric_reference", "grading_error", "invalid_evaluation", "ambiguous_answer_slice",
        "unmatched_question", "missing_question_identifier", "invalid_rubric_marks", "rubric_maximum_mismatch",
        "missing_submission_identifier",
    }
    global_review = bool(grading["issues"]) or any(i["code"] in {
        "conflicting_exam_identifier", "conflicting_exam_metadata", "ambiguous_exam_identity",
        "duplicate_question", "ambiguous_rubric", "invalid_roster", "duplicate_roster_student",
        "question_type_conflict", "unexpected_question", "invalid_question_definition",
        "unexpected_question_type",
    } for i in paper["issues"])
    for student in paper["students"]:
        components = {}
        for kind, records in (("essay", essays), ("diagram", diagrams)):
            if kind not in maxima:
                continue
            own = [r for r, _ in records if r["student_id"] == student["studentId"]]
            maximum, score = maxima[kind], None
            if len(own) == 1 and _number(maximum):
                record = own[0]
                if kind == "essay":
                    evaluation = record.get("evaluation")
                    evaluation = evaluation if isinstance(evaluation, dict) else {}
                    rows = evaluation.get("results")
                    rows = rows if isinstance(rows, list) else []
                    expected = {q["questionNumber"]: q for q in essay_questions}
                    numbers = [_qno(r.get("q_no")) if isinstance(r, dict) else None for r in rows]
                    awards = [r.get("score") for r in rows if isinstance(r, dict)]
                    valid = (record.get("status") == "graded" and len(numbers) == len(expected)
                        and len(set(numbers)) == len(numbers) and set(numbers) == set(expected)
                        and all(_identifier(record.get("rubric_ref")) == q["rubricRef"]["id"] for q in essay_questions)
                        and len(awards) == len(rows) and all(_number(v) for v in awards)
                        and all(0 <= r["score"] <= expected[no]["maximumMarks"] for r, no in zip(rows, numbers)))
                    total, reported_maximum = evaluation.get("total_score"), evaluation.get("max_score")
                    if (valid and _number(total) and _number(reported_maximum) and reported_maximum == maximum
                            and math.isclose(total, sum(awards), rel_tol=0, abs_tol=0.001)):
                        score = total
                else:
                    result = record.get("evaluation_result")
                    result = result if isinstance(result, dict) else {}
                    grade = result.get("agent_grading")
                    grade = grade if isinstance(grade, dict) else {}
                    total = grade.get("agent_marks")
                    if (result.get("status") == "ok" and _number(total) and 0 <= total <= maximum
                            and _number(grade.get("max_marks")) and grade["max_marks"] == maximum
                            and _identifier(record.get("guideline_object_id")) == diagram_rubrics[0]["source"]["id"]
                            and all(v is None or (_number(v) and v == total) for v in (
                                record.get("agent_marks"), result.get("agent_marks")))):
                        score = total
            components[kind] = {"awardedMarks": score, "maximumMarks": maximum,
                "sourceRefs": [_ref("submissions" if kind == "essay" else "diagram_evaluations", r) for r in own]}
        reviewed = global_review or any(i["code"] in review_codes for i in student["issues"])
        available = (grading["maximumMarks"] is not None
            and not any(i["code"] == "missing_submission_identifier" for i in student["issues"])
            and all(c["awardedMarks"] is not None for c in components.values()))
        awarded = sum(c["awardedMarks"] for c in components.values()) if available else None
        student["grading"] = {"components": components, "awardedMarks": awarded,
            "maximumMarks": grading["maximumMarks"],
            "percentage": round(awarded / grading["maximumMarks"] * 100, 2) if available else None,
            "status": "needs_review" if reviewed else "complete" if available else "pending"}


def reconstruct_exam_paper(exam_key: str, sources: dict) -> dict:
    """Reconstruct a paper, preserving ambiguous records as source references.

    sources contains examkeys, rubrics (with _source_collection provenance),
    submissions, diagram_marking and diagram_evaluations. This function performs
    no I/O and never modifies its inputs. A complete student requires a complete
    question paper, unambiguous answers and verified marks; no marks are summed
    across unrelated or duplicate attempts.
    """
    paper = {
        "exam": None, "questions": [], "rubrics": [], "students": [], "issues": [],
        "unresolvedRecords": [], "unresolvedDiagramQuestions": [],
        "validation": {"examDefinitionStatus": "invalid", "questionPaperStatus": "incomplete",
                       "expectedQuestionCount": None, "actualQuestionCount": 0,
                       "missingQuestionNumbers": [], "missingQuestionTypes": [], "status": "incomplete"},
    }
    if "readStartedAt" in sources:
        paper["sourceRead"] = {"startedAt": sources["readStartedAt"],
                               "completedAt": sources.get("readCompletedAt"), "consistentSnapshot": False}
    exams = [e for e in sources.get("examkeys", []) if e.get("examKey") == exam_key]
    if len(exams) != 1:
        _issue(paper, "missing_exam" if not exams else "duplicate_exam_key", scope="exam")
        return paper
    exam = exams[0]
    paper["exam"] = deepcopy(exam)
    identity = _identity(exam, canonical=True)
    structure = exam.get("examStructure")
    peers = [e for e in sources.get("examkeys", []) if _identity(e, canonical=True) == identity]
    if (not isinstance(exam_key, str) or not exam_key.strip() or _identifier(exam.get("_id")) is None
            or None in identity or not isinstance(identity[0], str) or not identity[0].strip()
            or identity[1] < 1900 or identity[3] not in (1, 2)
            or not isinstance(structure, list) or not structure
            or any(t not in ("Essay", "Diagram") for t in structure)):
        _issue(paper, "invalid_exam_definition", scope="exam")
        return paper
    paper["validation"]["expectedQuestionCount"] = len(structure)
    if len(peers) != 1:
        _issue(paper, "ambiguous_exam_identity", scope="exam")
    else:
        paper["validation"]["examDefinitionStatus"] = "valid"

    def matches(document, source):
        supplied_key = document.get("examKey")
        actual = _identity(document)
        if supplied_key:
            if supplied_key != exam_key:
                if actual == identity:
                    _issue(paper, "conflicting_exam_identifier", source=source)
                return None
            fields = ("subject_code", "year", "month", "semester", "session_name")
            if any(field in document and document[field] is not None and actual[i] != identity[i] for i, field in enumerate(fields)):
                _issue(paper, "conflicting_exam_metadata", source=source)
                return None
            return "examKey"
        if actual == identity:
            if len(peers) != 1:
                _issue(paper, "ambiguous_exam_identity", source=source)
                return None
            return "full_metadata"
        return None

    def unresolved(source, reason):
        paper["unresolvedRecords"].append({"source": source, "reason": reason})

    matched_rubrics = [r for r in sources.get("rubrics", []) if matches(r, _ref(r.get("_source_collection", "rubricCollection"), r))]
    by_rubric_id = defaultdict(list)
    for rubric in matched_rubrics:
        by_rubric_id[_identifier(rubric.get("_id"))].append(rubric)
    candidates = defaultdict(list)
    rubric_for_question = {}
    roster = set()
    duplicate_roster = set()
    for rid, rubrics in by_rubric_id.items():
        for rubric in rubrics:
            rref = _ref(rubric.get("_source_collection", "rubricCollection"), rubric)
            exam_roster = rubric.get("exam_roster") or {}
            if not isinstance(exam_roster, dict) or not isinstance(exam_roster.get("students", []), list):
                _issue(paper, "invalid_roster", source=rref)
                continue
            ids = []
            for row in exam_roster.get("students", []):
                sid = row.get("student_id") if isinstance(row, dict) else None
                if not isinstance(sid, str) or not sid.strip() or sid.strip().upper() == "UNKNOWN":
                    _issue(paper, "invalid_roster", source=rref)
                    continue
                ids.append(sid)
                roster.add(sid)
            declared_duplicates = exam_roster.get("duplicate_roster_ids", [])
            if not isinstance(declared_duplicates, list):
                _issue(paper, "invalid_roster", source=rref)
                declared_duplicates = []
            if len(ids) != len(set(ids)) or declared_duplicates:
                _issue(paper, "duplicate_roster_student", source=rref)
                duplicate_roster.update(sid for sid, count in Counter(ids).items() if count > 1)
                duplicate_roster.update(sid for sid in declared_duplicates if isinstance(sid, str))
        if rid is None or len(rubrics) != 1:
            _issue(paper, "ambiguous_rubric", scope="paper")
            continue
        rubric = rubrics[0]
        source = _ref(rubric.get("_source_collection", "rubricCollection"), rubric)
        paper["rubrics"].append({"source": source, "kind": "Essay", "definition": deepcopy(rubric.get("questions"))})
        raw_questions = rubric.get("questions")
        if not isinstance(raw_questions, list):
            _issue(paper, "invalid_question_definition", source=source, scope="paper")
            continue
        for index, question in enumerate(raw_questions):
            qref = {**source, "path": f"questions.{index}"}
            if not isinstance(question, dict):
                _issue(paper, "invalid_question_definition", source=qref, scope="paper")
                unresolved(qref, "invalid_question_definition")
                continue
            no = _qno(question.get("question_no"))
            if no is None:
                _issue(paper, "missing_question_identifier", source=qref, scope="paper")
                unresolved(qref, "missing_question_identifier")
                continue
            position = int(no) - 1
            if position >= len(structure) or structure[position] != "Essay":
                reason = "question_type_conflict" if position < len(structure) else "unexpected_question"
                _issue(paper, reason, source=qref, question=no, scope="paper")
                unresolved(qref, reason)
                continue
            candidates[no].append((rubric, question, qref))
    for no, definitions in sorted(candidates.items()):
        if len(definitions) != 1:
            _issue(paper, "duplicate_question", question=no, scope="paper")
            for _, _, source in definitions:
                unresolved(source, "duplicate_question")
            continue
        rubric, question, source = definitions[0]
        maximum = _maximum(question.get("criteria") or [], "marks", question.get("max_marks"), paper, source, "paper")
        if not isinstance(question.get("question_text"), str) or not question["question_text"].strip():
            _issue(paper, "missing_question_text", source=source, scope="paper")
        item = {"questionId": f"{source['collection']}:{source['id']}:{no}", "questionNumber": no,
                "questionType": "Essay", "questionText": question.get("question_text"),
                "maximumMarks": maximum, "rubricRef": source}
        paper["questions"].append(item)
        rubric_for_question[item["questionId"]] = (rubric, question)

    students = {}

    def get_student(student_id):
        if student_id not in students:
            students[student_id] = {"studentId": student_id, "answers": [], "submissionRefs": [],
                                    "unresolvedEvaluations": [], "issues": [], "status": "incomplete"}
        return students[student_id]

    for sid in sorted(roster):
        get_student(sid)
        if sid in duplicate_roster:
            _issue(students[sid], "duplicate_roster_student")

    def matched_records(collection):
        result = []
        for record in sources.get(collection, []):
            if record.get("archived_at") is not None:
                continue
            ref = _ref(collection, record)
            method = matches(record, ref)
            if not method:
                continue
            sid = record.get("student_id")
            if not isinstance(sid, str) or not sid.strip() or sid.strip().upper() == "UNKNOWN":
                _issue(paper, "missing_student_identifier", source=ref)
                unresolved(ref, "missing_student_identifier")
                continue
            if _identifier(record.get("_id")) is None:
                _issue(get_student(sid), "missing_submission_identifier", source=ref)
                unresolved(ref, "missing_submission_identifier")
                continue
            get_student(sid)
            result.append((record, method))
        return result

    essays = matched_records("submissions")
    diagrams = matched_records("diagram_evaluations")
    essay_groups = defaultdict(list)
    for record, method in essays:
        essay_groups[record["student_id"]].append((record, method))
    for sid, records in essay_groups.items():
        student = get_student(sid)
        student["submissionRefs"] = [_ref("submissions", r) for r, _ in records]
        if len(records) != 1:
            _issue(student, "duplicate_submission")
            student["unresolvedEvaluations"].extend({"source": _ref("submissions", r), "reason": "duplicate_submission"} for r, _ in records)
            continue
        record, method = records[0]
        source = _ref("submissions", record)
        rid = _identifier(record.get("rubric_ref"))
        rubrics = by_rubric_id.get(rid, []) if rid is not None else []
        if len(rubrics) != 1:
            _issue(student, "ambiguous_rubric" if rubrics else "missing_rubric", source=source)
            student["unresolvedEvaluations"].append({"source": source, "reason": "unmatched_rubric"})
            continue
        rubric = rubrics[0]
        evaluation = record.get("evaluation")
        if not isinstance(evaluation, dict) or not isinstance(evaluation.get("results"), list):
            _issue(student, "missing_evaluation", source=source)
            continue
        if record.get("status") != "graded":
            _issue(student, "submission_not_graded", source=source)
        results = defaultdict(list)
        for i, row in enumerate(evaluation["results"]):
            result_ref = {**source, "path": f"evaluation.results.{i}"}
            no = _qno(row.get("q_no")) if isinstance(row, dict) else None
            if no is None:
                _issue(student, "missing_question_identifier", source=result_ref)
                student["unresolvedEvaluations"].append({"source": result_ref, "reason": "missing_question_identifier"})
                continue
            results[no].append((row, result_ref))
        for no, rows in results.items():
            definitions = [q for q in paper["questions"] if q["questionNumber"] == no and rubric_for_question[q["questionId"]][0] is rubric]
            if len(rows) != 1 or len(definitions) != 1:
                reason = "duplicate_evaluation" if len(rows) != 1 else "unmatched_question"
                _issue(student, reason, question=no)
                student["unresolvedEvaluations"].extend({"source": ref, "reason": reason} for _, ref in rows)
                continue
            row, result_ref = rows[0]
            question = definitions[0]
            score, maximum = row.get("score"), question["maximumMarks"]
            _check_marks(score, maximum, student, result_ref)
            _criteria_check(row.get("criteria_breakdown"), rubric_for_question[question["questionId"]][1].get("criteria") or [],
                            key="point", score_key="awarded_marks", max_key="marks", target=student, source=result_ref, score=score)
            text, slice_source = row.get("answer_excerpt"), row.get("slice_source")
            if not isinstance(text, str) or not text.strip():
                _issue(student, "missing_answer", source=result_ref)
            if isinstance(text, str) and len(text) >= 1200:
                _issue(student, "answer_excerpt_truncated", source=result_ref)
            if slice_source != "split":
                _issue(student, "ambiguous_answer_slice", source=result_ref)
            if row.get("error") or row.get("grading_source") in ("error", "emergency"):
                _issue(student, "grading_error", source=result_ref)
            if slice_source != "split":
                student["unresolvedEvaluations"].append({"source": result_ref,
                    "reason": "ambiguous_answer_slice", "questionId": question["questionId"],
                    "evaluation": deepcopy(row)})
                continue
            student["answers"].append({"questionId": question["questionId"], "questionNumber": no,
                "examMatch": method, "source": result_ref, "awardedMarks": score, "maximumMarks": maximum,
                "answer": {"text": text, "kind": "saved_grading_excerpt", "sliceSource": slice_source,
                           "transcriptRef": {**source, "path": "cleaned_ocr_transcript"}},
                "evaluation": deepcopy(row)})
        scores = [r.get("score") for r in evaluation["results"] if isinstance(r, dict)]
        if scores and all(_number(s) for s in scores):
            total = evaluation.get("total_score")
            if not _number(total) or not math.isclose(total, sum(scores), rel_tol=0, abs_tol=0.001):
                _issue(student, "evaluation_total_mismatch", source=source)
        raw_questions = rubric.get("questions")
        rubric_maxima = [q.get("max_marks") for q in raw_questions if isinstance(q, dict)] if isinstance(raw_questions, list) else []
        if (not rubric_maxima or not all(_number(m) and m > 0 for m in rubric_maxima)
                or not _number(evaluation.get("max_score"))
                or not math.isclose(evaluation["max_score"], sum(rubric_maxima), rel_tol=0, abs_tol=0.001)):
            _issue(student, "evaluation_maximum_mismatch", source=source)

    guidelines = defaultdict(list)
    for guideline in sources.get("diagram_marking", []):
        gid = _identifier(guideline.get("_id"))
        if gid is not None:
            guidelines[gid].append(guideline)
    diagram_groups = Counter((r["student_id"], _identifier(r.get("guideline_object_id"))) for r, _ in diagrams)
    used_guidelines = set()
    for record, method in diagrams:
        source = _ref("diagram_evaluations", record)
        student = get_student(record["student_id"])
        gid = _identifier(record.get("guideline_object_id"))
        options = guidelines.get(gid, [])
        if len(options) != 1:
            reason = "ambiguous_rubric" if options else "missing_rubric"
            _issue(student, reason, source=source)
            student["unresolvedEvaluations"].append({"source": source, "reason": reason})
            continue
        guideline = options[0]
        gref = _ref("diagram_marking", guideline)
        if gid not in used_guidelines:
            used_guidelines.add(gid)
            paper["rubrics"].append({"source": gref, "kind": "Diagram",
                "definition": {k: deepcopy(guideline[k]) for k in ("examCode", "guideLines", "totalMarks", "source_file") if k in guideline}})
            paper["unresolvedDiagramQuestions"].append({"questionId": None, "questionNumber": None,
                "questionType": "Diagram", "questionText": None, "rubricRef": gref,
                "examAssociation": "referenced_by_matching_evaluations"})
            _issue(paper, "unverified_diagram_question", source=gref, scope="paper")
            if "Diagram" not in structure:
                _issue(paper, "unexpected_question_type", source=gref, scope="paper")
        maximum = _maximum(guideline.get("guideLines") or [], "marks", guideline.get("totalMarks"), student, gref, "record")
        result = record.get("evaluation_result") or {}
        if not isinstance(result, dict):
            _issue(student, "invalid_evaluation", source=source)
            result = {}
        grade = result.get("agent_grading")
        if not isinstance(grade, dict):
            _issue(student, "missing_evaluation", source=source)
            grade = {}
        if result.get("status") != "ok":
            _issue(student, "grading_error", source=source)
        score = grade.get("agent_marks")
        _check_marks(score, maximum, student, source)
        if not _number(grade.get("max_marks")) or grade.get("max_marks") != maximum:
            _issue(student, "evaluation_maximum_mismatch", source=source)
        for supplied in (record.get("agent_marks"), result.get("agent_marks")):
            if supplied is not None and (not _number(supplied) or supplied != score):
                _issue(student, "evaluation_total_mismatch", source=source)
        if result.get("guideline_object_id") not in (None, record.get("guideline_object_id")):
            _issue(student, "conflicting_rubric_reference", source=source)
        _criteria_check(grade.get("criterion_results"), guideline.get("guideLines") or [], key="id",
                        score_key="marks", max_key="marks", target=student, source=source, score=score)
        duplicate = diagram_groups[(record["student_id"], gid)] > 1
        if duplicate:
            _issue(student, "duplicate_evaluation", source=source)
        _issue(student, "unverified_diagram_question", source=source)
        _issue(student, "missing_original_diagram_artifact", source=source)
        student["unresolvedEvaluations"].append({"source": source,
            "reason": "duplicate_evaluation" if duplicate else "unverified_diagram_question",
            "examMatch": method, "rubricRef": gref, "awardedMarks": score,
            "maximumMarks": maximum, "evaluation": deepcopy(grade),
            "answerRef": {**source, "path": "diagram_details"}})

    actual = {q["questionNumber"] for q in paper["questions"]}
    missing = [str(i).zfill(2) for i in range(1, len(structure) + 1) if str(i).zfill(2) not in actual]
    paper["validation"].update(actualQuestionCount=len(actual), missingQuestionNumbers=missing,
        missingQuestionTypes=sorted({structure[int(no) - 1] for no in missing}))
    if missing:
        _issue(paper, "question_count_mismatch", scope="paper")
    complete = not missing and not any(i["scope"] in ("exam", "paper") for i in paper["issues"])
    paper["validation"]["questionPaperStatus"] = "complete" if complete else "incomplete"
    for sid, student in sorted(students.items()):
        if "Essay" in structure and sid not in essay_groups:
            _issue(student, "missing_submission")
        answered = {a["questionNumber"] for a in student["answers"]}
        for i, kind in enumerate(structure, 1):
            no = str(i).zfill(2)
            if no not in answered:
                _issue(student, "missing_evaluation", question=no)
        student["status"] = "complete" if complete and not student["issues"] else "incomplete"
        paper["students"].append(student)
    paper["validation"]["status"] = "valid" if complete and not paper["issues"] and all(s["status"] == "complete" for s in paper["students"]) else "incomplete"
    _add_combined_grades(paper, essays, diagrams)
    return paper


def reconstruction_summary(paper: dict) -> dict:
    """Counts/statuses only: safe for console output without student answers/IDs."""
    issues = Counter(i["code"] for i in paper["issues"])
    student_issues = Counter(i["code"] for s in paper["students"] for i in s["issues"])
    return {"examKey": (paper["exam"] or {}).get("examKey"), "validation": paper["validation"],
            "studentCount": len(paper["students"]),
            "completeStudentCount": sum(s["status"] == "complete" for s in paper["students"]),
            "linkedAnswerCount": sum(len(s["answers"]) for s in paper["students"]),
            "unresolvedDiagramQuestionCount": len(paper["unresolvedDiagramQuestions"]),
            "unresolvedEvaluationCount": sum(len(s["unresolvedEvaluations"]) for s in paper["students"]),
            "maximumMarks": (paper.get("grading") or {}).get("maximumMarks"),
            "gradeStatusCounts": dict(Counter(s["grading"]["status"] for s in paper["students"])),
            "issueCounts": dict(issues), "studentIssueCounts": dict(student_issues)}

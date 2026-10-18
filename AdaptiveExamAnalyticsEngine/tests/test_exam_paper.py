"""Synthetic fixtures follow the observed gradev5 schema; no live DB writes."""

from copy import deepcopy

import pytest

from app.services.exam_paper import reconstruct_exam_paper, reconstruction_summary


def fixture(essays=4, diagram=True, students=("S1", "S2")):
    exam = {
        "_id": "exam-1", "examKey": "EXAM-2025-S1-Apr", "subjectCode": "IT2040",
        "subjectName": "DBMS", "examYear": 2025, "examSemester": 1,
        "examMonth": "April", "session": "Final",
        "examStructure": ["Essay"] * essays + (["Diagram"] if diagram else []),
    }
    identity = {"examKey": exam["examKey"], "subject_code": "IT2040", "year": 2025,
                "month": 4, "semester": 1, "session_name": "Final Examination"}
    questions = [
        {"question_no": f"{i:02}", "question_text": f"Explain concept {i}.", "max_marks": 5,
         "criteria": [{"point": f"Criterion {i}", "marks": 5}]}
        for i in range(1, essays + 1)
    ]
    rubric = {"_id": "rubric-1", "_source_collection": "rubicCollection", **identity,
              "questions": questions, "exam_roster": {"students": [{"student_id": s} for s in students]}}
    submissions = [
        {"_id": f"essay-{s}", **identity, "student_id": s, "rubric_ref": "rubric-1",
         "status": "graded", "cleaned_ocr_transcript": "Full transcript",
         "evaluation": {"total_score": 3 * essays, "max_score": 5 * essays, "results": [
             {"q_no": q["question_no"], "score": 3, "answer_excerpt": f"{s} answer {i}",
              "slice_source": "split", "grading_source": "groq", "error": None,
              "feedback": "More detail.", "criteria_breakdown": [
                  {"point": q["criteria"][0]["point"], "awarded_marks": 3, "reason": "Partial"}]}
             for i, q in enumerate(questions, 1)]}}
        for s in students
    ]
    guideline = {"_id": "guide-1", "examCode": "ERD-004", "totalMarks": 20,
                 "guideLines": [{"id": 1, "criterion": "Correct diagram", "marks": 20}],
                 "source_file": {"filename": "marking.pdf", "extracted_text": "Marking guidance"}}
    evaluations = [
        {"_id": f"diagram-{s}", **identity, "student_id": s,
         "guideline_object_id": "guide-1", "agent_marks": 12,
         "diagram_details": {"structure": {"entities": {"Course": {}}}},
         "evaluation_result": {"status": "ok", "guideline_object_id": "guide-1",
             "agent_marks": 12, "agent_grading": {"agent_marks": 12, "max_marks": 20,
                 "criterion_results": [{"id": 1, "marks": 12, "reason": "Partial"}], "feedback": "Review links"}}}
        for s in students
    ] if diagram else []
    return {"examkeys": [exam], "rubrics": [rubric], "submissions": submissions,
            "diagram_marking": [guideline], "diagram_evaluations": evaluations}


def reconstruct(sources):
    return reconstruct_exam_paper("EXAM-2025-S1-Apr", sources)


def codes(value):
    return {issue["code"] for issue in value["issues"]}


def test_four_essays_and_diagram_preserve_unverified_question_instead_of_inventing_q5():
    sources = fixture()
    original = deepcopy(sources)
    paper = reconstruct(sources)
    assert paper["validation"]["examDefinitionStatus"] == "valid"
    assert paper["validation"]["questionPaperStatus"] == "incomplete"
    assert paper["validation"]["actualQuestionCount"] == 4
    assert paper["validation"]["expectedQuestionCount"] == 5
    assert paper["validation"]["missingQuestionTypes"] == ["Diagram"]
    assert "unverified_diagram_question" in codes(paper)
    assert len(paper["unresolvedDiagramQuestions"]) == 1
    assert paper["unresolvedDiagramQuestions"][0]["questionId"] is None
    assert paper["unresolvedDiagramQuestions"][0]["questionText"] is None
    assert len(paper["students"]) == 2
    for student in paper["students"]:
        assert student["status"] == "incomplete"
        assert len(student["answers"]) == 4
        assert len(student["unresolvedEvaluations"]) == 1
        assert all(student["studentId"] in a["answer"]["text"] for a in student["answers"])
    assert sources == original


def test_complete_essay_only_definition_does_not_need_any_student_evaluation():
    sources = fixture(diagram=False)
    sources["submissions"] = []
    paper = reconstruct(sources)
    assert paper["validation"]["questionPaperStatus"] == "complete"
    assert len(paper["questions"]) == 4
    assert len(paper["students"]) == 2  # authoritative roster, not fabricated submissions
    assert all(s["status"] == "incomplete" for s in paper["students"])
    assert all("missing_submission" in codes(s) for s in paper["students"])


def test_complete_essay_student_preserves_results_exactly():
    sources = fixture(diagram=False)
    paper = reconstruct(sources)
    assert all(s["status"] == "complete" for s in paper["students"])
    result = paper["students"][0]["answers"][0]
    assert result["evaluation"] == sources["submissions"][0]["evaluation"]["results"][0]
    assert result["source"]["collection"] == "submissions"
    assert result["maximumMarks"] == 5


def test_missing_key_uses_complete_unique_metadata_with_explicit_month_session_mapping():
    sources = fixture(diagram=False)
    del sources["rubrics"][0]["examKey"]
    del sources["submissions"][0]["examKey"]
    sources["submissions"][0]["month"] = "4"
    paper = reconstruct(sources)
    assert len(paper["students"][0]["answers"]) == 4
    assert paper["students"][0]["answers"][0]["examMatch"] == "full_metadata"


def test_nonempty_conflicting_exam_key_never_uses_metadata_fallback():
    sources = fixture(diagram=False)
    sources["submissions"][0]["examKey"] = "ANOTHER-EXAM"
    paper = reconstruct(sources)
    assert "conflicting_exam_identifier" in codes(paper)
    assert paper["students"][0]["answers"] == []


@pytest.mark.parametrize("field,value", [("year", 2027), ("semester", 2), ("session_name", "Mid Term"), ("month", 11), ("subject_code", "IT9999")])
def test_same_explicit_key_with_conflicting_metadata_is_quarantined(field, value):
    sources = fixture(diagram=False)
    sources["submissions"][0][field] = value
    paper = reconstruct(sources)
    assert "conflicting_exam_metadata" in codes(paper)
    assert paper["students"][0]["answers"] == []


def test_two_exams_same_subject_do_not_mix_students_or_questions():
    sources = fixture(diagram=False)
    other = fixture(essays=2, diagram=False, students=("OTHER",))
    exam = other["examkeys"][0]
    exam.update(examKey="EXAM-IT2040-2027-S2-Nov-FINAL", examYear=2027, examSemester=2, examMonth="November")
    for doc in other["rubrics"] + other["submissions"]:
        doc.update(examKey=exam["examKey"], year=2027, month=11, semester=2)
    other["rubrics"][0]["_id"] = "other-rubric"
    other["submissions"][0]["rubric_ref"] = "other-rubric"
    for collection in sources:
        sources[collection] += other[collection]
    paper = reconstruct(sources)
    assert len(paper["questions"]) == 4
    assert {s["studentId"] for s in paper["students"]} == {"S1", "S2"}


def test_missing_diagram_and_missing_essay_and_wrong_count_reported():
    sources = fixture()
    sources["diagram_evaluations"] = []
    sources["rubrics"][0]["questions"].pop()
    paper = reconstruct(sources)
    assert paper["validation"]["missingQuestionNumbers"] == ["04", "05"]
    assert set(paper["validation"]["missingQuestionTypes"]) == {"Essay", "Diagram"}
    assert "question_count_mismatch" in codes(paper)


def test_fifth_essay_is_not_relabelled_as_diagram_or_discarded():
    sources = fixture(essays=5)
    sources["examkeys"][0]["examStructure"] = ["Essay"] * 4 + ["Diagram"]
    paper = reconstruct(sources)
    assert "question_type_conflict" in codes(paper)
    assert len(paper["questions"]) == 4
    assert any(x["reason"] == "question_type_conflict" for x in paper["unresolvedRecords"])
    assert len(paper["students"][0]["answers"]) == 4
    assert any(x["reason"] == "unmatched_question" for x in paper["students"][0]["unresolvedEvaluations"])


@pytest.mark.parametrize("kind", ["question", "submission", "evaluation", "diagram"])
def test_duplicates_are_flagged_and_never_silently_selected(kind):
    sources = fixture()
    if kind == "question":
        sources["rubrics"][0]["questions"].append(deepcopy(sources["rubrics"][0]["questions"][0]))
    elif kind == "submission":
        duplicate = deepcopy(sources["submissions"][0]); duplicate["_id"] = "another-attempt"
        sources["submissions"].append(duplicate)
    elif kind == "evaluation":
        rows = sources["submissions"][0]["evaluation"]["results"]
        rows.append(deepcopy(rows[0]))
    else:
        duplicate = deepcopy(sources["diagram_evaluations"][0]); duplicate["_id"] = "diagram-duplicate"
        sources["diagram_evaluations"].append(duplicate)
    paper = reconstruct(sources)
    assert paper["validation"]["questionPaperStatus"] == "incomplete"
    assert any("duplicate" in c for c in codes(paper) | codes(paper["students"][0]))
    assert len({a["questionId"] for a in paper["students"][0]["answers"]}) == len(paper["students"][0]["answers"])
    if kind in {"question", "evaluation"}:
        assert not any(a["questionNumber"] == "01" for a in paper["students"][0]["answers"])
    if kind == "submission":
        assert paper["students"][0]["answers"] == []


def test_rubric_must_match_reference_and_exam_not_just_subject():
    sources = fixture(diagram=False)
    sources["submissions"][0]["rubric_ref"] = "missing-rubric"
    paper = reconstruct(sources)
    assert "missing_rubric" in codes(paper["students"][0])
    assert paper["students"][0]["answers"] == []


def test_two_rubric_spellings_with_same_id_are_ambiguous():
    sources = fixture(diagram=False)
    duplicate = deepcopy(sources["rubrics"][0])
    duplicate["_source_collection"] = "rubricCollection"
    sources["rubrics"].append(duplicate)
    paper = reconstruct(sources)
    assert "ambiguous_rubric" in codes(paper)
    assert all(s["answers"] == [] for s in paper["students"])


@pytest.mark.parametrize("score", [None, -1, 6, float("nan"), float("inf"), True, "3"])
def test_invalid_or_missing_marks_are_preserved_and_flagged(score):
    sources = fixture(diagram=False)
    sources["submissions"][0]["evaluation"]["results"][0]["score"] = score
    paper = reconstruct(sources)
    student = paper["students"][0]
    assert "invalid_marks" in codes(student)
    assert student["status"] == "incomplete"
    if score is None:
        assert student["answers"][0]["awardedMarks"] is None


def test_score_criterion_disagreement_and_unknown_criteria_flagged():
    sources = fixture(diagram=False)
    row = sources["submissions"][0]["evaluation"]["results"][0]
    row["criteria_breakdown"][0].update(point="Different criterion", awarded_marks=0)
    paper = reconstruct(sources)
    assert "criterion_mismatch" in codes(paper["students"][0])
    assert "score_criterion_mismatch" in codes(paper["students"][0])


def test_missing_evaluation_is_not_zero_and_does_not_invalidate_definition():
    sources = fixture(diagram=False)
    sources["submissions"][0].update(status="processing", evaluation=None)
    paper = reconstruct(sources)
    assert paper["validation"]["questionPaperStatus"] == "complete"
    assert paper["students"][0]["answers"] == []
    assert "missing_evaluation" in codes(paper["students"][0])


def test_truncated_excerpt_or_full_paper_fallback_never_claims_complete_answer():
    sources = fixture(diagram=False)
    sources["submissions"][0]["evaluation"]["results"][0]["answer_excerpt"] = "x" * 1200
    sources["submissions"][0]["evaluation"]["results"][1]["slice_source"] = "full"
    paper = reconstruct(sources)
    student = paper["students"][0]
    assert {"answer_excerpt_truncated", "ambiguous_answer_slice"} <= codes(student)
    assert student["status"] == "incomplete"


@pytest.mark.parametrize("field", ["student_id", "rubric_ref"])
def test_missing_id_is_not_replaced_with_another_students_or_rubric(field):
    sources = fixture(diagram=False)
    del sources["submissions"][0][field]
    paper = reconstruct(sources)
    assert paper["students"][0]["answers"] == []
    assert len(paper["students"][1]["answers"]) == 4


def test_ambiguous_legacy_exam_mapping_and_duplicate_canonical_keys_fail_closed():
    sources = fixture(diagram=False)
    duplicate = deepcopy(sources["examkeys"][0]); duplicate["_id"] = "exam-2"
    duplicate["examKey"] = "LEGACY-ALIAS"
    sources["examkeys"].append(duplicate)
    del sources["rubrics"][0]["examKey"]
    paper = reconstruct(sources)
    assert "ambiguous_exam_identity" in codes(paper)
    assert not paper["questions"]
    duplicate["examKey"] = "EXAM-2025-S1-Apr"
    paper = reconstruct(sources)
    assert paper["validation"]["examDefinitionStatus"] == "invalid"


def test_missing_canonical_exam_and_missing_question_number_fail_closed():
    sources = fixture(diagram=False)
    sources["rubrics"][0]["questions"][0]["question_no"] = None
    assert "missing_question_identifier" in codes(reconstruct(sources))
    sources["examkeys"] = []
    assert reconstruct(sources)["validation"]["examDefinitionStatus"] == "invalid"


def test_default_summary_contains_no_student_ids_answers_or_crop_paths():
    paper = reconstruct(fixture(students=("PRIVATE-STUDENT-A", "PRIVATE-STUDENT-B")))
    summary = reconstruction_summary(paper)
    assert summary["studentCount"] == 2
    assert "students" not in summary
    assert "PRIVATE-STUDENT" not in repr(summary)
    assert "answer 1" not in repr(summary)


class ReadOnlyCollection:
    def __init__(self, docs):
        self.docs, self.queries = docs, []

    async def find_one(self, query, projection=None, **kwargs):
        docs = await self.find(query, projection).to_list(length=1)
        return docs[0] if docs else None

    def find(self, query, projection=None):
        self.queries.append(query)
        def matches(doc, condition):
            for field, expected in condition.items():
                if field == "$or":
                    if not any(matches(doc, branch) for branch in expected):
                        return False
                elif isinstance(expected, dict) and "$in" in expected:
                    if doc.get(field) not in expected["$in"]:
                        return False
                elif doc.get(field) != expected:
                    return False
            return True
        docs = [deepcopy(d) for d in self.docs if matches(d, query)]
        class Cursor:
            async def to_list(self, length=None):
                return docs
        return Cursor()


class ReadOnlyDatabase:
    def __init__(self, sources):
        self.collections = {name: ReadOnlyCollection(sources.get(name, [])) for name in (
            "examkeys", "submissions", "diagram_evaluations", "diagram_marking")}
        for name in ("rubicCollection", "rubricCollection"):
            self.collections[name] = ReadOnlyCollection([
                r for r in sources["rubrics"] if r["_source_collection"] == name])

    def __getitem__(self, name):
        return self.collections[name]

    async def list_collection_names(self):
        return list(self.collections)


def immediate(coroutine):
    # All fake queries complete immediately; a real I/O suspension is an error.
    try:
        coroutine.send(None)
    except StopIteration as finished:
        return finished.value
    finally:
        coroutine.close()
    raise AssertionError("Unexpected real I/O in read-only fixture")


def test_loader_uses_targeted_queries_both_rubric_spellings_and_exact_references():
    from app.db.repository import load_exam_paper_sources
    sources = fixture()
    db = ReadOnlyDatabase(sources)
    loaded = immediate(load_exam_paper_sources(db, "EXAM-2025-S1-Apr"))
    assert len(loaded["rubrics"]) == 1
    assert loaded["rubrics"][0]["_source_collection"] == "rubicCollection"
    assert len(loaded["submissions"]) == 2
    assert len(loaded["diagram_marking"]) == 1
    assert "ERD-004" not in repr(db["diagram_marking"].queries)
    assert all(query for collection in db.collections.values() for query in collection.queries)
    assert reconstruct(loaded)["validation"]["actualQuestionCount"] == 4


def test_loader_fetches_conflicts_and_unrelated_referenced_rubrics_for_validation():
    from app.db.repository import load_exam_paper_sources
    sources = fixture(diagram=False)
    sources["submissions"][0]["year"] = 2027  # explicit key still pulls conflicting record
    sources["rubrics"][0]["examKey"] = "DIFFERENT"
    sources["rubrics"][0]["year"] = 2027  # ref pulls rubric; service must reject it
    loaded = immediate(load_exam_paper_sources(ReadOnlyDatabase(sources), "EXAM-2025-S1-Apr"))
    assert len(loaded["rubrics"]) == 1
    paper = reconstruct(loaded)
    assert not paper["questions"]
    assert "conflicting_exam_metadata" in codes(paper)


def test_loader_does_not_fetch_every_exam_student_or_rubric_on_missing_key():
    from app.db.repository import load_exam_paper_sources
    db = ReadOnlyDatabase(fixture())
    loaded = immediate(load_exam_paper_sources(db, "MISSING"))
    assert loaded["examkeys"] == []
    assert not db["submissions"].queries
    assert not db["rubicCollection"].queries


def test_reported_essay_maximum_must_match_the_referenced_rubric():
    sources = fixture(diagram=False)
    sources["submissions"][0]["evaluation"]["max_score"] = 999
    student = reconstruct(sources)["students"][0]
    assert student["status"] == "incomplete"
    assert "evaluation_maximum_mismatch" in codes(student)


def test_full_paper_fallback_is_not_counted_as_several_question_answers():
    sources = fixture(diagram=False)
    for row in sources["submissions"][0]["evaluation"]["results"]:
        row.update(slice_source="full", answer_excerpt="Same full paper")
    student = reconstruct(sources)["students"][0]
    assert student["answers"] == []
    assert len(student["unresolvedEvaluations"]) == 4
    assert student["unresolvedEvaluations"][0]["evaluation"]["score"] == 3


@pytest.mark.parametrize("malformation", ["question", "questions_null", "criteria", "criterion_label", "roster", "roster_row", "diagram_result", "diagram_criteria"])
def test_malformed_nested_data_is_reported_instead_of_crashing(malformation):
    sources = fixture()
    if malformation == "question":
        sources["rubrics"][0]["questions"][0] = None
    elif malformation == "questions_null":
        sources["rubrics"][0]["questions"] = None
    elif malformation == "criteria":
        sources["rubrics"][0]["questions"][0]["criteria"] = "broken"
    elif malformation == "criterion_label":
        sources["submissions"][0]["evaluation"]["results"][0]["criteria_breakdown"][0]["point"] = []
    elif malformation == "roster":
        sources["rubrics"][0]["exam_roster"] = "broken"
    elif malformation == "roster_row":
        sources["rubrics"][0]["exam_roster"]["students"].append(None)
    elif malformation == "diagram_result":
        sources["diagram_evaluations"][0]["evaluation_result"] = "broken"
    else:
        sources["diagram_marking"][0]["guideLines"] = "broken"
    paper = reconstruct(sources)
    assert paper["validation"]["status"] == "incomplete"
    assert codes(paper) | set().union(*(codes(s) for s in paper["students"]))


def test_duplicate_roster_student_is_reported_without_creating_two_students():
    sources = fixture(diagram=False)
    sources["rubrics"][0]["exam_roster"]["students"].append({"student_id": "S1"})
    paper = reconstruct(sources)
    assert len(paper["students"]) == 2
    assert "duplicate_roster_student" in codes(paper)
    assert paper["validation"]["status"] == "incomplete"


def test_explicit_duplicate_roster_ids_also_mark_affected_student_incomplete():
    sources = fixture(diagram=False)
    sources["rubrics"][0]["exam_roster"]["duplicate_roster_ids"] = ["S1"]
    paper = reconstruct(sources)
    assert "duplicate_roster_student" in codes(paper["students"][0])
    assert paper["students"][0]["status"] == "incomplete"


def test_string_objectid_reference_and_numeric_question_number_match_exactly():
    from bson import ObjectId
    from app.db.repository import load_exam_paper_sources
    sources = fixture(diagram=False)
    oid = ObjectId("6ad1d3d7b344e85db5f5f07a")
    sources["rubrics"][0]["_id"] = oid
    for sub in sources["submissions"]:
        sub["rubric_ref"] = str(oid)
        sub["evaluation"]["results"][0]["q_no"] = "1"
    loaded = immediate(load_exam_paper_sources(ReadOnlyDatabase(sources), "EXAM-2025-S1-Apr"))
    paper = reconstruct(loaded)
    assert all(s["status"] == "complete" for s in paper["students"])


def test_two_diagram_guidelines_never_get_assigned_to_one_slot_by_order():
    sources = fixture()
    another = deepcopy(sources["diagram_marking"][0]); another["_id"] = "guide-2"
    sources["diagram_marking"].append(another)
    sources["diagram_evaluations"][1]["guideline_object_id"] = "guide-2"
    sources["diagram_evaluations"][1]["evaluation_result"]["guideline_object_id"] = "guide-2"
    paper = reconstruct(sources)
    assert len(paper["unresolvedDiagramQuestions"]) == 2
    assert all(q["questionNumber"] is None for q in paper["unresolvedDiagramQuestions"])
    assert all(len(s["answers"]) == 4 for s in paper["students"])


def cli_module(monkeypatch, sources):
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("reconstruction_cli", Path(__file__).parents[1] / "scripts" / "reconstruct_exam_paper.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    def run(coroutine):
        coroutine.close()
        return reconstruct(sources)
    monkeypatch.setattr(module.asyncio, "run", run)
    return module


def test_cli_default_is_private_and_incomplete_exit_is_two(monkeypatch, capsys):
    import sys
    module = cli_module(monkeypatch, fixture(students=("PRIVATE-STUDENT",)))
    monkeypatch.setattr(sys, "argv", ["reconstruct_exam_paper.py", "EXAM-2025-S1-Apr"])
    assert module.main() == 2
    output = capsys.readouterr().out
    assert "PRIVATE-STUDENT" not in output
    assert '"studentCount": 1' in output


def test_cli_complete_exit_and_explicit_full_export(monkeypatch, capsys):
    import sys
    module = cli_module(monkeypatch, fixture(diagram=False, students=("PRIVATE-STUDENT",)))
    monkeypatch.setattr(sys, "argv", ["reconstruct_exam_paper.py", "EXAM-2025-S1-Apr", "--include-student-data"])
    assert module.main() == 0
    output = capsys.readouterr().out
    assert "PRIVATE-STUDENT" in output
    assert "saved_grading_excerpt" in output


def test_cli_connection_errors_never_print_exception_credentials(monkeypatch, capsys):
    import sys
    from pymongo.errors import ConnectionFailure
    module = cli_module(monkeypatch, fixture())
    def fail(coroutine):
        coroutine.close()
        raise ConnectionFailure("mongodb://PRIVATE-USER:PRIVATE-SECRET@host")
    monkeypatch.setattr(module.asyncio, "run", fail)
    monkeypatch.setattr(sys, "argv", ["reconstruct_exam_paper.py", "EXAM-2025-S1-Apr"])
    assert module.main() == 1
    output = capsys.readouterr()
    assert "PRIVATE" not in output.err
    assert "ConnectionFailure" in output.err


def test_cli_existing_output_is_never_overwritten(monkeypatch, capsys):
    import sys
    from pathlib import Path
    module = cli_module(monkeypatch, fixture())
    def exists(*args, **kwargs):
        raise FileExistsError("sensitive-file-name")
    monkeypatch.setattr(Path, "open", exists)
    monkeypatch.setattr(sys, "argv", ["reconstruct_exam_paper.py", "EXAM-2025-S1-Apr", "--output", "existing.json"])
    assert module.main() == 1
    assert "sensitive-file-name" not in capsys.readouterr().err


@pytest.mark.parametrize("value", [True, 1, "S1"])
def test_malformed_duplicate_roster_list_is_reported(value):
    sources = fixture(diagram=False)
    sources["rubrics"][0]["exam_roster"]["duplicate_roster_ids"] = value
    assert "invalid_roster" in codes(reconstruct(sources))


def test_unverified_numeric_rubric_ids_are_not_coerced_to_string_references():
    sources = fixture(diagram=False)
    sources["rubrics"][0]["_id"] = 1
    for submission in sources["submissions"]:
        submission["rubric_ref"] = "1"
    paper = reconstruct(sources)
    assert paper["validation"]["status"] == "incomplete"
    assert all(not s["answers"] for s in paper["students"])


def test_combined_grade_adds_both_rubrics_and_keeps_students_separate():
    sources = fixture(essays=5)
    maxima = [10, 7, 6, 6, 6]
    awards = [10, 7, 5.5, 6, 6]
    for q, maximum in zip(sources["rubrics"][0]["questions"], maxima):
        q["max_marks"] = maximum
        q["criteria"][0]["marks"] = maximum
    for submission in sources["submissions"]:
        for row, score in zip(submission["evaluation"]["results"], awards):
            row["score"] = score
            row["criteria_breakdown"][0]["awarded_marks"] = score
        submission["evaluation"].update(total_score=34.5, max_score=35)
    sources["diagram_evaluations"][0]["agent_marks"] = 19
    sources["diagram_evaluations"][0]["evaluation_result"].update(agent_marks=19)
    grade = sources["diagram_evaluations"][0]["evaluation_result"]["agent_grading"]
    grade.update(agent_marks=19)
    grade["criterion_results"][0]["marks"] = 19
    paper = reconstruct(sources)
    assert paper["grading"]["maximumMarks"] == 55
    first, second = [s["grading"] for s in paper["students"]]
    assert first["status"] == "complete"
    assert first["awardedMarks"] == 53.5
    assert first["maximumMarks"] == 55
    assert first["percentage"] == 97.27
    assert first["components"]["essay"]["maximumMarks"] == 35
    assert first["components"]["diagram"]["maximumMarks"] == 20
    assert second["awardedMarks"] == 46.5
    assert paper["validation"]["questionPaperStatus"] == "incomplete"  # missing prompt does not erase saved grades


@pytest.mark.parametrize("missing", ["essay", "diagram"])
def test_combined_grade_is_pending_instead_of_zero_when_evaluation_missing(missing):
    sources = fixture(essays=5)
    if missing == "essay":
        sources["submissions"][0].update(status="processing", evaluation=None)
    else:
        sources["diagram_evaluations"] = sources["diagram_evaluations"][1:]
    grade = reconstruct(sources)["students"][0]["grading"]
    assert grade["status"] == "pending"
    assert grade["maximumMarks"] == 45
    assert grade["components"][missing]["awardedMarks"] is None
    assert grade["awardedMarks"] is None
    assert grade["percentage"] is None


@pytest.mark.parametrize("invalid", ["duplicate_essay", "duplicate_diagram", "excess_marks", "wrong_total", "missing_row"])
def test_combined_grade_never_adds_ambiguous_or_invalid_marks(invalid):
    sources = fixture(essays=5)
    if invalid == "duplicate_essay":
        sources["submissions"].append(deepcopy(sources["submissions"][0]))
    elif invalid == "duplicate_diagram":
        sources["diagram_evaluations"].append(deepcopy(sources["diagram_evaluations"][0]))
    elif invalid == "excess_marks":
        sources["submissions"][0]["evaluation"]["results"][0]["score"] = 99
    elif invalid == "wrong_total":
        sources["submissions"][0]["evaluation"]["total_score"] = 99
    else:
        sources["submissions"][0]["evaluation"]["results"].pop()
    grade = reconstruct(sources)["students"][0]["grading"]
    assert grade["status"] != "complete"
    assert grade["awardedMarks"] is None
    assert grade["percentage"] is None


def test_combined_numeric_grade_with_criterion_conflict_is_explicitly_for_review():
    sources = fixture(essays=5)
    sources["submissions"][0]["evaluation"]["results"][0]["criteria_breakdown"][0]["point"] = "Wrong criterion"
    grade = reconstruct(sources)["students"][0]["grading"]
    assert grade["awardedMarks"] == 27
    assert grade["percentage"] == 60
    assert grade["status"] == "needs_review"


def test_combined_grade_does_not_choose_between_multiple_diagram_rubrics():
    sources = fixture(essays=5)
    other = deepcopy(sources["diagram_marking"][0]); other["_id"] = "another-guide"
    sources["diagram_marking"].append(other)
    sources["diagram_evaluations"][1]["guideline_object_id"] = "another-guide"
    paper = reconstruct(sources)
    assert paper["grading"]["maximumMarks"] is None
    assert all(s["grading"]["status"] != "complete" for s in paper["students"])


def test_quarantined_attempt_with_unsupported_id_cannot_leave_a_final_grade():
    sources = fixture(essays=5)
    duplicate = deepcopy(sources["submissions"][0]); duplicate["_id"] = 123
    sources["submissions"].append(duplicate)
    grade = reconstruct(sources)["students"][0]["grading"]
    assert grade["status"] == "needs_review"
    assert grade["awardedMarks"] is None


def test_unexpected_diagram_component_prevents_final_grade_for_essay_only_exam():
    sources = fixture(essays=5)
    sources["examkeys"][0]["examStructure"].pop()
    assert all(s["grading"]["status"] == "needs_review" for s in reconstruct(sources)["students"])

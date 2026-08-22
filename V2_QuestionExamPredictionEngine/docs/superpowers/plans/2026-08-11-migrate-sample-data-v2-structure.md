# Migrate Sample Data to v2 Structure — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reshape the checked-in IT2040 sample documents (`app/sample_data/`) to the v2 structure (courses as `code`/`name`/`description`; rubric + submissions gaining `subject_name`, `year`, `month`, `semester`, `paper_key`, `exam_roster`, `lecturer_note`, per-criterion `reason`; criteria breakdown using `{point, awarded_marks, reason}` instead of `{point, marks, earned}`) and update the pipeline code + tests that read them.

**Architecture:** A one-time migration script (`migrate_sample_v2.py`) reads the current sample JSONs and rewrites them in the v2 shape, preserving every existing value (question text, criteria points, marks, scores, transcripts, grading/RAG metadata). Pipeline code (`loader.py`, `run_sample.py`, `student_data.py`) is updated to consume the new shape; existing tests are updated and a structure-invariant test suite guards the contract. The analytics consumers (`transformer.py`, `mastery.py`, `student.py`, `schemas/catalog.py`) read the *normalized* `student_analytics` documents and are unaffected.

**Tech Stack:** Python, pytest, JSON, MongoDB (motor), pydantic — same as the existing repo.

## Global Constraints

- Keep the IT2040 Database Management Systems subject and ALL content unchanged (question text, criteria point strings, criterion marks, scores, `raw_ocr_transcript`, grading/RAG metadata). Only the *structure* changes.
- `criteria_breakdown` items must be `{point, awarded_marks, reason}` — never contain `marks` or `earned`.
- Every sample submission must keep `status: "graded"`.
- Courses are keyed by `code`; rubric and submissions still carry `subject_code` + `session_name` for repository lookups.
- All sample JSONs must remain valid JSON parseable by `run_sample.load_raw_sample_documents()`.
- Preserve existing test expectations: 11 rubric questions; Q01 `score == 6.0`, `max_score == 8.0`, first criterion `awarded_marks == 2.5`; exactly 5 submissions.
- Run all commands from the repository root (`V2_QuestionExamPredictionEngine`).

---

### Task 1: Add sample-data structure invariant tests (fail on current data)

**Files:**
- Create: `tests/test_sample_data_structure.py`

**Interfaces:**
- Consumes: `run_sample.load_raw_sample_documents()` (root module, already imported by `tests/test_run_sample.py`).
- Produces: a failing test contract that the v2 JSON data must satisfy; later tasks use it to verify the regenerated data.

- [ ] **Step 1: Write the failing test**

```python
from run_sample import load_raw_sample_documents


def test_courses_have_v2_shape():
    courses, _, _ = load_raw_sample_documents()
    assert len(courses) == 1
    course = courses[0]
    assert course["code"] == "IT2040"
    assert course["name"]
    assert course["description"]


def test_rubric_has_v2_metadata():
    _, rubrics, _ = load_raw_sample_documents()
    rubric = rubrics[0]
    assert rubric["subject_code"] == "IT2040"
    assert rubric["subject_name"]
    assert rubric["year"] == 2021
    assert rubric["month"]
    assert rubric["semester"]
    assert rubric["session_name"]
    assert len(rubric["exam_roster"]) == 5


def test_submissions_have_v2_shape_and_graded_status():
    _, _, submissions = load_raw_sample_documents()
    assert len(submissions) == 5
    for sub in submissions:
        assert sub["status"] == "graded"
        assert sub["paper_key"]
        assert sub["subject_code"] == "IT2040"
        assert sub["subject_name"]
        assert sub["year"] == 2021
        assert sub["month"]
        assert sub["semester"]
        assert sub["session_name"]
        assert "lecturer_note" in sub
        for result in sub["evaluation"]["results"]:
            for criterion in result["criteria_breakdown"]:
                assert "earned" not in criterion
                assert "marks" not in criterion
                assert "awarded_marks" in criterion
                assert criterion["awarded_marks"] >= 0
                assert "reason" in criterion
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sample_data_structure.py -v`
Expected: FAIL — `course["code"]` raises `KeyError` (current `courses.json` is rubric-shaped and has no `code` key).

- [ ] **Step 3: Commit**

```bash
git add tests/test_sample_data_structure.py
git commit -m "test: assert v2 sample-data structure invariants"
```

---

### Task 2: Add migration script and regenerate the sample JSONs

**Files:**
- Create: `migrate_sample_v2.py`
- Rewrite: `app/sample_data/courses.json`
- Rewrite: `app/sample_data/rubricCollection.json`
- Rewrite: `app/sample_data/submission.json`
- Rewrite: `app/sample_data/submission_2.json`
- Rewrite: `app/sample_data/submission_3.json`
- Rewrite: `app/sample_data/submission_4.json`
- Rewrite: `app/sample_data/submission_5.json`

**Interfaces:**
- Consumes: the current (pre-migration) sample JSONs under `app/sample_data/`.
- Produces: the v2 JSON files that make Task 1's tests pass, plus a repeatable migration tool. Re-running the script on already-migrated files is a no-op.

- [ ] **Step 1: Write the migration script**

```python
"""Regenerate the checked-in sample documents in the v2 data structure.

Reads the current JSON files under app/sample_data/ and rewrites them to the
v2 shape (criteria as {point, awarded_marks, reason}, paper_key, subject
metadata, exam roster, lecturer_note) while preserving every existing value.
Re-running is a no-op for already-migrated files.

Run from the repository root:
    python migrate_sample_v2.py
"""

import json
from pathlib import Path

SAMPLE_DIR = Path(__file__).resolve().parent / "app" / "sample_data"

SUBJECT_CODE = "IT2040"
SUBJECT_NAME = "Database Management Systems"
YEAR = 2021
MONTH = "December"
SEMESTER = "Semester 1"
SESSION_NAME = "Final Examination 2021"
PAPER_KEY = "IT2040-FE-2021"
COURSE_DESCRIPTION = (
    "Database design and implementation: ER/EER modeling, relational schema "
    "design and normalization, SQL and T-SQL, transaction management, "
    "concurrency control, and SQL Server user/role administration."
)


def _load(name: str) -> dict:
    with open(SAMPLE_DIR / name, encoding="utf-8") as fh:
        return json.load(fh)


def _save(name: str, document: dict) -> None:
    with open(SAMPLE_DIR / name, "w", encoding="utf-8") as fh:
        json.dump(document, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def _reason(awarded: float, max_marks: float) -> str:
    if awarded <= 0:
        return "No marks awarded"
    if awarded >= max_marks:
        return "Full marks"
    return "Partial credit"


def _reshape_criterion(criterion: dict) -> dict:
    if "awarded_marks" in criterion and "reason" in criterion:
        return criterion
    awarded = float(criterion.pop("awarded_marks", criterion.pop("earned", 0.0)))
    max_marks = float(criterion.pop("marks", awarded))
    criterion["awarded_marks"] = awarded
    criterion["reason"] = _reason(awarded, max_marks)
    return criterion


def course_v2(existing: dict) -> dict:
    return {
        "_id": existing.get("_id", "ObjectId('...')"),
        "code": existing.get("code", existing.get("subject_code", SUBJECT_CODE)),
        "name": existing.get("name", SUBJECT_NAME),
        "description": existing.get("description", COURSE_DESCRIPTION),
    }


def rubric_v2(existing: dict, roster: list[str]) -> dict:
    document = {k: v for k, v in existing.items() if k != "_id"}
    document["_id"] = existing.get("_id", "ObjectId('...')")
    document["subject_code"] = SUBJECT_CODE
    document["subject_name"] = SUBJECT_NAME
    document["year"] = existing.get("year", YEAR)
    document["month"] = existing.get("month", MONTH)
    document["semester"] = existing.get("semester", SEMESTER)
    document["session_name"] = existing.get("session_name", SESSION_NAME)
    document["exam_roster"] = sorted(roster)
    return document


def submission_v2(existing: dict) -> dict:
    document = {k: v for k, v in existing.items() if k != "_id"}
    document["_id"] = existing.get("_id", "ObjectId('...')")
    document["rubric_ref"] = existing.get("rubric_ref", "ObjectId('...')")
    document["paper_key"] = existing.get("paper_key", PAPER_KEY)
    document["subject_code"] = SUBJECT_CODE
    document["subject_name"] = SUBJECT_NAME
    document["year"] = existing.get("year", YEAR)
    document["month"] = existing.get("month", MONTH)
    document["semester"] = existing.get("semester", SEMESTER)
    document["session_name"] = existing.get("session_name", SESSION_NAME)
    if "lecturer_note" not in document:
        document["lecturer_note"] = ""
    evaluation = document.setdefault("evaluation", {})
    for result in evaluation.get("results", []):
        result["criteria_breakdown"] = [
            _reshape_criterion(c) for c in result.get("criteria_breakdown", [])
        ]
    return document


def main() -> None:
    paths = sorted(SAMPLE_DIR.glob("submission*.json"))
    submissions = [
        json.loads(path.read_text(encoding="utf-8")) for path in paths
    ]
    roster = [sub["student_id"] for sub in submissions]
    _save("courses.json", course_v2(_load("courses.json")))
    _save("rubricCollection.json", rubric_v2(_load("rubricCollection.json"), roster))
    for path in paths:
        _save(path.name, submission_v2(json.loads(path.read_text(encoding="utf-8"))))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the script**

Run: `python migrate_sample_v2.py`
Expected: all 7 JSON files rewritten; no errors.

- [ ] **Step 3: Verify the v2 structure and preserved values**

Run: `python -m pytest tests/test_sample_data_structure.py tests/test_student_data_ingestion.py::test_normalize_submission_joins_questions_and_criteria -v`
Expected: PASS. The structure tests pass AND the pre-existing real-data ingestion test still passes (11 questions; Q01 `score == 6.0`, `max_score == 8.0`, first criterion `awarded_marks == 2.5`), proving content was preserved.

- [ ] **Step 4: Spot-check a diff**

Run: `git diff --stat app/sample_data/`
Expected: `courses.json` collapses from rubric-shaped to 7 lines; `submission*.json` and `rubricCollection.json` change but the criteria `point` strings, `score` values, `raw_ocr_transcript` text, and `max_marks_per_question` arrays are unchanged (only `earned`/`marks` became `awarded_marks`/`reason`, and the new metadata keys were added).

- [ ] **Step 5: Commit**

```bash
git add migrate_sample_v2.py app/sample_data/
git commit -m "refactor: reshape sample data to v2 structure"
```

---

### Task 3: Update the sample-data loader for the v2 structure

**Files:**
- Modify: `app/sample_data/loader.py` (all of `parse_submission`, `course_settings`, `load_real`; the `year` line in `parse_paper`)
- Create: `tests/test_loader.py`

**Interfaces:**
- Consumes: v2 JSON files from Task 2 (`courses.json`, `rubricCollection.json`, `submission*.json`).
- Produces:
  - `parse_submission(sub: dict, exam_id: str, course_code: str, rubric_questions: list[dict]) -> list[dict]` — rows with `criteria_breakdown` items `{criterion, awarded_marks, max_marks, met}` (max marks now sourced from the rubric criteria, since v2 breakdowns carry no `marks`).
  - `course_settings(course: dict) -> dict` — reads `code`/`name` from the course document (was: hardcoded DBMS name).
  - `load_real() -> tuple[dict, list[dict], list[dict]]` — loads `courses.json` and passes rubric questions into `parse_submission`.
  - `parse_paper(rubric: dict) -> dict` — `year` prefers `rubric["year"]`.

- [ ] **Step 1: Write the failing tests**

```python
from app.sample_data.loader import _load, load_real, parse_submission


def test_parse_submission_reads_awarded_marks_and_rubric_maxima():
    rubric = _load("rubricCollection.json")
    sub = _load("submission.json")
    rows = parse_submission(
        sub, "IT2040-final-examination-2021", "IT2040", rubric["questions"]
    )
    q01 = next(row for row in rows if row["question_number"] == "01")
    assert q01["awarded_marks"] == 6.0
    assert q01["max_marks"] == 8.0
    first = q01["criteria_breakdown"][0]
    assert first["awarded_marks"] == 2.5
    assert first["max_marks"] == 3.0
    assert first["met"] is False


def test_load_real_builds_course_from_courses_json():
    course, papers, submissions = load_real()
    assert course["course_code"] == "IT2040"
    assert course["course_name"] == "Database Management Systems"
    assert len(papers) == 1
    assert papers[0]["year"] == 2021
    assert len(submissions) >= 5
    assert all(row["max_marks"] > 0 for row in submissions)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_loader.py -v`
Expected: FAIL. `parse_submission` currently reads `c.get("earned", 0.0)` and `c.get("marks", earned)` — with v2 data both default to 0, so `q01["criteria_breakdown"][0]["awarded_marks"] == 0.0` and `max_marks == 0.0`. `load_real` uses the old `course_settings(course_code)` signature.

- [ ] **Step 3: Implement the v2 loader**

Replace `parse_submission`, `course_settings`, and `load_real` in `app/sample_data/loader.py` with:

```python
def parse_submission(
    sub: dict, exam_id: str, course_code: str, rubric_questions: list[dict]
) -> list[dict]:
    student_key = sub.get("student_id") or sub.get("student_key") or "student-1"
    max_by_q = {
        str(m["question_no"]).zfill(2): float(m["max_marks"])
        for m in sub.get("max_marks_per_question", [])
    }
    rubric_by_qno = {
        str(q["question_no"]).zfill(2): q for q in rubric_questions
    }
    results = sub["evaluation"]["results"] if "evaluation" in sub else sub.get("results", [])
    rows = []
    for r in results:
        q_no = str(r["q_no"]).zfill(2)
        rubric_q = rubric_by_qno.get(q_no, {})
        rubric_criteria = rubric_q.get("criteria", [])
        evaluated = r.get("criteria_breakdown", [])
        criteria = []
        for position, rubric_criterion in enumerate(rubric_criteria):
            point = rubric_criterion.get("point", "")
            matched = next(
                (c for c in evaluated if c.get("point") == point), None
            )
            if matched is None and position < len(evaluated):
                matched = evaluated[position]
            awarded = (
                float(matched.get("awarded_marks", matched.get("earned", 0.0)))
                if matched
                else 0.0
            )
            max_marks = float(rubric_criterion.get("marks", 0.0))
            criteria.append(
                {
                    "criterion": point,
                    "awarded_marks": awarded,
                    "max_marks": max_marks,
                    "met": awarded >= max_marks,
                }
            )
        rows.append(
            {
                "exam_id": exam_id,
                "course_code": course_code,
                "student_key": f"{course_code}-{student_key}",
                "question_number": q_no,
                "part": "a",
                "awarded_marks": float(r["score"]),
                "max_marks": max_by_q.get(q_no, 0.0),
                "answer_text": "",
                "feedback": r.get("feedback", ""),
                "criteria_breakdown": criteria,
            }
        )
    return rows
```

```python
def course_settings(course: dict) -> dict:
    course_code = (
        course.get("code") or course.get("subject_code") or "IT2040"
    )
    course_name = (
        course.get("name")
        or course.get("course_name")
        or "Database Management Systems"
    )
    return {
        "course_code": course_code,
        "course_name": course_name,
        "settings": {
            "pass_threshold": 0.5,
            "min_students": 3,
            "min_attempts": 1,
            "topic_importance": {},
            "blueprint_targets": {},
        },
    }
```

```python
def load_real() -> tuple[dict, list[dict], list[dict]]:
    course_document = _load("courses.json")
    rubric = _load("rubricCollection.json")

    paper = parse_paper(rubric)
    course = course_settings(course_document)

    submissions = []
    for sub_path in sorted(SAMPLE_DIR.glob("submission*.json")):
        sub = json.loads(sub_path.read_text(encoding="utf-8"))
        submissions.extend(
            parse_submission(
                sub, paper["exam_id"], paper["course_code"], rubric["questions"]
            )
        )
    return course, [paper], submissions
```

Also change the `year` line in `parse_paper` from:

```python
"year": 2021 if "2021" in rubric.get("session_name", "") else 0,
```

to:

```python
"year": rubric.get("year")
        or (2021 if "2021" in rubric.get("session_name", "") else 0),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_loader.py tests/test_student_data_ingestion.py -v`
Expected: PASS (new loader tests + all ingestion tests, including the real-data test).

- [ ] **Step 5: Commit**

```bash
git add app/sample_data/loader.py tests/test_loader.py
git commit -m "refactor: load v2 sample data (awarded_marks, course from courses.json)"
```

---

### Task 4: Prefer `awarded_marks` in student-data normalization and update its v2-shaped fixtures

**Files:**
- Modify: `app/ingestion/student_data.py:73`
- Modify: `tests/test_student_data_ingestion.py` (`minimal_submission`, parametrize case)

**Interfaces:**
- Consumes: v2 submission documents (criteria breakdown `{point, awarded_marks, reason}`).
- Produces: `normalize_student_submission` reads `awarded_marks` preferentially; the ingestion tests exercise only v2-shaped criteria.

- [ ] **Step 1: Write the failing test (update fixtures to v2)**

In `tests/test_student_data_ingestion.py`, change `minimal_submission` so its criteria breakdown is v2-shaped (no `marks`/`earned`):

```python
def minimal_submission(q_no: str, score: float, max_score: float) -> dict:
    return {
        "rubric_ref": "rubric-1",
        "session_name": "Final Examination",
        "subject_code": "IT2040",
        "student_id": "IT21001234",
        "evaluation": {
            "results": [
                {
                    "q_no": q_no,
                    "score": score,
                    "criteria_breakdown": [
                        {"point": "Correct answer", "awarded_marks": score}
                    ],
                }
            ]
        },
    }
```

And change the parametrize case at line 103 from `[{"point": "Correct answer", "marks": 5, "earned": 5}]` to `[{"point": "Correct answer", "awarded_marks": 5}]`.

- [ ] **Step 2: Run tests to verify the fixture change is handled**

Run: `python -m pytest tests/test_student_data_ingestion.py -v`
Expected: The v2-shaped fixtures already pass because `_criteria_for_question` falls back to `awarded_marks`. This step locks the v2 shape into the tests.

- [ ] **Step 3: Flip the fallback order so `awarded_marks` is canonical**

In `app/ingestion/student_data.py:73`, change:

```python
matched.get("earned", matched.get("awarded_marks", 0)),
```

to:

```python
matched.get("awarded_marks", matched.get("earned", 0)),
```

- [ ] **Step 4: Run tests to verify they still pass**

Run: `python -m pytest tests/test_student_data_ingestion.py tests/test_student_pipeline.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/ingestion/student_data.py tests/test_student_data_ingestion.py
git commit -m "refactor: prefer awarded_marks in student-data normalization"
```

---

### Task 5: Seed courses by `code` in `run_sample.py`

**Files:**
- Modify: `run_sample.py:33-39`
- Modify: `tests/test_run_sample.py` (`_sample_identity`, `_clean_sample_documents`, the courses count assertion in `test_seed_raw_samples_idempotently_upserts_sample_documents`)

**Interfaces:**
- Consumes: v2 `courses.json` (has `code`, no `subject_code`).
- Produces: `seed_raw_samples` upserts the course doc keyed on `code` (or legacy `subject_code`), so the seed is idempotent and queryable by the new shape.

- [ ] **Step 1: Write the failing test**

In `tests/test_run_sample.py`, update `_sample_identity` to read `code` first:

```python
def _sample_identity():
    courses, rubrics, submissions = load_raw_sample_documents()
    return {
        "course_codes": [
            course.get("code") or course.get("subject_code") or "IT2040"
            for course in courses
        ],
        "sessions": [rubric["session_name"] for rubric in rubrics],
        "student_ids": [submission["student_id"] for submission in submissions],
    }
```

And update `_clean_sample_documents` so it also deletes course documents keyed by `code`:

```python
await db["courses"].delete_many(
    {
        "$or": [
            {"subject_code": {"$in": identity["course_codes"]}},
            {"code": {"$in": identity["course_codes"]}},
        ]
    }
)
```

And update the courses count assertion in `test_seed_raw_samples_idempotently_upserts_sample_documents`:

```python
assert await test_db["courses"].count_documents(
    {
        "$or": [
            {"subject_code": {"$in": identity["course_codes"]}},
            {"code": {"$in": identity["course_codes"]}},
        ]
    }
) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_run_sample.py::test_seed_raw_samples_idempotently_upserts_sample_documents -v`
Expected: FAIL. `seed_raw_samples` upserts by `{"subject_code": "IT2040"}` (the v2 course doc has no `subject_code`), and the cleanup filter never matches the seeded `code`-keyed document.

- [ ] **Step 3: Implement code-keyed seeding**

In `run_sample.py`, replace the courses upsert loop (lines 33-39) with:

```python
for course in courses:
    course_document = {key: value for key, value in course.items() if key != "_id"}
    course_key = course.get("code") or course.get("subject_code") or "IT2040"
    await db["courses"].replace_one(
        {"$or": [{"code": course_key}, {"subject_code": course_key}]},
        course_document,
        upsert=True,
    )
```

- [ ] **Step 4: Run the full run_sample test module**

Run: `python -m pytest tests/test_run_sample.py -v`
Expected: PASS (all seed + materialize + main-flow tests).

- [ ] **Step 5: Commit**

```bash
git add run_sample.py tests/test_run_sample.py
git commit -m "refactor: seed sample courses by code"
```

---

### Task 6: Update remaining v1-shaped test fixtures

**Files:**
- Modify: `tests/test_student_pipeline.py:50-66` (two `criteria_breakdown` blocks)

**Interfaces:**
- Consumes: v2 submission shape.
- Produces: all tests in the repo exercise only the v2 criteria shape.

- [ ] **Step 1: Update the synthetic submissions**

In `tests/test_student_pipeline.py`, change both `criteria_breakdown` blocks (lines 50-56 and 61-67) from:

```python
{
    "point": "Explains the concept",
    "marks": 5,
    "earned": second_score,
}
```

and

```python
{
    "point": "Uses the correct query",
    "marks": 5,
    "earned": first_score,
}
```

to:

```python
{
    "point": "Explains the concept",
    "awarded_marks": second_score,
}
```

and

```python
{
    "point": "Uses the correct query",
    "awarded_marks": first_score,
}
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `python -m pytest tests/test_student_pipeline.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_student_pipeline.py
git commit -m "test: use v2 criteria shape in pipeline fixtures"
```

---

### Task 7: Full verification

**Files:**
- None (verification only; only touch files if a leftover v1 reference is found).

**Interfaces:**
- Consumes: the completed migration (Tasks 1-6).
- Produces: confidence that the whole suite passes and no v1-shaped references remain.

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest tests/ -q`
Expected: PASS. Pay special attention to `tests/test_run_sample.py`, `tests/test_student_data_ingestion.py`, `tests/test_student_pipeline.py`, `tests/test_sample_data_structure.py`, `tests/test_loader.py`, and `tests/test_repository.py`.

- [ ] **Step 2: Grep for leftover v1 references**

Run:
```
rg -n "earned|criteria_breakdown" --glob "!*.pyc" --glob "!.venv/**" --glob "!tests/.pytest_cache/**"
```
Expected: only the intentional `matched.get("awarded_marks", matched.get("earned", 0))` fallback in `app/ingestion/student_data.py` and any non-sample references. No sample JSON or test fixture should still use `earned`/`marks` in `criteria_breakdown`.

- [ ] **Step 3: Confirm the sample data still round-trips through the repository lookup paths**

Run: `python -m pytest tests/test_run_sample.py tests/test_repository.py -v`
Expected: PASS (seeded docs are found by `find_course_for_submission` via `code` and by `find_rubric_for_submission` via `subject_code` + `session_name` fallback).

- [ ] **Step 4: Optional live smoke test (requires Mongo + LLM backend)**

Run: `python run_sample.py dbms_analytics_test`
Expected: seeds `courses=1 rubrics=1 submissions=5`, then `saved student_ids: ...` with `failures: 0` and `student_analytics count=5`. Skip this step if no Mongo/Ollama backend is reachable — the seeded test suite covers the pipeline with monkeypatched LLM calls.

- [ ] **Step 5: Commit any leftover fixes**

```bash
git add -A
git commit -m "chore: finish v2 sample-data migration cleanup"
```

---

## Self-Review Notes

**Spec coverage:**
- v2 course shape (`code`/`name`/`description`) → Tasks 1, 2, 3, 5.
- v2 rubric/submission metadata (`subject_name`, `year`, `month`, `semester`, `paper_key`, `exam_roster`, `lecturer_note`) → Tasks 1, 2.
- criteria `{point, awarded_marks, reason}` (no `marks`/`earned`) → Tasks 1, 2, 4, 6.
- Loader consumption of v2 data → Task 3.
- Seeding by `code` → Task 5.
- Test fixtures updated to v2 → Tasks 1, 4, 6.
- Content preservation (11 questions, Q01 6.0/8.0/2.5, 5 submissions, transcripts) → Task 2 Step 3, Task 3 Step 4.
- Full-suite verification → Task 7.

**Placeholder scan:** No "TBD"/"implement later" placeholders; every code step carries the full implementation. The only data authored fresh (rather than preserved) is the per-criterion `reason` string, generated deterministically from the awarded/max marks in the migration script.

**Type consistency:** `parse_submission` signature is `(sub, exam_id, course_code, rubric_questions)` and is only called from `load_real`; `course_settings(course: dict)` is only called from `load_real`; `load_real()` keeps the existing 3-tuple return type. `criteria_breakdown` items stay `{criterion, awarded_marks, max_marks, met}`, matching `schemas/catalog.py:CriteriaEvidence` and the `met` reads in `analytics/mastery.py:57`.

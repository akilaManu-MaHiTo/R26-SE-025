# Match Codebase to Reorganized Sample Data Collections — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the loaders, migration script, and tests consume the reorganized sample data (3 folders mirroring the `courses`, `rubricCollection`, `submissions` MongoDB collections) and the new submission/rubric shapes, with Extended JSON decoded to native BSON types.

**Architecture:** `run_sample.py` and `app/sample_data/loader.py` are the two consumers of the raw sample JSON. Both read the new folder layout and decode MongoDB Extended JSON (`$oid` -> `ObjectId`, `$date` -> `datetime`) via `bson.json_util.loads`. `seed_raw_samples` preserves original `_id` values so a submission's `rubric_ref` resolves to the seeded rubric. `migrate_sample_v2.py` is reworked to the new layout as an idempotent no-op. Sample-data-dependent tests are updated to the new expected values.

**Tech Stack:** Python, MongoDB Extended JSON (`bson.json_util`), pytest (asyncio mode auto).

## Global Constraints

- Working directory for all commands: `V2_QuestionExamPredictionEngine` (repo root of the engine).
- Python: use the checked-in virtualenv: `.venv\Scripts\python.exe`.
- Do NOT decode Extended JSON inside `migrate_sample_v2.py` — it rewrites JSON with plain `json.dump`, and `ObjectId`/`datetime` are not JSON-serializable.
- Sample facts: 2 courses (SE3040, IT2040); rubric `subject_code=IT2040`, `year=2022`, `session_name="Final Examination"`, `exam_roster: null`, 4 questions, 20 marks each; 5 graded submissions (`IT22145976`, `IT22145980`, `IT22145984`, `IT22145988`, `IT22145992`), first submission Q01 `score=11.0`, `max_marks=20.0`, first criterion `awarded_marks=2.0`, `max_marks=4.0`.
- Spec: `docs/superpowers/specs/2026-08-13-match-sample-data-collections-design.md`.

---

### Task 1: Update `app/sample_data/loader.py` for the new layout

**Files:**
- Modify: `app/sample_data/loader.py` (`_load`, `parse_paper` year line, `load_real`)
- Test: `tests/test_loader.py`
- Test: `tests/test_student_data_ingestion.py` (only `test_normalize_submission_joins_questions_and_criteria`)

**Interfaces:**
- Consumes: new folder layout under `app/sample_data/`.
- Produces: `load_real() -> tuple[dict, list[dict], list[dict]]` returning the IT2040 course, one paper, and submission rows; `_load(name: str) -> object` decoding Extended JSON.

- [ ] **Step 1: Update `_load` to decode Extended JSON**

```python
from bson.json_util import loads

def _load(name: str) -> object:
    path = SAMPLE_DIR / name
    with open(path, encoding="utf-8") as fh:
        return loads(fh.read())
```

- [ ] **Step 2: Simplify the `parse_paper` year line**

Replace:

```python
        "year": rubric.get("year")
        or (2021 if "2021" in rubric.get("session_name", "") else 0),
```

with:

```python
        "year": rubric.get("year") or 0,
```

- [ ] **Step 3: Rewrite `load_real` for the folder layout**

Replace the body of `load_real` with:

```python
def load_real() -> tuple[dict, list[dict], list[dict]]:
    courses = _load("courses/courses.json")
    rubric = _load("rubricCollection/rubricCollection.json")

    paper = parse_paper(rubric)
    subject_code = paper["course_code"]
    course_document = next(
        (
            course
            for course in courses
            if (course.get("code") or course.get("subject_code")) == subject_code
        ),
        courses[0] if courses else {},
    )
    course = course_settings(course_document)

    submissions = []
    for sub_path in sorted((SAMPLE_DIR / "submissions").glob("submission*.json")):
        for sub in _load(f"submissions/{sub_path.name}"):
            submissions.extend(
                parse_submission(
                    sub, paper["exam_id"], paper["course_code"], rubric["questions"]
                )
            )
    return course, [paper], submissions
```

- [ ] **Step 4: Update `tests/test_loader.py`**

Replace the file contents with:

```python
from app.sample_data.loader import _load, load_real, parse_submission


def test_parse_submission_reads_awarded_marks_and_rubric_maxima():
    rubric = _load("rubricCollection/rubricCollection.json")
    sub = _load("submissions/submission.json")[0]
    rows = parse_submission(
        sub, "IT2040-Final Examination", "IT2040", rubric["questions"]
    )
    q01 = next(row for row in rows if row["question_number"] == "01")
    assert q01["awarded_marks"] == 11.0
    assert q01["max_marks"] == 20.0
    first = q01["criteria_breakdown"][0]
    assert first["awarded_marks"] == 2.0
    assert first["max_marks"] == 4.0
    assert first["met"] is False


def test_load_real_builds_course_from_courses_json():
    course, papers, submissions = load_real()
    assert course["course_code"] == "IT2040"
    assert course["course_name"] == "Database Management Systems"
    assert len(papers) == 1
    assert papers[0]["year"] == 2022
    assert len(submissions) >= 5
    assert all(row["max_marks"] > 0 for row in submissions)
```

- [ ] **Step 5: Update `tests/test_student_data_ingestion.py` (one test)**

Replace only `test_normalize_submission_joins_questions_and_criteria` with:

```python
def test_normalize_submission_joins_questions_and_criteria():
    rubric = _load("rubricCollection/rubricCollection.json")
    submission = _load("submissions/submission.json")[0]
    normalized = normalize_student_submission(
        {"course_code": "IT2040", "course_name": "Database Management Systems"},
        rubric,
        submission,
    )
    assert normalized.student_id == "IT22145976"
    assert normalized.course_code == "IT2040"
    assert normalized.course_name == "Database Management Systems"
    assert len(normalized.questions) == 4
    assert normalized.questions[0].question_no == "01"
    assert normalized.questions[0].score == 11.0
    assert normalized.questions[0].max_score == 20.0
    assert normalized.questions[0].criteria[0].awarded_marks == 2.0
```

- [ ] **Step 6: Run the affected tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_loader.py tests/test_student_data_ingestion.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/sample_data/loader.py tests/test_loader.py tests/test_student_data_ingestion.py
git commit -m "refactor: load sample data from collection folders with Extended JSON decoding"
```

---

### Task 2: Rework `migrate_sample_v2.py` for the new layout (idempotent no-op)

**Files:**
- Modify: `migrate_sample_v2.py` (module docstring, `COURSES_FILE`/`RUBRIC_FILE`/`SUBMISSIONS_DIR`, `rubric_v2`, `main`)
- Test: `tests/test_sample_data_structure.py`

**Interfaces:**
- Consumes: subfolder layout under `app/sample_data/`; plain JSON (no Extended JSON decode).
- Produces: `main() -> None` rewriting each collection file in place, byte-idempotent across runs.

- [ ] **Step 1: Add collection path constants and update `rubric_v2`**

After the `SAMPLE_DIR` line, add:

```python
COURSES_FILE = "courses/courses.json"
RUBRIC_FILE = "rubricCollection/rubricCollection.json"
SUBMISSIONS_DIR = "submissions"
```

Replace the `exam_roster` line in `rubric_v2`:

```python
    document["exam_roster"] = sorted(roster)
```

with:

```python
    if "exam_roster" not in existing:
        document["exam_roster"] = sorted(roster)
```

- [ ] **Step 2: Rewrite `main()`**

Replace the `main()` body with:

```python
def main() -> None:
    courses = _load(COURSES_FILE)
    rubric = _load(RUBRIC_FILE)
    submission_paths = sorted((SAMPLE_DIR / SUBMISSIONS_DIR).glob("submission*.json"))
    submissions = [
        sub
        for path in submission_paths
        for sub in json.loads(path.read_text(encoding="utf-8"))
    ]
    roster = [sub["student_id"] for sub in submissions]
    _save(COURSES_FILE, [course_v2(course) for course in courses])
    _save(RUBRIC_FILE, rubric_v2(rubric, roster))
    for path in submission_paths:
        _save(
            f"{SUBMISSIONS_DIR}/{path.name}",
            [
                submission_v2(sub)
                for sub in json.loads(path.read_text(encoding="utf-8"))
            ],
        )
```

- [ ] **Step 3: Update `tests/test_sample_data_structure.py`**

Replace the file contents with:

```python
import shutil
from pathlib import Path

import migrate_sample_v2
from run_sample import load_raw_sample_documents


def test_courses_have_v2_shape():
    courses, _, _ = load_raw_sample_documents()
    assert len(courses) == 2
    assert {course["code"] for course in courses} == {"SE3040", "IT2040"}
    assert all(
        course.get("code") and course.get("name") and course.get("description")
        for course in courses
    )


def test_rubric_has_v2_metadata():
    _, rubrics, _ = load_raw_sample_documents()
    rubric = rubrics[0]
    assert rubric["subject_code"] == "IT2040"
    assert rubric["subject_name"]
    assert rubric["year"] == 2022
    assert rubric["month"]
    assert rubric["semester"]
    assert rubric["session_name"] == "Final Examination"
    assert "exam_roster" in rubric
    assert len(rubric["questions"]) == 4


def test_submissions_have_v2_shape_and_graded_status():
    _, _, submissions = load_raw_sample_documents()
    assert len(submissions) == 5
    for sub in submissions:
        assert sub["status"] == "graded"
        assert sub["paper_key"]
        assert sub["subject_code"] == "IT2040"
        assert sub["subject_name"]
        assert sub["year"] == 2022
        assert sub["month"]
        assert sub["semester"]
        assert sub["session_name"] == "Final Examination"
        assert "lecturer_note" in sub
        for result in sub["evaluation"]["results"]:
            for criterion in result["criteria_breakdown"]:
                assert "earned" not in criterion
                assert "marks" not in criterion
                assert "point" in criterion
                assert "awarded_marks" in criterion
                assert criterion["awarded_marks"] >= 0
                assert "reason" in criterion


def test_migrate_sample_v2_is_idempotent(tmp_path, monkeypatch):
    dest = tmp_path / "sample_data"
    shutil.copytree(Path("app/sample_data"), dest)
    monkeypatch.setattr(migrate_sample_v2, "SAMPLE_DIR", dest)

    def snapshot() -> dict[str, bytes]:
        return {
            str(p.relative_to(dest)): p.read_bytes()
            for p in sorted(dest.rglob("*"))
            if p.is_file()
        }

    migrate_sample_v2.main()
    first = snapshot()
    migrate_sample_v2.main()
    assert snapshot() == first
```

- [ ] **Step 4: Run the affected tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_sample_data_structure.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add migrate_sample_v2.py tests/test_sample_data_structure.py
git commit -m "refactor: migrate_sample_v2 handles collection folders idempotently"
```

---

### Task 3: Update `run_sample.load_raw_sample_documents` and its test

**Files:**
- Modify: `run_sample.py` (`imports`, `load_raw_sample_documents`)
- Test: `tests/test_run_sample.py::test_load_raw_sample_documents_loads_every_submission`

**Interfaces:**
- Consumes: subfolder layout under `app/sample_data/`.
- Produces: `load_raw_sample_documents() -> tuple[list[dict], list[dict], list[dict]]` returning 2 courses, 1 rubric, 5 submissions with native `ObjectId`/`datetime` values.

- [ ] **Step 1: Add the Extended JSON import**

Add to the imports at the top of `run_sample.py`:

```python
from bson.json_util import loads
```

- [ ] **Step 2: Rewrite `load_raw_sample_documents`**

Replace the function with:

```python
def load_raw_sample_documents() -> tuple[list[dict], list[dict], list[dict]]:
    """Load the checked-in raw MongoDB sample documents.

    The three folders under app/sample_data/ mirror the courses,
    rubricCollection, and submissions collections. Documents are decoded
    from MongoDB Extended JSON ($oid/$date) into native BSON types.
    """

    def load(path: Path) -> object:
        with open(path, encoding="utf-8") as fh:
            return loads(fh.read())

    courses = load(SAMPLE_DIR / "courses" / "courses.json")
    rubrics = [load(SAMPLE_DIR / "rubricCollection" / "rubricCollection.json")]
    submissions: list[dict] = []
    for path in sorted((SAMPLE_DIR / "submissions").glob("submission*.json")):
        submissions.extend(load(path))
    return courses, rubrics, submissions
```

- [ ] **Step 3: Update the test**

In `tests/test_run_sample.py`, change the assertions in `test_load_raw_sample_documents_loads_every_submission`:

```python
    assert len(courses) == 2
    assert len(rubrics) == 1
    assert len(submissions) == 5
    assert all(submission["status"] == "graded" for submission in submissions)
```

- [ ] **Step 4: Run the test**

Run: `.venv\Scripts\python.exe -m pytest tests/test_run_sample.py::test_load_raw_sample_documents_loads_every_submission -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add run_sample.py tests/test_run_sample.py
git commit -m "feat: load sample data collections from folder layout with BSON decoding"
```

---

### Task 4: Preserve `_id` in `seed_raw_samples`

**Files:**
- Modify: `run_sample.py` (`_usable_identity`, `_upsert_natural`, `seed_raw_samples`)
- Test: `tests/test_run_sample.py::test_seed_raw_samples_idempotently_upserts_sample_documents`

**Interfaces:**
- Consumes: decoded documents from `load_raw_sample_documents()`.
- Produces: `seed_raw_samples(db) -> dict[str, int]` returning `{"courses": 2, "rubrics": 1, "submissions": 5}`, upserting by original `_id` when usable.

- [ ] **Step 1: Add helpers and rewrite `seed_raw_samples`**

Add these helpers above `seed_raw_samples`:

```python
def _usable_identity(document: dict) -> object | None:
    """Return the document's _id when it is a usable reference, else None."""
    _id = document.get("_id")
    if _id is None:
        return None
    if isinstance(_id, str) and "..." in _id:
        return None
    return _id


async def _upsert_natural(
    db, collection: str, document: dict, natural_filter: dict
) -> None:
    identity = _usable_identity(document)
    if identity is not None:
        await db[collection].replace_one({"_id": identity}, document, upsert=True)
        return
    replacement = {key: value for key, value in document.items() if key != "_id"}
    await db[collection].replace_one(natural_filter, replacement, upsert=True)
```

Replace the body of `seed_raw_samples` with:

```python
    courses, rubrics, submissions = load_raw_sample_documents()

    for course in courses:
        course_key = course.get("code") or course.get("subject_code") or "IT2040"
        await _upsert_natural(
            db,
            "courses",
            course,
            {"$or": [{"code": course_key}, {"subject_code": course_key}]},
        )
    for rubric in rubrics:
        await _upsert_natural(
            db,
            "rubricCollection",
            rubric,
            {
                "subject_code": rubric["subject_code"],
                "session_name": rubric["session_name"],
            },
        )
    for submission in submissions:
        await _upsert_natural(
            db,
            "submissions",
            submission,
            {
                "student_id": submission["student_id"],
                "subject_code": submission["subject_code"],
                "session_name": submission["session_name"],
            },
        )

    return {
        "courses": len(courses),
        "rubrics": len(rubrics),
        "submissions": len(submissions),
    }
```

- [ ] **Step 2: Update the seed test**

In `tests/test_run_sample.py`, in `test_seed_raw_samples_idempotently_upserts_sample_documents`, change:

```python
        expected_counts = {"courses": 1, "rubrics": 1, "submissions": 5}
```

to:

```python
        expected_counts = {"courses": 2, "rubrics": 1, "submissions": 5}
```

and the course count assertion:

```python
        ) == 1
```

(after the `db["courses"].count_documents` call, inside the same test) to:

```python
        ) == 2
```

- [ ] **Step 3: Run the test**

Run: `.venv\Scripts\python.exe -m pytest tests/test_run_sample.py::test_seed_raw_samples_idempotently_upserts_sample_documents -v`
Expected: PASS (requires the test MongoDB database).

- [ ] **Step 4: Commit**

```bash
git add run_sample.py tests/test_run_sample.py
git commit -m "feat: seed raw samples preserving original _id references"
```

---

### Task 5: Select the rubric-matched course in `run_sample.main`

**Files:**
- Modify: `run_sample.py` (`main` course selection)
- Test: `tests/test_run_sample.py` (`_sample_identity`, `_clean_sample_documents`, `_ExamSnapshotCollection`, `test_main_runs_sample_workflow_and_reports_persisted_results`, `test_main_computes_exam_analytics_after_materialization`)

**Interfaces:**
- Consumes: `load_raw_sample_documents()` (2 courses, rubric `subject_code=IT2040`, `session_name="Final Examination"`).
- Produces: `main` computes exam analytics for `("IT2040", "Final Examination")`.

- [ ] **Step 1: Update the course selection in `main`**

Replace:

```python
        sample_course_code = (
            courses[0].get("code") or courses[0].get("subject_code") or "IT2040"
        )
```

with:

```python
        sample_course_code = next(
            (
                course.get("code") or course.get("subject_code")
                for course in courses
                if (course.get("code") or course.get("subject_code"))
                == rubrics[0].get("subject_code")
            ),
            courses[0].get("code") or courses[0].get("subject_code") or "IT2040",
        )
```

- [ ] **Step 2: Update `tests/test_run_sample.py` session constants**

In `_sample_identity`, no change needed. Update `_clean_sample_documents` — no session literal change needed (it derives sessions from `_sample_identity`).

In `_ExamSnapshotCollection.count_documents`, change:

```python
            "exam_id": "IT2040@Final Examination 2021",
```

to:

```python
            "exam_id": "IT2040@Final Examination",
```

In `test_main_runs_sample_workflow_and_reports_persisted_results`:
- change the `seed` return `{"courses": 1, "rubrics": 1, "submissions": 5}` to `{"courses": 2, "rubrics": 1, "submissions": 5}`;
- change the output assertion `"seeded courses=1 rubrics=1 submissions=5"` to `"seeded courses=2 rubrics=1 submissions=5"`;
- change `assert session_name == "Final Examination 2021"` to `assert session_name == "Final Examination"`.

In `test_main_computes_exam_analytics_after_materialization`:
- change `async def seed_raw_samples(candidate_db):` return to `{"courses": 2, "rubrics": 1, "submissions": 5}`;
- change `return {"exam_id": "IT2040@Final Examination 2021"}` to `return {"exam_id": "IT2040@Final Examination"}`.

- [ ] **Step 3: Run the run_sample tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_run_sample.py -v`
Expected: PASS (MongoDB-dependent tests need the test database).

- [ ] **Step 4: Commit**

```bash
git add run_sample.py tests/test_run_sample.py
git commit -m "feat: run sample exam analytics against rubric-matched course and session"
```

---

### Task 6: Update the session string in the API and exam-analytics tests

**Files:**
- Modify: `tests/test_api_dashboard.py`
- Modify: `tests/test_api_lecturer.py`
- Modify: `tests/test_exam_analytics.py`
- Modify: `tests/test_exam_analytics_service.py`

**Interfaces:**
- Consumes: sample data session "Final Examination".
- Produces: sample-flow API tests exercise `course_code=IT2040`, `session_name="Final Examination"`.

- [ ] **Step 1: Update `tests/test_api_dashboard.py`**

In `_clean_sample_documents`, change:

```python
        {"subject_code": "IT2040", "session_name": "Final Examination 2021"}
```

to:

```python
        {"subject_code": "IT2040", "session_name": "Final Examination"}
```

In `test_dashboard_endpoint_generates_on_first_access`, change:

```python
                    "session_name": "Final Examination 2021",
```

to:

```python
                    "session_name": "Final Examination",
```

and:

```python
        assert body["exam_id"] == "IT2040@Final Examination 2021"
```

to:

```python
        assert body["exam_id"] == "IT2040@Final Examination"
```

- [ ] **Step 2: Update `tests/test_exam_analytics.py`**

In `exam_document()`, change:

```python
        "exam_id": "IT2040@Final Examination 2021",
        "course": {"code": "IT2040", "name": "Database Management Systems"},
        "exam": {"session_name": "Final Examination 2021", "total_marks": 100.0, "question_count": 11},
```

to:

```python
        "exam_id": "IT2040@Final Examination",
        "course": {"code": "IT2040", "name": "Database Management Systems"},
        "exam": {"session_name": "Final Examination", "total_marks": 100.0, "question_count": 11},
```

- [ ] **Step 3: Update `tests/test_api_lecturer.py`**

In `valid_student_document()`, change:

```python
        "exam_id": "IT2040@Final Examination 2021",
```

to:

```python
        "exam_id": "IT2040@Final Examination",
```

In `test_lecturer_analytics_endpoint_returns_document`, change the request path `"/api/lecturers/exams/IT2040/Final%20Examination%202021/analytics"` to `"/api/lecturers/exams/IT2040/Final%20Examination/analytics"` and the assertion `response.json()["exam_id"] == "IT2040@Final Examination 2021"` to `== "IT2040@Final Examination"`.

In `test_lecturer_students_endpoint_reports_analysis_status`, change the upsert filter `"session_name": "Final Examination 2021"` to `"session_name": "Final Examination"`, the request path `"/api/lecturers/exams/IT2040/Final%20Examination%202021/students"` to `"/api/lecturers/exams/IT2040/Final%20Examination/students"`.

In `test_valid_student_document_is_a_reshaped_student_analytics_document`, change both assertions from `"IT2040@Final Examination 2021"` to `"IT2040@Final Examination"`.

- [ ] **Step 4: Update `tests/test_exam_analytics_service.py`**

Replace every occurrence of `"IT2040@Final Examination 2021"` with `"IT2040@Final Examination"` and every occurrence of `"Final Examination 2021"` with `"Final Examination"`.

- [ ] **Step 5: Run the affected tests**

Run: `.venv\Scripts\python.exe -m pytest tests/test_api_dashboard.py tests/test_api_lecturer.py tests/test_exam_analytics.py tests/test_exam_analytics_service.py -v`
Expected: PASS (MongoDB-dependent tests need the test database).

- [ ] **Step 6: Commit**

```bash
git add tests/test_api_dashboard.py tests/test_api_lecturer.py tests/test_exam_analytics.py tests/test_exam_analytics_service.py
git commit -m "test: use new sample session name across API and analytics tests"
```

---

### Task 7: Full suite verification

**Files:**
- None (verification only), unless a straggler test needs a fix.

- [ ] **Step 1: Run the full test suite**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: PASS (MongoDB-dependent tests need the test database).

- [ ] **Step 2: Run the sample runner end-to-end (if MongoDB is available)**

Run: `.venv\Scripts\python.exe run_sample.py dbms_analytics_test`
Expected: seeds `courses=2 rubrics=1 submissions=5`, materializes 5 student analytics, computes exam analytics, exit code 0.

- [ ] **Step 3: Commit any straggler fixes**

```bash
git add -A
git commit -m "test: align remaining sample-data assertions with reorganized collections"
```

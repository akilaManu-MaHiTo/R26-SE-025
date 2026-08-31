# Design: Match codebase to the reorganized sample data collections

Date: 2026-08-13

## Background

Commit `9735849` ("refactor: reorganize sample data structure") reorganized
`app/sample_data/` so that the three sample data folders are faithful examples
of the three MongoDB source collections:

- `app/sample_data/courses/`           -> `courses` collection (a JSON **array** of course documents)
- `app/sample_data/rubricCollection/`  -> `rubricCollection` collection (a single rubric document)
- `app/sample_data/submissions/`       -> `submissions` collection (a JSON **array** of graded submission documents)

The submission and rubric document shapes also changed:

- Rubric now carries `subject_code`, `subject_name`, `year` (2022), `month`,
  `semester`, `session_name` ("Final Examination"), `exam_roster` (null), and
  `questions` with `question_no` ("01".."04"), `question_text`, `max_marks`
  (20 each), `criteria` (`{point, marks}`), and `model_answer`.
- Submissions now carry `subject_code`, `subject_name`, `year`, `month`,
  `semester`, `session_name`, `paper_key`, `status: "graded"`,
  `processed_at`, `lecturer_note`, `rubric_ref`, and
  `evaluation.results[].criteria_breakdown` items shaped as
  `{point, awarded_marks, reason}`.
- `courses.json` now has two courses (SE3040, IT2040); the rubric and all five
  submissions reference IT2040 only.
- IDs and dates use MongoDB Extended JSON (`{"$oid": ...}` for ObjectId,
  `{"$date": ...}` for datetimes).

The rest of the codebase was not updated: the sample-data loaders, the
migration script, and the tests that consume the sample data still assume the
old flat layout and the old 2021 / 11-question / 5-file shapes.

The ingestion, repository, and analytics layers already handle the new shapes
(verified: `normalize_student_submission` yields 4 questions with Q01 score
11/20 and first criterion 2.0/4.0 against the new rubric+submission).

## Requirements

1. `run_sample.load_raw_sample_documents()` reads the new folder layout:
   - `courses/courses.json` as a list of 2 courses (no wrapping),
   - `rubricCollection/rubricCollection.json` as a single document wrapped in a list,
   - every `submissions/submission*.json` file, each an array that is flattened.
2. Raw documents are decoded from MongoDB Extended JSON into native BSON types
   via `bson.json_util.loads` (`$oid` -> `ObjectId`, `$date` -> `datetime`).
3. `seed_raw_samples()` preserves the original `_id` on seeded documents when it
   is usable, so a submission's `rubric_ref` (decoded ObjectId) resolves to the
   seeded rubric document.
4. `run_sample.main()` selects the course that matches the rubric's
   `subject_code` (IT2040) for exam analytics, not `courses[0]` (SE3040).
5. `app/sample_data/loader.py` (`_load`, `load_real`, `course_settings`) reads
   the subfolder layout and flattens arrays; picks the course matching the
   rubric for `load_real`.
6. `migrate_sample_v2.py` is updated to the new layout and is a no-op on
   already-migrated data (preserves `exam_roster` when already present). The
   idempotency test still passes.
7. Sample-data-dependent tests are updated to the new expected values.

## Data flow (unchanged where not listed)

`run_sample.main`:

1. `load_raw_sample_documents()` -> decoded courses, rubrics, submissions.
2. `create_indexes(db)`.
3. `seed_raw_samples(db)` upserts courses/rubric/submissions.
4. `materialize_student_analytics(db, submissions=sample_submissions)` builds
   and persists one `student_analytics` document per submission.
5. `compute_exam_analytics(db, IT2040, "Final Examination")` persists the
   lecturer snapshot.

Repository lookups (`find_course_for_submission`, `find_rubric_for_submission`)
keep their existing behavior. With `_id` preserved during seeding and `$oid`
decoded, the `_id`-based rubric lookup now succeeds; the
`subject_code` + `session_name` fallback remains as a safety net.

## Files to change

Production:

- `run_sample.py` (`load_raw_sample_documents`, `seed_raw_samples`, course selection in `main`).
- `app/sample_data/loader.py` (`_load`, `load_real`; `course_settings` unchanged signature).
- `migrate_sample_v2.py` (subfolder reads/writes, array handling, preserve `exam_roster`).

Tests:

- `tests/test_loader.py`
- `tests/test_student_data_ingestion.py` (`test_normalize_submission_joins_questions_and_criteria`)
- `tests/test_sample_data_structure.py`
- `tests/test_run_sample.py`
- `tests/test_api_dashboard.py`
- `tests/test_api_lecturer.py`
- `tests/test_exam_analytics_service.py`

Not changed: self-contained tests that use "Final Examination 2021" only as
their own fabricated constant (e.g. `test_repository.py`,
`test_schemas_student.py`, `test_practice_questions.py`,
`test_student_dashboard_service.py`, `test_api_practice_questions.py`).

## Error handling

- Loading uses `bson.json_util.loads`; malformed Extended JSON surfaces as a
  `json`/`bson` error (same failure class as today).
- Seeding preserves `_id` only when usable (real ObjectId after decode); the
  legacy `"..."` placeholder values are never treated as usable.
- `run_sample.main` falls back to the first course code if no course matches
  the rubric's `subject_code`.

## Testing

Run the full pytest suite (`python -m pytest`). The MongoDB-dependent tests
require the test database as today. Key coverage:

- `load_raw_sample_documents` returns 2 courses, 1 rubric, 5 submissions with
  native `ObjectId`/`datetime` types.
- `seed_raw_samples` counts are `{"courses": 2, "rubrics": 1, "submissions": 5}`
  and is idempotent.
- The migration script is byte-idempotent on the new layout.
- Dashboard/lecturer/exam-analytics sample flows work against session
  "Final Examination".

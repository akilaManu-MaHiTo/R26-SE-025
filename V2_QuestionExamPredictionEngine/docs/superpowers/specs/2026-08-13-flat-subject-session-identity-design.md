# Flat Subject/Session Identity for Analytics Documents

**Date:** 2026-08-13

## Goal

Reshape the persisted student and lecturer analytics documents so each one identifies *which* assessment it describes using flat, human-readable subject/session fields, replacing the opaque `exam_id` (`IT2040@Final Examination`) and the redundant `course` block.

## Requirements

For both `student_analytics` and `analytics_snapshots` documents:

- Add top-level fields: `subject_code`, `subject_name`, `year`, `month`, `semester`, `session_name`.
- Remove: `exam_id` and the `course` block.
- Values are sourced from the rubric (`rubricCollection`), which already contains exactly these fields (e.g. `subject_code=IT2040`, `subject_name=Database Management Systems`, `session_name=Final Examination`, `year=2022`, `month=7`, `semester=1`).

Sample target document header:

```json
{
  "student_id": "IT22145976",
  "subject_code": "IT2040",
  "subject_name": "Database Management Systems",
  "year": 2022,
  "month": 7,
  "semester": 1,
  "session_name": "Final Examination",
  "overall_performance": { ... }
}
```

## Scope

- Student analytics: pipeline, schema, repository identity, API responses.
- Lecturer exam analytics: `analytics_snapshots`, lecturer API responses.
- `run_sample.py`: filter/count code updated to the new identity, but the script is **not executed** during verification.

Out of scope: `question_catalog`, `question_attempts`, `analysis_runs`, `exam_recommendations`, `generatedQuestions` — these retain their `exam_id` fields.

## Design

### 1. Schemas

**`app/schemas/student.py`**

- `StudentAnalyticsDocument`: remove `exam_id` and `course`; add:

  ```python
  subject_code: str = Field(min_length=1)
  subject_name: str = Field(min_length=1)
  year: int
  month: int = Field(ge=1, le=12)
  semester: int = Field(ge=1)
  session_name: str = Field(min_length=1)
  ```

- Delete the now-unused `CourseInfo` model.

**`app/schemas/exam_analytics.py`**

- `ExamAnalyticsDocument`: remove `exam_id` and `course`; add the same six fields.
- Delete the now-unused `ExamCourse` model.
- The `exam` block keeps `session_name` (redundant with the top-level field but harmless for the lecturer UI).

### 2. Normalization (`app/ingestion/student_data.py`)

- `NormalizedStudentInput` gains `subject_name: str`, `year: int`, `month: int`, `semester: int`.
- `normalize_student_submission` populates them from the rubric:

  ```python
  subject_name = str(rubric.get("subject_name") or course_name or "").strip() or course_code
  year = int(rubric.get("year") or 0)
  month = int(rubric.get("month") or 0)
  semester = int(rubric.get("semester") or 0)
  ```

  (`subject_code` already exists as `course_code`.)

### 3. Builders

**`app/services/student_pipeline.py`** — `_assemble_document`:

- Replace `course={...}` and `exam_id=f"{code}@{session}"` with the flat subject/session fields from `normalized`.
- Drop `course` from the `document.update(...)` call.

**`app/services/exam_analytics.py`** — `compute_exam_analytics`:

- Replace the `exam_id`/`course` document fields with flat subject/session fields sourced from the rubric (`subject_code`, `subject_name`, `year`, `month`, `semester`, `session_name`).
- Course-name fallback logic maps to `subject_name`.

### 4. Repository (`app/db/repository.py`)

- `_UNIQUE_INDEXES`:
  - `student_analytics`: `(student_id, 1), (subject_code, 1), (session_name, 1)`
  - `analytics_snapshots`: `(subject_code, 1), (session_name, 1), (analytics_version, 1)`
- `upsert_student_analytics`: identity = `{student_id, subject_code, session_name}`.
- `find_student_analytics`: filters use `subject_code` + `session_name` instead of `course.code` + `exam_id`.
- `upsert_exam_analytics`: identity = `{subject_code, session_name, analytics_version}`.
- `find_exam_analytics`: filter uses `subject_code` + `session_name`.

### 5. APIs

- `app/api/dashboard.py`, `app/api/lecturer.py`: external contract unchanged — query params stay `course_code`/`session_name`, mapped to `subject_code`/`session_name` internally by the repository layer.

### 6. run_sample.py

- `sample_analytics_filter` (lines ~151-164): switch from `course.code` + `exam_id` to `subject_code` + `session_name`.
- Exam-analytics count filter (lines ~178-183): switch to `subject_code` + `session_name`.
- Not executed during verification.

### 7. Tests

Update fixtures and assertions that reference `exam_id`/`course`/`CourseInfo`:

- `tests/test_api_dashboard.py`
- `tests/test_api_lecturer.py`
- `tests/test_exam_analytics.py`
- `tests/test_exam_analytics_service.py`
- `tests/test_run_sample.py`
- `tests/test_student_dashboard_service.py`
- `tests/test_api_practice_questions.py`
- `tests/test_repository.py`

## Verification

- Run the affected unit test suite (excluding `run_sample.py` execution):

  `.\.venv\Scripts\python.exe -m pytest tests/test_schemas_student.py tests/test_student_document_analytics.py tests/test_student_data_ingestion.py tests/test_student_pipeline.py tests/test_student_dashboard_service.py tests/test_api_dashboard.py tests/test_exam_analytics.py tests/test_exam_analytics_service.py tests/test_api_lecturer.py tests/test_repository.py -q`
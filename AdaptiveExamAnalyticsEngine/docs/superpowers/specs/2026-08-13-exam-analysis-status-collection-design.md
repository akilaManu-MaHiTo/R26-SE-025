# Exam Analysis Status Collection (`analyzedExams`)

**Date:** 2026-08-13

## Goal

Add a MongoDB collection that records whether each exam has been analyzed, so dashboards and tooling can list exams with a `done`/`pending` status.

## Requirements

- New collection `analyzedExams` with one document per exam (keyed by `subject_code` + `session_name`).
- Document fields:

  ```json
  {
    "subject_code": "IT2040",
    "subject_name": "Database Management Systems",
    "year": 2022,
    "month": 7,
    "semester": 1,
    "session_name": "Final Examination",
    "analyzed": "done",
    "analyzed_at": "2026-08-13T12:19:46.289563Z"
  }
  ```

- `analyzed` is `"done"` or `"pending"`.
- `analyzed_at` is an ISO-8601 UTC timestamp populated only when `analyzed == "done"`.

## Design

### 1. Repository (`app/db/repository.py`)

- Add `"analyzedExams"` to `COLLECTIONS`.
- Add a unique index so each exam has exactly one status document:
  - `analyzedExams`: `(subject_code, 1), (session_name, 1)`
- New helpers:

  ```python
  async def upsert_exam_analysis_status(db, document: dict) -> None:
      identity = {"subject_code": document["subject_code"], "session_name": document["session_name"]}
      await db["analyzedExams"].replace_one(identity, deepcopy(document), upsert=True)

  async def find_exam_analysis_status(db, subject_code: str, session_name: str) -> dict | None:
      return await db["analyzedExams"].find_one(
          {"subject_code": subject_code, "session_name": session_name}
      )
  ```

### 2. Mark `done` in the exam analytics flow (`app/services/exam_analytics.py`)

- In `compute_exam_analytics`, after `upsert_exam_analytics` succeeds, upsert an `analyzedExams` document:

  ```python
  await upsert_exam_analysis_status(db, {
      "subject_code": course_code,
      "subject_name": subject_name,
      "year": year,
      "month": month,
      "semester": semester,
      "session_name": session_name,
      "analyzed": "done",
      "analyzed_at": datetime.now(timezone.utc).isoformat(),
  })
  ```

- This covers both the `run_sample.py` path and the on-demand lecturer API path (`app/api/lecturer.py` calls `compute_exam_analytics` when no snapshot exists).

### 3. Seed `pending` markers (`run_sample.py`)

- After `seed_raw_samples`, for each rubric in the sample data, upsert an `analyzedExams` document with `analyzed="pending"`.
- Do not overwrite an existing `done` marker — use a check-then-write (or rely on the upsert only when the doc does not yet exist):

  ```python
  for rubric in rubrics:
      subject_code = rubric["subject_code"]
      session_name = rubric["session_name"]
      existing = await find_exam_analysis_status(db, subject_code, session_name)
      if existing is not None:
          continue
      await upsert_exam_analysis_status(db, {
          "subject_code": subject_code,
          "subject_name": rubric.get("subject_name") or subject_code,
          "year": int(rubric.get("year") or 0),
          "month": int(rubric.get("month") or 0),
          "semester": int(rubric.get("semester") or 0),
          "session_name": session_name,
          "analyzed": "pending",
      })
  ```

### 4. Tests

- `tests/test_repository.py`: round-trip upsert/find for `analyzedExams`; assert the unique index is created and named.
- `tests/test_exam_analytics_service.py`: after `compute_exam_analytics`, an `analyzedExams` doc exists with `analyzed == "done"`.
- `tests/test_run_sample.py`: seeding writes `pending` markers and does not overwrite a pre-existing `done` marker.

## Out of Scope

- No new API endpoint; the collection is consumed by future dashboard work.
- No changes to `student_analytics` or `analytics_snapshots` shapes.

## Verification

Run the affected test suite:

```
.\.venv\Scripts\python.exe -m pytest tests/test_repository.py tests/test_exam_analytics_service.py tests/test_run_sample.py -q
```

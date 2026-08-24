# Student Account Provisioning on Lecture Exam Analysis — Design

Date: 2026-08-24
Status: Approved
Scope: V2_QuestionExamPredictionEngine (V2 engine) + Gradex_AI_Server routing

## 1. Goal
When a lecturer triggers **Analyze** for an exam in the Lecturer Dashboard (`GET /api/lecturers/exams/{course_code}/{session_name}/analytics`), automatically create student accounts for every student who faced that exam (i.e., has a `graded` submission for `course_code` + `session_name`). Email = `{lower(student_id)}@my.sliit.lk`, default password = `Student@123` (hashed).

## 2. Architecture
- **Trigger point:** `app/api/lecturer.py:lecturer_exam_analytics` — after `document` is obtained (either cache hit or `compute_exam_analytics` success). Best-effort, does not fail the analytics response.
- **New service:** `app/services/student_accounts.py`
  - `DEFAULT_PASSWORD = "Student@123"`
  - `EMAIL_DOMAIN = "my.sliit.lk"`
  - `student_email(student_id: str) -> str` — strip, lower, append domain
  - `hash_password(password: str) -> str` — `hashlib.pbkdf2_hmac('sha256', pwd, salt, 100000)` with `secrets.token_bytes(16)`, stored as `pbkdf2_sha256$iterations$salt_hex$hash_hex`
  - `verify_password(password, stored) -> bool` helper
  - `ensure_student_account(db, student_id) -> dict` — idempotent single upsert
  - `provision_student_accounts(db, course_code, session_name, year, month, semester) -> {created, existed, total}` — fetches `find_graded_submissions_for_exam`, deduplicates student_ids, iterates `ensure_student_account`
- **Repository changes:** `app/db/repository.py`
  - Add `"users"` to `COLLECTIONS`
  - Add `_UNIQUE_INDEXES["users"] = [("email",1), ("student_id",1)]` (separate unique indexes)
  - Helpers: `find_user_by_email(db, email)`, `find_user_by_student_id(db, student_id)`, `upsert_user(db, doc)`
  - Index creation via existing `create_indexes`
- **Collection schema (`users`):**
  ```json
  {
    "student_id": "IT22134776",
    "email": "it22134776@my.sliit.lk",
    "password_hash": "pbkdf2_sha256$100000$...$...",
    "role": "student",
    "created_at": "2026-08-24T...",
    "updated_at": "2026-08-24T..."
  }
  ```

## 3. Data Flow
1. Lecturer calls `GET /api/lecturers/exams/{course}/{session}/analytics?year&month&semester`
2. Handler tries `find_exam_analytics`; on miss calls `compute_exam_analytics`
3. On success, handler calls `provision_student_accounts(db, ...)` inside try/except
4. Service fetches graded submissions, deduplicates, for each student_id: check `users` by email/student_id, if exists skip, else insert with hashed password
5. Analytics document returned regardless of provisioning result; provisioning errors logged

## 4. Error Handling
- No graded submissions → `ExamNotFound` already raised, no provisioning
- DB write failures → caught, logged, do not propagate 5xx
- Duplicate key races → catch DuplicateKeyError, treat as existed
- Invalid student_id (blank) → skip

## 5. Security
- No plaintext password stored
- Stdlib only (no new deps) using pbkdf2_hmac; iterations 100k
- Email lowercased to avoid duplicates like `IT221...@my.sliit.lk` vs `it221...`

## 6. Testing
- Unit: `tests/test_student_accounts.py` — email lowercasing, hash/verify, idempotent ensure, bulk provision with dedup, no-op when user exists
- Integration: `tests/test_api_lecturer.py` — mock provision, verify called on both cache and compute paths, verify analytics still 200 when provision raises
- Existing `tests/test_repository.py` — ensure users indexes

## 7. Out of Scope
- Frontend login integration (LoginPage still role-based mock)
- Password reset flow
- Lecturer/ admin account creation
- Email sending

## 8. Alternatives Considered
- Hook inside `compute_exam_analytics` only → misses cache-hit case
- BackgroundTasks → eventual consistency, harder to test
-Chosen: endpoint-level synchronous best-effort, covers both paths, minimal latency.

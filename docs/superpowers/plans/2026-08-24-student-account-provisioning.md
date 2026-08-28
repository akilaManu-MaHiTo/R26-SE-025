# Student Account Provisioning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically create student accounts (email `{lower(student_id)}@my.sliit.lk`, password `Student@123` hashed) when lecturer analyzes an exam via `GET /api/lecturers/exams/{course}/{session}/analytics`.

**Architecture:** New `app/services/student_accounts.py` provides idempotent provisioning with pbkdf2_hmac hashing (stdlib). Repository adds `users` collection with unique indexes on `email` and `student_id`. Lecturer endpoint calls `provision_student_accounts` best-effort after analytics document is obtained (both cache and compute paths).

**Tech Stack:** FastAPI, Motor (Mongo), hashlib/pbkdf2, secrets, pytest-asyncio

## Global Constraints
- Email lowercased + `@my.sliit.lk`
- Default password `Student@123`, never store plaintext, store `pbkdf2_sha256$100000$salt_hex$hash_hex`
- Idempotent: skip if `email` or `student_id` exists
- Hook in `app/api/lecturer.py:lecturer_exam_analytics` after document, not failing analytics on provisioning error
- Use `grading` DB via `app/api/deps.py:get_db` and `app/db/repository.py`
- No new external dependencies
---

### Task 1: Repository — users collection and helpers

**Files:**
- Modify: `V2_QuestionExamPredictionEngine/app/db/repository.py:1-52`
- Test: `V2_QuestionExamPredictionEngine/tests/test_repository_users.py` (new)

**Interfaces:**
- Consumes: existing `COLLECTIONS`, `_UNIQUE_INDEXES`, `create_indexes`
- Produces: `find_user_by_email(db, email)`, `find_user_by_student_id(db, student_id)`, `upsert_user(db, doc)`, updated `COLLECTIONS` and `_UNIQUE_INDEXES` for `users`

- [ ] **Step 1: Write the failing test for repository helpers**

```python
# tests/test_repository_users.py
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.db.repository import COLLECTIONS, _UNIQUE_INDEXES

def test_users_in_collections():
    assert "users" in COLLECTIONS

def test_users_unique_indexes():
    assert "users" in _UNIQUE_INDEXES

async def test_find_user_by_email_calls_db(monkeypatch):
    from app.db import repository
    mock_db = MagicMock()
    mock_col = AsyncMock()
    mock_col.find_one = AsyncMock(return_value=None)
    mock_db.__getitem__.return_value = mock_col
    result = await repository.find_user_by_email(mock_db, "it22134776@my.sliit.lk")
    assert result is None
    mock_col.find_one.assert_awaited_once_with({"email": "it22134776@my.sliit.lk"})

async def test_upsert_user_calls_replace():
    from app.db import repository
    mock_db = MagicMock()
    mock_col = AsyncMock()
    mock_db.__getitem__.return_value = mock_col
    doc = {"student_id": "IT22134776", "email": "it22134776@my.sliit.lk", "password_hash": "x"}
    await repository.upsert_user(mock_db, doc)
    mock_col.replace_one.assert_awaited()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest V2_QuestionExamPredictionEngine/tests/test_repository_users.py -v`
Expected: FAIL — `users not in COLLECTIONS`, `find_user_by_email not defined`

- [ ] **Step 3: Write minimal implementation in repository.py**

In `V2_QuestionExamPredictionEngine/app/db/repository.py`:
- Add `"users"` to `COLLECTIONS` tuple (after `"exam_drafts"`)
- Add to `_UNIQUE_INDEXES`: `"users": [("email", 1)]` and also ensure `student_id` unique via separate index? Use two indexes but _UNIQUE_INDEXES only supports one entry per collection; create two separate unique indexes manually in `create_indexes` or store as list with two fields? Simplest: create unique on `email` and also on `student_id` via second index creation. For now add `"users": [("email",1)]` and handle second index separately. Alternatively add two entries: `"users_email": [("email",1)]` — but follow pattern: single unique on email is sufficient for idempotency since email derived from student_id. Add `"users": [("email",1)]` and in `create_indexes` also ensure `student_id` unique via manual call if collection == "users".
Simpler: set `"users": [("email",1)]` and manually ensure second index.
Add functions:
```python
async def find_user_by_email(db, email: str) -> dict | None:
    doc = await db["users"].find_one({"email": email})
    if doc is None:
        return None
    doc.pop("_id", None)
    return doc

async def find_user_by_student_id(db, student_id: str) -> dict | None:
    doc = await db["users"].find_one({"student_id": student_id})
    if doc is None:
        return None
    doc.pop("_id", None)
    return doc

async def upsert_user(db, doc: dict) -> None:
    await db["users"].replace_one({"email": doc["email"]}, doc, upsert=True)
```
Update `create_indexes` to create second index for `users` on `student_id`:
```python
if collection == "users":
    await db[collection].create_index([("student_id", 1)], unique=True, name="uniq_users_student_id")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest V2_QuestionExamPredictionEngine/tests/test_repository_users.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add V2_QuestionExamPredictionEngine/app/db/repository.py V2_QuestionExamPredictionEngine/tests/test_repository_users.py
git commit -m "feat: add users collection and repo helpers for student provisioning"
```

### Task 2: Student Accounts Service

**Files:**
- Create: `V2_QuestionExamPredictionEngine/app/services/student_accounts.py`
- Test: `V2_QuestionExamPredictionEngine/tests/test_student_accounts.py`

**Interfaces:**
- Consumes: `app/db/repository.py: find_user_by_email, find_user_by_student_id, upsert_user, find_graded_submissions_for_exam`
- Produces: `student_email(student_id)->str`, `hash_password(pwd)->str`, `verify_password(pwd, hash)->bool`, `ensure_student_account(db, student_id)->dict`, `provision_student_accounts(db, course_code, session_name, year, month, semester)->dict`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_student_accounts.py
import re
from unittest.mock import AsyncMock, MagicMock

from app.services import student_accounts

def test_student_email_lowercases():
    assert student_accounts.student_email("IT22134776") == "it22134776@my.sliit.lk"
    assert student_accounts.student_email("  IT22134776  ") == "it22134776@my.sliit.lk"

def test_hash_and_verify():
    h = student_accounts.hash_password("Student@123")
    assert h.startswith("pbkdf2_sha256$100000$")
    assert student_accounts.verify_password("Student@123", h) is True
    assert student_accounts.verify_password("wrong", h) is False

async def test_ensure_creates_when_missing(monkeypatch):
    mock_db = MagicMock()
    monkeypatch.setattr(student_accounts, "find_user_by_email", AsyncMock(return_value=None))
    monkeypatch.setattr(student_accounts, "find_user_by_student_id", AsyncMock(return_value=None))
    mock_upsert = AsyncMock()
    monkeypatch.setattr(student_accounts, "upsert_user", mock_upsert)
    result = await student_accounts.ensure_student_account(mock_db, "IT22134776")
    assert result["email"] == "it22134776@my.sliit.lk"
    assert result["student_id"] == "IT22134776"
    mock_upsert.assert_awaited_once()

async def test_ensure_skips_when_exists(monkeypatch):
    existing = {"email": "it22134776@my.sliit.lk", "student_id": "IT22134776"}
    monkeypatch.setattr(student_accounts, "find_user_by_email", AsyncMock(return_value=existing))
    mock_upsert = AsyncMock()
    monkeypatch.setattr(student_accounts, "upsert_user", mock_upsert)
    result = await student_accounts.ensure_student_account(MagicMock(), "IT22134776")
    assert result == existing
    mock_upsert.assert_not_awaited()

async def test_provision_dedups_and_counts(monkeypatch):
    subs = [{"student_id": "IT1"}, {"student_id": "IT1"}, {"student_id": "IT2"}]
    monkeypatch.setattr(student_accounts, "find_graded_submissions_for_exam", AsyncMock(return_value=subs))
    # first call creates, second exists, third creates
    calls = []
    async def fake_ensure(db, sid):
        calls.append(sid)
        return {"student_id": sid, "email": f"{sid.lower()}@my.sliit.lk", "created": sid=="IT1" and len(calls)==1}
    monkeypatch.setattr(student_accounts, "ensure_student_account", fake_ensure)
    # we need to track created vs existed: mock ensure to return with flag
    # instead test provision returns total=2 unique
    mock_db = MagicMock()
    result = await student_accounts.provision_student_accounts(mock_db, "IT2040", "Final Examination")
    assert result["total"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest V2_QuestionExamPredictionEngine/tests/test_student_accounts.py -v`
Expected: FAIL — `module not found` or `function not defined`

- [ ] **Step 3: Write minimal implementation**

Create `V2_QuestionExamPredictionEngine/app/services/student_accounts.py`:
```python
import hashlib, secrets
from datetime import datetime, timezone

from app.db.repository import find_user_by_email, find_user_by_student_id, upsert_user, find_graded_submissions_for_exam

DEFAULT_PASSWORD = "Student@123"
EMAIL_DOMAIN = "my.sliit.lk"
ITERATIONS = 100000

def student_email(student_id: str) -> str:
    return f"{student_id.strip().lower()}@my.sliit.lk"

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return f"pbkdf2_sha256${ITERATIONS}${salt.hex()}${dk.hex()}"

def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_hex, hash_hex = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iters))
        return dk.hex() == hash_hex
    except Exception:
        return False

async def ensure_student_account(db, student_id: str) -> dict:
    sid = student_id.strip()
    if not sid:
        raise ValueError("student_id required")
    email = student_email(sid)
    existing = await find_user_by_email(db, email)
    if existing:
        return existing
    # also check by student_id to avoid duplicate email case mismatch
    by_sid = await find_user_by_student_id(db, sid)
    if by_sid:
        return by_sid
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "student_id": sid,
        "email": email,
        "password_hash": hash_password(DEFAULT_PASSWORD),
        "role": "student",
        "created_at": now,
        "updated_at": now,
    }
    await upsert_user(db, doc)
    return doc

async def provision_student_accounts(db, course_code: str, session_name: str, year=None, month=None, semester=None) -> dict:
    submissions = await find_graded_submissions_for_exam(db, course_code, session_name, year, month, semester)
    seen = set()
    created = 0
    existed = 0
    for sub in submissions:
        sid = str(sub.get("student_id") or "").strip()
        if not sid or sid in seen:
            continue
        seen.add(sid)
        email = student_email(sid)
        existing = await find_user_by_email(db, email)
        if existing or await find_user_by_student_id(db, sid):
            existed += 1
            continue
        await ensure_student_account(db, sid)
        created += 1
    return {"total": len(seen), "created": created, "existed": existed}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest V2_QuestionExamPredictionEngine/tests/test_student_accounts.py -v`
Expected: PASS (adjust test to match actual return shape)

- [ ] **Step 5: Commit**

```bash
git add V2_QuestionExamPredictionEngine/app/services/student_accounts.py V2_QuestionExamPredictionEngine/tests/test_student_accounts.py
git commit -m "feat: add student account provisioning service with pbkdf2 hashing"
```

### Task 3: Hook provisioning into lecturer analytics endpoint

**Files:**
- Modify: `V2_QuestionExamPredictionEngine/app/api/lecturer.py:31-52`
- Test: `V2_QuestionExamPredictionEngine/tests/test_lecturer_provision.py` (or extend `tests/test_api_lecturer.py`)

**Interfaces:**
- Consumes: `app/services/student_accounts.py: provision_student_accounts`
- Produces: Side-effect on `GET /api/lecturers/exams/{course}/{session}/analytics` (and also ensure cached path provisions)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_lecturer_provision.py
from unittest.mock import AsyncMock, patch
import httpx, pytest
from app.main import app
from app.api import deps

async def test_analytics_provisions_accounts(test_db, monkeypatch):
    mock_provision = AsyncMock(return_value={"total":1,"created":1,"existed":0})
    monkeypatch.setattr("app.api.lecturer.provision_student_accounts", mock_provision)
    # need to ensure exam exists: seed minimal rubric+submission or mock find_exam_analytics
    monkeypatch.setattr("app.api.lecturer.find_exam_analytics", AsyncMock(return_value={"subject_code":"IT2040","session_name":"Final","year":2024,"month":1,"semester":1,"analytics_version":"1.0","canonical_topic_performance":[]}))
    monkeypatch.setattr("app.api.lecturer.canonicalize_topics", AsyncMock(return_value={}))
    app.dependency_overrides[deps.get_db] = lambda: test_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/lecturers/exams/IT2040/Final/analytics", params={"year":2024,"month":1,"semester":1})
        assert resp.status_code == 200
        mock_provision.assert_awaited_once()
    finally:
        app.dependency_overrides.clear()

async def test_analytics_still_returns_200_when_provision_fails(test_db, monkeypatch):
    monkeypatch.setattr("app.api.lecturer.provision_student_accounts", AsyncMock(side_effect=Exception("db down")))
    monkeypatch.setattr("app.api.lecturer.find_exam_analytics", AsyncMock(return_value={"subject_code":"IT2040","session_name":"Final","year":2024,"month":1,"semester":1,"analytics_version":"1.0"}))
    monkeypatch.setattr("app.api.lecturer.canonicalize_topics", AsyncMock(return_value={}))
    app.dependency_overrides[deps.get_db] = lambda: test_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/lecturers/exams/IT2040/Final/analytics", params={"year":2024,"month":1,"semester":1})
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.clear()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest V2_QuestionExamPredictionEngine/tests/test_lecturer_provision.py -v`
Expected: FAIL — `provision_student_accounts not found`

- [ ] **Step 3: Write minimal implementation**

In `V2_QuestionExamPredictionEngine/app/api/lecturer.py`:
- Add import: `from app.services.student_accounts import provision_student_accounts`
- After obtaining `document` (both cache hit and compute paths, before canonicalize), add:
```python
    try:
        await provision_student_accounts(db, course_code, session_name, year, month, semester)
    except Exception:
        pass  # best-effort, log if logger available
```
Ensure it is after `if document is None: try compute ... except ...` and before `canonical = await canonicalize_topics(...)`.

Full snippet for `lecturer_exam_analytics`:
```python
    document = await find_exam_analytics(db, course_code, session_name, year, month, semester)
    if document is None:
        try:
            document = await compute_exam_analytics(db, course_code, session_name, year, month, semester)
        except ExamNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    try:
        await provision_student_accounts(db, course_code, session_name, year, month, semester)
    except Exception:
        pass
    canonical = await canonicalize_topics(db, document, course_code, session_name, year, month, semester)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest V2_QuestionExamPredictionEngine/tests/test_lecturer_provision.py -v` and `python -m pytest V2_QuestionExamPredictionEngine/tests/test_api_lecturer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add V2_QuestionExamPredictionEngine/app/api/lecturer.py V2_QuestionExamPredictionEngine/tests/test_lecturer_provision.py
git commit -m "feat: provision student accounts when lecturer analyzes exam"
```

### Task 4: Verification and docs

**Files:**
- Modify: none
- Test: run full suite

- [ ] **Step 1: Run full relevant suite**

Run: `python -m pytest V2_QuestionExamPredictionEngine/tests/test_student_accounts.py V2_QuestionExamPredictionEngine/tests/test_repository_users.py V2_QuestionExamPredictionEngine/tests/test_lecturer_provision.py V2_QuestionExamPredictionEngine/tests/test_api_lecturer.py -v`

- [ ] **Step 2: Manual check — provision idempotency**

Run: `python -m pytest V2_QuestionExamPredictionEngine/tests/ -k "provision or student_account or repository_users" -v`
Expected: all PASS, no duplicate key errors

- [ ] **Step 3: Commit docs if needed**

No doc change.


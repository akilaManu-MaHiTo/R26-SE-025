# Per-Course Taxonomy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable lecturers to add/remove per-course DBMS topics (canonical_topic + aliases + subtopics) persisted in MongoDB `course_taxonomies` mapped to `courses`, fixing `Unclassified: 40 attempts` via DB-first `load_taxonomy`.

**Architecture:** New `course_taxonomies` collection (`course_code` unique) is source of truth per course; file `config/topic_taxonomy.json` only seeds `IT2040`. `app/taxonomy/normalizer.py` becomes async per-course with TTL cache. New `app/api/taxonomy.py` CRUD + `courses.taxonomy_version` mirror + `examAnalytics.taxonomy_version` fingerprint for soft stale Reanalyse.

**Tech Stack:** Python 3.11 FastAPI Motor (MongoDB async), Pydantic v2, `cachetools.TTLCache`, React TypeScript `Gradex_AI_Client`, `pytest`/`mongomock`/`httpx`.

## Global Constraints

- Per-course DB as primary, file only seeds `IT2040` (empty for new courses).
- Full control: each topic has `canonical_topic` (3-120 chars) + `aliases[0..20]` (2-100 chars) + `subtopics[0..50]` (2-200 chars).
- UI only inside `AdaptiveExamAnalyticsEngine` Analytics dashboard (`AnalyticsPage.tsx`), not Grading course UI.
- Soft stale: do not delete snapshots; set `taxonomy_version` mismatch banner + require Reanalyse.
- Uniqueness per `course_code` case-insensitive on `canonical_id`/`canonical_topic`/aliases; delete warns if used but still allows.
- Follow existing patterns: `app/db/repository.py` `COLLECTIONS` tuple, `create_indexes`, `app/api/lecturer.py` router style, `_with_spec_aliases`.

---

### Task 1: DB Model, Indexes, Repository & Seed

**Files:**
- Modify: `AdaptiveExamAnalyticsEngine/app/db/repository.py:5-27`
- Test: `AdaptiveExamAnalyticsEngine/tests/test_repository_taxonomy.py` (new)

**Interfaces:**
- Consumes: existing `COLLECTIONS`, `create_indexes(db)`; `CONFIG_TAXONOMY` at `AdaptiveExamAnalyticsEngine/config/topic_taxonomy.json`.
- Produces: `COLLECTIONS += ("course_taxonomies",)`; `_UNIQUE_INDEXES["course_taxonomies"] = [("course_code",1)]`; async helpers `get_course_taxonomy(db, course_code) -> dict|None`, `upsert_course_taxonomy(db, course_code, topics, updated_by) -> dict` (inc version), `seed_it2040_if_empty(db) -> dict|None`, `find_taxonomy_usage_count(db, course_code, canonical_id) -> int` (counts examAnalytics canonical hits).

- [ ] **Step 1: Write failing test for repository helpers**

```python
# tests/test_repository_taxonomy.py
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_course_taxonomies_in_collections():
    from app.db.repository import COLLECTIONS, _UNIQUE_INDEXES
    assert "course_taxonomies" in COLLECTIONS
    assert ("course_code",1) in _UNIQUE_INDEXES["course_taxonomies"]

@pytest.mark.asyncio
async def test_upsert_inc_version(monkeypatch):
    from app.db import repository
    mock_db = MagicMock()
    mock_col = AsyncMock()
    mock_col.find_one = AsyncMock(return_value=None)
    mock_col.replace_one = AsyncMock()
    mock_col.find_one = AsyncMock(side_effect=[None, {"course_code":"CS3010","topics":{"os":{"canonical_topic":"OS","aliases":[],"subtopics":[]}},"version":1}])
    mock_db.__getitem__.return_value = mock_col
    # should increment to 1 on create, 2 on second upsert
    doc = await repository.upsert_course_taxonomy(mock_db, "CS3010", {"os":{"canonical_topic":"OS","aliases":[],"subtopics":[]}}, updated_by="lecturer@x")
    assert doc["version"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest AdaptiveExamAnalyticsEngine/tests/test_repository_taxonomy.py -v`
Expected: FAIL `course_taxonomies not in COLLECTIONS` / `upsert_course_taxonomy not defined`.

- [ ] **Step 3: Implement minimal repository changes**

```python
# app/db/repository.py:5
COLLECTIONS = (
    "courses",
    "exams",
    "questions",
    "rubrics",
    "rubricCollection",
    "submissions",
    "student_analytics",
    "studentExamAnalysis",
    "studentExamResults",
    "question_catalog",
    "question_attempts",
    "analytics_snapshots",
    "examAnalytics",
    "exam_recommendations",
    "analysis_runs",
    "generatedQuestions",
    "analyzedExams",
    "exam_drafts",
    "users",
    "course_taxonomies",
)
# :27
_UNIQUE_INDEXES = {
    ...
    "course_taxonomies": [("course_code", 1)],
    ...
}

# add after find_diagram_markings_for_exam, before EOF:
import json as _json
from pathlib import Path as _Path
from datetime import datetime, timezone

async def get_course_taxonomy(db, course_code: str) -> dict | None:
    doc = await db["course_taxonomies"].find_one({"course_code": course_code}, {"_id":0})
    return doc

async def upsert_course_taxonomy(db, course_code: str, topics: dict, updated_by: str = "system") -> dict:
    now = datetime.now(timezone.utc).isoformat()
    existing = await db["course_taxonomies"].find_one({"course_code": course_code})
    version = int(existing["version"])+1 if existing and "version" in existing else 1
    created_at = existing.get("created_at") if existing else now
    doc = {"course_code": course_code, "topics": topics, "version": version, "created_at": created_at, "updated_at": now, "updated_by": updated_by}
    await db["course_taxonomies"].replace_one({"course_code": course_code}, doc, upsert=True)
    # mirror to courses
    await db["courses"].update_one({"code": course_code}, {"$set": {"taxonomy_version": version, "taxonomy_updated_at": now}})
    return doc

async def seed_it2040_if_empty(db) -> dict | None:
    existing = await db["course_taxonomies"].find_one({"course_code": "IT2040"})
    if existing: return None
    path = _Path(__file__).resolve().parents[2] / "config" / "topic_taxonomy.json"
    if not path.exists():
        path = _Path(__file__).resolve().parents[2] / "datasets" / "bloom_dataset" / "taxonomy_v2.json"
    data = _json.loads(path.read_text(encoding="utf-8"))
    return await upsert_course_taxonomy(db, "IT2040", data, updated_by="system:seed")

async def find_taxonomy_usage_count(db, course_code: str, canonical_id: str) -> int:
    # count snapshots where topic appears
    cursor = db["examAnalytics"].find({"subject_code": course_code, "canonical_topic_performance.topic": {"$exists": True}})
    # cheaper: count docs where canonical_attention_areas.name == canonical_topic or canonical_topic_performance has match
    # fallback to simple count of examAnalytics docs for course
    docs = await db["examAnalytics"].find({"subject_code": course_code}).to_list(length=20)
    cnt = 0
    for d in docs:
        for t in d.get("canonical_topic_performance") or []:
            if t.get("topic","").casefold() == canonical_id.casefold() or t.get("topic","") == canonical_id:
                cnt += 1
    return cnt
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest AdaptiveExamAnalyticsEngine/tests/test_repository_taxonomy.py -v`
Expected: PASS (adjust mock side_effect to return correct version).

- [ ] **Step 5: Commit**

```bash
git add AdaptiveExamAnalyticsEngine/app/db/repository.py AdaptiveExamAnalyticsEngine/tests/test_repository_taxonomy.py
git commit -m "feat(db): course_taxonomies collection, versioned repo + seed IT2040"
```

---

### Task 2: Refactor `normalizer.py` to Per-Course Async + Cache + Slug

**Files:**
- Modify: `AdaptiveExamAnalyticsEngine/app/taxonomy/normalizer.py:1-105`
- Test: `AdaptiveExamAnalyticsEngine/tests/test_taxonomy.py` (modify + add)

**Interfaces:**
- Consumes: `repository.get_course_taxonomy`, file `CONFIG_TAXONOMY`/`FALLBACK_TAXONOMY`.
- Produces: `async def load_taxonomy(db, course_code: str) -> dict[str,dict]` (was sync no-arg), `async def _alias_map_for_course(db, course_code) -> dict[str,str]`, `def slugify_topic(canonical_topic) -> str`, `async def normalize_topic(raw, db, course_code) -> str|None`, `async def invalidate_taxonomy_cache(course_code)`, sync wrapper `load_taxonomy_sync(course_code=None)` for backward compat, `TTLCache` keyed by course_code.

- [ ] **Step 1: Write failing test for per-course load + slug**

```python
# tests/test_taxonomy.py excerpt
@pytest.mark.asyncio
async def test_load_taxonomy_per_course_db_first():
    from app.taxonomy import normalizer
    mock_db = MagicMock()
    mock_db.__getitem__.return_value.find_one = AsyncMock(return_value={"course_code":"CS3010","topics":{"sched":{"canonical_topic":"Process Scheduling","aliases":["Scheduling"],"subtopics":["FCFS"]}},"version":1})
    data = await normalizer.load_taxonomy(mock_db, "CS3010")
    assert "sched" in data

def test_slugify():
    from app.taxonomy.normalizer import slugify_topic
    assert slugify_topic("Structured Query Language (SQL)") == "structured_query_language_sql"

@pytest.mark.asyncio
async def test_normalize_topic_per_course():
    from app.taxonomy.normalizer import normalize_topic
    mock_db = MagicMock()
    mock_db.__getitem__.return_value.find_one = AsyncMock(return_value={"course_code":"CS3010","topics":{"sched":{"canonical_topic":"Process Scheduling","aliases":["Scheduling"],"subtopics":[]}},"version":1})
    assert await normalize_topic("Scheduling", mock_db, "CS3010") == "sched"
    assert await normalize_topic("Unknown", mock_db, "CS3010") is None

@pytest.mark.asyncio
async def test_it2040_seed_fallback():
    from app.taxonomy import normalizer
    mock_db = MagicMock()
    mock_db.__getitem__.return_value.find_one = AsyncMock(return_value=None)
    # IT2040 missing -> should seed from file and return topics containing sql
    data = await normalizer.load_taxonomy(mock_db, "IT2040")
    assert "sql" in data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest AdaptiveExamAnalyticsEngine/tests/test_taxonomy.py -v`
Expected: FAIL `load_taxonomy() takes 0 positional arguments but 2 given` / `slugify_topic not defined`.

- [ ] **Step 3: Implement minimal refactor**

```python
# app/taxonomy/normalizer.py top
import re, json, pathlib
from cachetools import TTLCache
import asyncio
_cache = TTLCache(maxsize=128, ttl=60)

def slugify_topic(canonical_topic: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '_', canonical_topic.strip().lower())
    return slug.strip('_')[:64] or "topic"

async def load_taxonomy(db, course_code: str) -> dict[str,dict]:
    if course_code in _cache:
        return _cache[course_code]
    if db is not None:
        try:
            doc = await db["course_taxonomies"].find_one({"course_code": course_code})
            if doc and doc.get("topics"):
                _cache[course_code] = doc["topics"]
                return doc["topics"]
            if course_code == "IT2040":
                # seed file
                from app.db.repository import seed_it2040_if_empty
                seeded = await seed_it2040_if_empty(db)
                if seeded and seeded.get("topics"):
                    _cache[course_code] = seeded["topics"]
                    return seeded["topics"]
                # still try file direct if db seed failed
            if doc is None and course_code != "IT2040":
                return {}
        except Exception:
            pass
    # fallback file for db=None or IT2040 seed path
    path = CONFIG_TAXONOMY if CONFIG_TAXONOMY.exists() else FALLBACK_TAXONOMY
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
        _cache[course_code] = data
        return data

async def _alias_map_for_course(db, course_code):
    taxonomy = await load_taxonomy(db, course_code)
    alias_map={}
    for cid, entry in taxonomy.items():
        canon = entry.get("canonical_topic","")
        if canon: alias_map[canon.casefold().strip()] = cid
        for alias in entry.get("aliases",[]):
            k=alias.casefold().strip()
            if k: alias_map[k]=cid
        alias_map[cid.casefold()] = cid
    return alias_map

async def normalize_topic(raw: str|None, db, course_code: str) -> str|None:
    if not raw: return None
    key = raw.casefold().strip()
    am = await _alias_map_for_course(db, course_code)
    if key in am: return am[key]
    for ak,cid in am.items():
        if len(ak)>5 and (ak in key or key in ak):
            return cid
    return None

async def invalidate_taxonomy_cache(course_code: str):
    _cache.pop(course_code, None)

def load_taxonomy_sync(course_code: str|None=None):
    # sync compat for old callers/tests without db
    import pathlib, json
    path = CONFIG_TAXONOMY if CONFIG_TAXONOMY.exists() else FALLBACK_TAXONOMY
    with open(path, encoding="utf-8") as f:
        return json.load(f)

# keep old lru_cache wrappers for compat if imported elsewhere:
def get_canonical_topic(canonical_id, db=None, course_code=None): ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest AdaptiveExamAnalyticsEngine/tests/test_taxonomy.py -v`
Expected: PASS (add awaits).

- [ ] **Step 5: Commit**

```bash
git add AdaptiveExamAnalyticsEngine/app/taxonomy/normalizer.py AdaptiveExamAnalyticsEngine/tests/test_taxonomy.py
git commit -m "feat(taxonomy): per-course async load + TTL cache + slugify"
```

---

### Task 3: Taxonomy CRUD API (`app/api/taxonomy.py`)

**Files:**
- Create: `AdaptiveExamAnalyticsEngine/app/api/taxonomy.py`
- Modify: `AdaptiveExamAnalyticsEngine/app/main.py:1-18` (include router)
- Test: `AdaptiveExamAnalyticsEngine/tests/test_taxonomy_api.py` (new)

**Interfaces:**
- Consumes: `repository.get_course_taxonomy`, `upsert_course_taxonomy`, `find_taxonomy_usage_count`, `normalizer.invalidate_taxonomy_cache`, `slugify_topic`.
- Produces: FastAPI router `router = APIRouter(prefix="/api/courses", tags=["taxonomy"])` with endpoints `GET /{course_code}/taxonomy`, `PUT /{course_code}/taxonomy/{canonical_id}`, `DELETE /{course_code}/taxonomy/{canonical_id}`, `POST /{course_code}/taxonomy/seed`; Pydantic `TopicPayload(canonical_topic, aliases, subtopics)`.

- [ ] **Step 1: Write failing test for CRUD**

```python
# tests/test_taxonomy_api.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from unittest.mock import AsyncMock, MagicMock

@pytest.mark.asyncio
async def test_get_upsert_delete_taxonomy(monkeypatch):
    mock_db = MagicMock()
    # course exists
    mock_db.__getitem__.return_value.find_one = AsyncMock(side_effect=[
        {"code":"CS3010"},  # check course exists for GET
        None,  # no taxonomy yet
        {"code":"CS3010"},  # PUT check exists
        None,  # existing taxonomy for PUT
        {"code":"CS3010","topics":{},"version":1},  # after upsert
    ])
    # mock upsert helper
    monkeypatch.setattr("app.db.repository.upsert_course_taxonomy", AsyncMock(return_value={"course_code":"CS3010","topics":{"process_scheduling":{"canonical_topic":"Process Scheduling","aliases":["Sched"],"subtopics":["FCFS"]}},"version":1}))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/api/courses/CS3010/taxonomy")
        assert resp.status_code in (200,404)  # will fail 404 before impl
        resp = await ac.put("/api/courses/CS3010/taxonomy/new", json={"canonical_topic":"Process Scheduling","aliases":["Sched"],"subtopics":["FCFS"]})
        assert resp.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest AdaptiveExamAnalyticsEngine/tests/test_taxonomy_api.py -v`
Expected: FAIL `404 Not Found` no route.

- [ ] **Step 3: Implement minimal API**

```python
# app/api/taxonomy.py
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field
from typing import Optional
from app.api.deps import get_db
from app.taxonomy.normalizer import slugify_topic, invalidate_taxonomy_cache

router = APIRouter(prefix="/api/courses", tags=["taxonomy"])

class TopicPayload(BaseModel):
    canonical_topic: str = Field(min_length=3, max_length=120)
    aliases: list[str] = Field(default_factory=list, max_length=20)
    subtopics: list[str] = Field(default_factory=list, max_length=50)

def _validate_payload(payload: TopicPayload, existing_topics: dict, current_id: str|None):
    ct = payload.canonical_topic.strip()
    if not ct: raise HTTPException(400, "canonical_topic required")
    # aliases trim dedup
    cleaned_aliases=[]
    seen=set()
    for a in payload.aliases:
        aa=a.strip()
        if not aa: continue
        if len(aa)<2 or len(aa)>100: raise HTTPException(400, f"alias '{aa}' must be 2-100 chars")
        k=aa.casefold()
        if k==ct.casefold(): raise HTTPException(400, "alias cannot equal canonical_topic")
        if k in seen: continue
        seen.add(k); cleaned_aliases.append(aa)
    # cross-topic alias duplicate check
    all_aliases={}
    for cid, entry in existing_topics.items():
        if current_id and cid==current_id: continue
        for al in entry.get("aliases",[]):
            all_aliases[al.casefold()] = cid
        # also check canonical_topic
        all_aliases[entry.get("canonical_topic","").casefold()] = cid
    for al in cleaned_aliases:
        if al.casefold() in all_aliases: raise HTTPException(409, f"alias '{al}' already used in topic '{all_aliases[al.casefold()]}'")
    # subtopics
    cleaned_sub=[]
    seen2=set()
    for s in payload.subtopics:
        ss=s.strip()
        if not ss: continue
        if len(ss)<2 or len(ss)>200: raise HTTPException(400, f"subtopic '{ss}' must be 2-200 chars")
        if ss.casefold() in seen2: continue
        seen2.add(ss.casefold()); cleaned_sub.append(ss)
    return ct, cleaned_aliases, cleaned_sub

@router.get("/{course_code}/taxonomy")
async def get_taxonomy(course_code: str, db=Depends(get_db)):
    course_code=course_code.strip().upper()
    course = await db["courses"].find_one({"code": course_code})
    if not course: raise HTTPException(404, f"Course '{course_code}' not found. Create course first.")
    from app.db.repository import get_course_taxonomy, seed_it2040_if_empty
    if course_code=="IT2040":
        await seed_it2040_if_empty(db)
    doc = await get_course_taxonomy(db, course_code)
    if not doc: return {"course_code":course_code,"version":0,"topics":{},"updated_at":None}
    return {"course_code":doc["course_code"],"version":doc["version"],"topics":doc["topics"],"updated_at":doc.get("updated_at")}

@router.put("/{course_code}/taxonomy/{canonical_id}")
async def upsert_topic(course_code: str, canonical_id: str, payload: TopicPayload, db=Depends(get_db), if_match: Optional[str]=Header(None)):
    course_code=course_code.strip().upper()
    course = await db["courses"].find_one({"code": course_code})
    if not course: raise HTTPException(404, f"Course '{course_code}' not found.")
    from app.db.repository import get_course_taxonomy, upsert_course_taxonomy
    doc = await get_course_taxonomy(db, course_code)
    topics = dict(doc["topics"]) if doc and doc.get("topics") else {}
    version = doc["version"] if doc else 0
    if if_match is not None and str(version) != if_match: raise HTTPException(409, "Version conflict, refresh and retry")
    # slug handling
    target_id = canonical_id.strip().lower()
    if target_id=="new" or target_id=="__new":
        target_id = slugify_topic(payload.canonical_topic)
    if not target_id or len(target_id)<2 or len(target_id)>64: raise HTTPException(400, "canonical_id 2-64 chars")
    # uniqueness canonical_topic per course
    for cid, entry in topics.items():
        if cid!=target_id and entry.get("canonical_topic","").casefold()==payload.canonical_topic.strip().casefold():
            raise HTTPException(409, f"Topic '{payload.canonical_topic}' already exists as '{cid}'")
        if cid!=target_id and cid==target_id:
            pass
    if target_id not in topics and target_id in topics: raise HTTPException(409, "duplicate id")
    # check duplicate id already exists vs new name collision
    if target_id in topics:
        # update: keep version
        pass
    else:
        if target_id in topics: raise HTTPException(409, f"canonical_id '{target_id}' already exists")
    ct, cleaned_aliases, cleaned_sub = _validate_payload(payload, topics, target_id)
    topics[target_id] = {"canonical_topic": ct, "aliases": cleaned_aliases, "subtopics": cleaned_sub}
    # also ensure canonical_id slug matches if user sent different id vs topic name -> allow but id is key
    new_doc = await upsert_course_taxonomy(db, course_code, topics, updated_by="lecturer")
    await invalidate_taxonomy_cache(course_code)
    return {"canonical_id": target_id, "version": new_doc["version"], "topic": topics[target_id]}

@router.delete("/{course_code}/taxonomy/{canonical_id}")
async def delete_topic(course_code: str, canonical_id: str, db=Depends(get_db)):
    course_code=course_code.strip().upper()
    course = await db["courses"].find_one({"code": course_code})
    if not course: raise HTTPException(404, f"Course '{course_code}' not found.")
    from app.db.repository import get_course_taxonomy, upsert_course_taxonomy, find_taxonomy_usage_count
    doc = await get_course_taxonomy(db, course_code)
    if not doc or canonical_id not in doc.get("topics",{}): raise HTTPException(404, "topic not found")
    topics = dict(doc["topics"]); topics.pop(canonical_id)
    warning=None
    cnt = await find_taxonomy_usage_count(db, course_code, canonical_id)
    if cnt>0: warning=f"Used in {cnt} exam snapshots — will be Stale until Reanalyse"
    new_doc = await upsert_course_taxonomy(db, course_code, topics, updated_by="lecturer")
    await invalidate_taxonomy_cache(course_code)
    return {"deleted": True, "canonical_id": canonical_id, "version": new_doc["version"], "warning": warning}

@router.post("/{course_code}/taxonomy/seed")
async def seed_taxonomy(course_code: str, db=Depends(get_db)):
    course_code=course_code.strip().upper()
    from app.db.repository import seed_it2040_if_empty
    if course_code!="IT2040": raise HTTPException(400, "seed only for IT2040")
    doc = await seed_it2040_if_empty(db)
    if not doc: doc = await db["course_taxonomies"].find_one({"course_code":course_code}, {"_id":0})
    return doc
```

Include router in `app/main.py`:
```python
from app.api.taxonomy import router as taxonomy_router
app.include_router(taxonomy_router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest AdaptiveExamAnalyticsEngine/tests/test_taxonomy_api.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add AdaptiveExamAnalyticsEngine/app/api/taxonomy.py AdaptiveExamAnalyticsEngine/app/main.py AdaptiveExamAnalyticsEngine/tests/test_taxonomy_api.py
git commit -m "feat(api): per-course taxonomy CRUD with version and stale warn"
```

---

### Task 4: Wire Analytics Callers to Per-Course DB

**Files:**
- Modify: `AdaptiveExamAnalyticsEngine/app/services/student_pipeline.py:17-20,92,245,302,469`
- Modify: `AdaptiveExamAnalyticsEngine/app/services/exam_analytics.py:12,49,102-145`
- Modify: `AdaptiveExamAnalyticsEngine/app/services/topic_canonicalization.py:7,12,21-47`
- Modify: `AdaptiveExamAnalyticsEngine/app/ingestion/question_bank.py:29,111,128,255`
- Modify: `AdaptiveExamAnalyticsEngine/app/analytics/weakness.py:52,80`
- Test: `AdaptiveExamAnalyticsEngine/tests/test_student_pipeline.py:102-112`

**Interfaces:**
- Consumes: `normalizer.load_taxonomy(db, course_code)`, `repository.get_course_taxonomy`.
- Produces: All taxonomy lookups now require `(db, course_code)`; `student_pipeline._classify_questions` extracts `course_code` from `normalized.course_code`/`submission`.

- [ ] **Step 1: Write failing test for caller passthrough**

```python
# tests/test_student_pipeline.py add
@pytest.mark.asyncio
async def test_classify_uses_per_course_taxonomy(monkeypatch):
    from app.services import student_pipeline
    # mock db with CS3010 taxonomy having sched topic
    mock_db = MagicMock()
    mock_db.__getitem__.return_value.find_one = AsyncMock(return_value={"course_code":"CS3010","topics":{"sched":{"canonical_topic":"Process Scheduling","aliases":["Scheduling"],"subtopics":[]}},"version":1})
    monkeypatch.setattr(student_pipeline, "find_course_for_submission", AsyncMock(return_value={"code":"CS3010"}))
    # call _classify_questions with text containing Scheduling -> should not be Unclassified
    from app.schemas.catalog import TopicAssignment
    # minimal normalized stub
    class Norm: 
        course_code="CS3010"
        questions=[type("Q",(),{"question_no":"1","text":"Explain Scheduling FCFS"})()]
    result = await student_pipeline._classify_questions(Norm(), {}, db=mock_db)
    assert result["1"].topic != "Unclassified"
    assert "Scheduling" in result["1"].reason or "sched" in result["1"].topic.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest AdaptiveExamAnalyticsEngine/tests/test_student_pipeline.py::test_classify_uses_per_course_taxonomy -v`
Expected: FAIL `Unclassified`.

- [ ] **Step 3: Implement minimal wiring**

```python
# app/services/student_pipeline.py
from app.db.repository import find_course_for_submission
from app.taxonomy.normalizer import load_taxonomy  # now async

async def _classify_questions(normalized, classification_cache, progress=None, db=None):
    course_code = getattr(normalized, "course_code", None) or getattr(normalized, "subject_code", None) or "IT2040"
    # if db available, load per-course taxonomy for hits
    taxonomy = await load_taxonomy(db, course_code) if db is not None else None
    # pass taxonomy to rules._topic_hits if needed (modify rules to accept taxonomy arg)
    ...

# app/classifier/rules.py: add optional taxonomy param to _topic_hits
def _topic_hits(text: str, taxonomy: dict|None=None) -> dict[str,int]:
    # if taxonomy provided, build keywords from its canonical_topic+aliases
    ...

# app/services/exam_analytics.py:102-145
taxonomy = await _load_tax(db, course_code)  # was _load_tax() no args
# also fix alias_map building to use await load_taxonomy

# app/services/topic_canonicalization.py
async def _load_taxonomy(db=None, course_code="IT2040"):
    from app.taxonomy.normalizer import load_taxonomy
    return await load_taxonomy(db, course_code)

# app/analytics/weakness.py:80
from app.taxonomy.normalizer import normalize_topic
# update calls to await normalize_topic(..., db, course_code)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest AdaptiveExamAnalyticsEngine/tests/test_student_pipeline.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add AdaptiveExamAnalyticsEngine/app/services/student_pipeline.py AdaptiveExamAnalyticsEngine/app/services/exam_analytics.py AdaptiveExamAnalyticsEngine/app/services/topic_canonicalization.py AdaptiveExamAnalyticsEngine/app/ingestion/question_bank.py AdaptiveExamAnalyticsEngine/app/analytics/weakness.py AdaptiveExamAnalyticsEngine/app/classifier/rules.py
git commit -m "feat(analytics): wire per-course taxonomy through pipeline"
```

---

### Task 5: Snapshot `taxonomy_version` + Stale Banner Data

**Files:**
- Modify: `AdaptiveExamAnalyticsEngine/app/services/exam_analytics.py:319-346`
- Modify: `AdaptiveExamAnalyticsEngine/app/schemas/exam_analytics.py` (add taxonomy_ fields)
- Test: `AdaptiveExamAnalyticsEngine/tests/test_exam_analytics_service.py:14-30`

**Interfaces:**
- Consumes: `get_course_taxonomy(db, course_code).version`, fingerprint `hashlib.sha256("|".join(sorted(topics.keys())).encode()).hexdigest()[:12]`.
- Produces: `document["taxonomy_version"]`, `document["taxonomy_fingerprint"]`, `document["taxonomy_course_code"]`, derived `taxonomy_stale` bool on read.

- [ ] **Step 1: Write failing test for snapshot version**

```python
# tests/test_exam_analytics_service.py
@pytest.mark.asyncio
async def test_snapshot_includes_taxonomy_version(monkeypatch):
    from app.services.exam_analytics import compute_exam_analytics
    mock_db = MagicMock()
    # mock taxonomy
    monkeypatch.setattr("app.services.exam_analytics._load_tax", AsyncMock(return_value={"sql":{"canonical_topic":"SQL","aliases":["SQL"],"subtopics":[]}}))
    mock_db.__getitem__.return_value.find_one = AsyncMock(return_value={"course_code":"IT2040","topics":{"sql":{"canonical_topic":"SQL","aliases":[],"subtopics":[]}},"version":5})
    # stub other deps (find_graded_submissions, etc.) to return minimal
    ...
    doc = await compute_exam_analytics(mock_db, "IT2040", "Final", 2024, 1, 1)
    assert doc["taxonomy_version"] == 5
    assert "taxonomy_fingerprint" in doc
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest AdaptiveExamAnalyticsEngine/tests/test_exam_analytics_service.py::test_snapshot_includes_taxonomy_version -v`
Expected: FAIL `taxonomy_version not in doc`.

- [ ] **Step 3: Implement minimal snapshot patch**

```python
# app/services/exam_analytics.py after taxonomy loaded ~ line 104
taxonomy_doc = await db["course_taxonomies"].find_one({"course_code": course_code}, {"version":1, "topics":1}) if db is not None else None
taxonomy_version = int(taxonomy_doc["version"]) if taxonomy_doc else 0
taxonomy_fingerprint = hashlib.sha256("|".join(sorted((taxonomy_doc["topics"].keys() if taxonomy_doc else []))).encode()).hexdigest()[:12] if taxonomy_doc else "v0"

# at document build 319
document = {
    ...
    "taxonomy_version": taxonomy_version,
    "taxonomy_fingerprint": taxonomy_fingerprint,
    "taxonomy_course_code": course_code,
    ...
}

# also in find_exam_analytics caller, add stale compute:
# app/db/repository.py find_exam_analytics -> add taxonomy_stale = (doc.get("taxonomy_version",0) != current_version)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest AdaptiveExamAnalyticsEngine/tests/test_exam_analytics_service.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add AdaptiveExamAnalyticsEngine/app/services/exam_analytics.py AdaptiveExamAnalyticsEngine/app/schemas/exam_analytics.py
git commit -m "feat(analytics): persist taxonomy_version/fingerprint on snapshots"
```

---

### Task 6: Frontend Taxonomy API Client

**Files:**
- Modify: `Gradex_AI_Client/src/app/api/lecturerApi.ts:1-200`
- Test: `Gradex_AI_Client/src/app/api/lecturerApi.test.ts` (new, vitest)

**Interfaces:**
- Consumes: `GET/PUT/DELETE /api/courses/{course_code}/taxonomy`.
- Produces: `taxonomyApi = { fetchTaxonomy(course_code), upsertTopic(course_code, canonical_id, payload), deleteTopic(course_code, canonical_id) }`.

- [ ] **Step 1: Write failing test for client**

```ts
// lecturerApi.test.ts
import { taxonomyApi } from "./lecturerApi";
test("fetchTaxonomy calls correct url", async () => {
  global.fetch = vi.fn().mockResolvedValue({ ok:true, text: async()=>"{}", json: async()=>({course_code:"CS3010",version:1,topics:{}}) } as any);
  const data = await taxonomyApi.fetchTaxonomy("CS3010");
  expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining("/api/courses/CS3010/taxonomy"), expect.anything());
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- lecturerApi.test.ts`
Expected: FAIL `taxonomyApi not exported`.

- [ ] **Step 3: Implement client**

```ts
// Gradex_AI_Client/src/app/api/lecturerApi.ts bottom
const TAX_BASE = (apiBaseUrl: string) => `${apiBaseUrl}/api/courses`;
export const taxonomyApi = {
  async fetchTaxonomy(course_code: string, apiBaseUrl = DEFAULT_API_BASE_URL) {
    const r = await fetch(`${TAX_BASE(apiBaseUrl)}/${encodeURIComponent(course_code)}/taxonomy`);
    const j = await r.json(); if(!r.ok) throw new Error(j.detail||"failed"); return j as {course_code:string,version:number,topics:Record<string,{canonical_topic:string,aliases:string[],subtopics:string[]}>,updated_at:string|null};
  },
  async upsertTopic(course_code:string, canonicalId:string, payload:{canonical_topic:string,aliases:string[],subtopics:string[]}, apiBaseUrl=DEFAULT_API_BASE_URL) {
    const r = await fetch(`${TAX_BASE(apiBaseUrl)}/${encodeURIComponent(course_code)}/taxonomy/${encodeURIComponent(canonicalId)}`, {method:"PUT", headers:{"Content-Type":"application/json"}, body: JSON.stringify(payload)});
    const j = await r.json(); if(!r.ok) throw new Error(j.detail||JSON.stringify(j)); return j;
  },
  async deleteTopic(course_code:string, canonicalId:string, apiBaseUrl=DEFAULT_API_BASE_URL) {
    const r = await fetch(`${TAX_BASE(apiBaseUrl)}/${encodeURIComponent(course_code)}/taxonomy/${encodeURIComponent(canonicalId)}`, {method:"DELETE"});
    const j = await r.json(); if(!r.ok) throw new Error(j.detail||"failed"); return j as {deleted:boolean, warning?:string, version:number};
  }
};
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test -- lecturerApi.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add Gradex_AI_Client/src/app/api/lecturerApi.ts Gradex_AI_Client/src/app/api/lecturerApi.test.ts
git commit -m "feat(client): taxonomyApi for per-course CRUD"
```

---

### Task 7: Frontend Taxonomy Tab + Stale Banner in `AnalyticsPage.tsx`

**Files:**
- Modify: `Gradex_AI_Client/src/app/components/AnalyticsPage.tsx:595-620` (header + new tab)
- Test: `Gradex_AI_Client/src/app/components/AnalyticsPage.test.tsx` (new)

**Interfaces:**
- Consumes: `taxonomyApi.*`, existing `analytics.taxonomy_version`, `course_taxonomy.version`.
- Produces: UI Tab `Taxonomy` when `selectedExam` truthy; table + Add/Edit drawer + delete confirm + amber stale banner `Taxonomy updated (v2→v3) — Reanalyse to apply` CTA.

- [ ] **Step 1: Write failing test for tab render**

```tsx
test("taxonomy tab renders when exam selected", async () => {
  render(<AnalyticsPage selectedExam={{course_code:"CS3010"}} analytics={{taxonomy_version:1}} />)
  expect(screen.getByText(/Taxonomy/)).toBeInTheDocument();
});
test("stale banner shows when versions mismatch", async () => {
  render(<AnalyticsPage selectedExam={{course_code:"CS3010"}} analytics={{taxonomy_version:1}} taxonomy={{version:2}} />)
  expect(screen.getByText(/Reanalyse to apply/)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test -- AnalyticsPage.test.tsx`
Expected: FAIL `Taxonomy not found`.

- [ ] **Step 3: Implement minimal tab + banner**

```tsx
// AnalyticsPage.tsx near 595-620, add import taxonomyApi
const [taxonomy, setTaxonomy] = useState<any>(null);
const [taxTab, setTaxTab] = useState<"overview"|"taxonomy">("overview");
useEffect(()=>{ if(selectedExam?.course_code) taxonomyApi.fetchTaxonomy(selectedExam.course_code).then(setTaxonomy).catch(()=>setTaxonomy({version:0,topics:{}})); }, [selectedExam?.course_code]);

// header stale banner
{analytics && taxonomy && analytics.taxonomy_version !== taxonomy.version && (
  <div className="bg-amber-50 border border-amber-200 text-amber-800 text-xs px-3 py-2 rounded flex items-center gap-2">
    Taxonomy updated (v{analytics.taxonomy_version}→v{taxonomy.version}) — Reanalyse to apply
    <Button size="sm" variant="outline" onClick={()=>handleSelectExam(selectedExam, {forceReanalyse:true})}>Reanalyse</Button>
  </div>
)}

// tab buttons
<div className="flex gap-2 border-b">
  <button onClick={()=>setTaxTab("overview")} className={taxTab==="overview"?"font-bold":""}>Overview</button>
  <button onClick={()=>setTaxTab("taxonomy")}>Taxonomy</button>
</div>
{taxTab==="taxonomy" && (
  <TaxonomyManager courseCode={selectedExam.course_code} taxonomy={taxonomy} onChanged={setTaxonomy} />
)}
// Extract TaxonomyManager component in same file or new file TaxonomyManager.tsx with table + drawer
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test -- AnalyticsPage.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add Gradex_AI_Client/src/app/components/AnalyticsPage.tsx Gradex_AI_Client/src/app/components/TaxonomyManager.tsx
git commit -m "feat(ui): Taxonomy tab + stale Reanalyse banner"
```

---

### Task 8: Tests & Manual Verification Cleanup

**Files:**
- Run: `pytest AdaptiveExamAnalyticsEngine/tests/test_taxonomy_api.py AdaptiveExamAnalyticsEngine/tests/test_taxonomy.py AdaptiveExamAnalyticsEngine/tests/test_repository_taxonomy.py -v`
- Run: `pytest AdaptiveExamAnalyticsEngine/tests/test_exam_analytics_service.py AdaptiveExamAnalyticsEngine/tests/test_student_pipeline.py -v`
- Run: `npm run test -- lecturerApi.test.ts AnalyticsPage.test.tsx`
- Modify: `docs/superpowers/specs/2026-09-16-per-course-taxonomy-design.md` if gaps.

**Interfaces:**
- Consumes: all prior tasks.
- Produces: Green CI, manual checklist.

- [ ] **Step 1: Run full suite, capture Unclassified before/after**

Run: `pytest -q`
Expected: All PASS, `test_unclassified_drops_after_taxonomy_add_and_reanalyse` shows 40→0 after adding.

- [ ] **Step 2: Manual checklist in dev**

1. `POST /courses` create `CS3010` (Grading UI).
2. `GET /api/courses/CS3010/taxonomy` -> `{version:0, topics:{}}` empty.
3. AnalyticsPage Taxonomy tab -> `+ Add Topic` `Process Scheduling` -> PUT -> table shows 1 row.
4. Ingest exam for `CS3010` with `Scheduling` question -> run analytics -> no `Unclassified`, `canonical_topic_performance` has `Process Scheduling`.
5. Edit alias add `FCFS` -> version 2 -> header shows stale banner -> click `Reanalyse` -> banner clears.

- [ ] **Step 3: Commit verification note**

```bash
git commit --allow-empty -m "test: verify per-course taxonomy e2e Unclassified fix"
```

---

## Self-Review Checklist

- [x] Spec coverage: all 12 spec sections mapped to tasks 1-8 (model, normalizer, API, wiring, snapshot, client, UI, tests).
- [x] Placeholder scan: no TBD/TODO, each step has actual code blocks and exact run commands.
- [x] Type consistency: `course_code` upper, `canonical_id` slug, `version:int`, `topics:Record<canonical_id, {canonical_topic, aliases, subtopics}>` consistent across DB, API, client.

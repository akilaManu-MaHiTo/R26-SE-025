# Per-Course Taxonomy Design — Lecturer-Managed DBMS Taxonomy in MongoDB

**Date:** 2026-09-16
**Status:** Approved (brainstorming Q1-Q5)
**Scope:** Move taxonomy from file (`config/topic_taxonomy.json`) to per-course MongoDB, mapped to `courses` collection.

## 1. Context & Problem

- Today taxonomy is global file `AdaptiveExamAnalyticsEngine/config/topic_taxonomy.json:1` (11 DBMS topics) loaded via `app/taxonomy/normalizer.py:19-30`. Fallback `datasets/bloom_dataset/taxonomy_v2.json:1`. Displayed as `TOPICS` in `app/analytics/taxonomy.py:1`.
- `courses` collection (`GradingEngine/app/main.py:285`, `AdaptiveExamAnalyticsEngine/app/db/repository.py:142`) only has `{code, name, description}` — no taxonomy link.
- Classifier `app/classifier/rules.py:78` + `app/services/student_pipeline.py:56` forces `Unclassified` for non-DBMS or no keyword hit. Result: `AdaptiveExamAnalyticsEngine/app/services/exam_analytics.py:221` reports `Unclassified: 40 attempts at 63.38% — review topic assignment`.
- Lecturers cannot fix Unclassified without code change.

**Goal:** Lecturer (via Analytics dashboard) can Add/Remove/Edit taxonomy per `course_code`, persisted in MongoDB, versioned, with soft stale until Reanalyse.

**Decisions from brainstorming:**
- Q1=1 Per-course DB as primary, seeded from file, empty for new courses until lecturer adds.
- Q2=A Full control: `canonical_topic` + `aliases[]` + `subtopics[]`.
- Q3=2 UI inside `AdaptiveExamAnalyticsEngine` Analytics dashboard only.
- Q4=1 Soft — mark stale, prompt Reanalyse (do not auto-delete snapshots).
- Q5= Correct — warn on delete if used but allow; enforce unique `canonical_id`/`canonical_topic` per course case-insensitive.

## 2. Architecture

```
[Gradex_AI_Client AnalyticsPage.tsx] --GET/PUT/DELETE--> [AdaptiveExamAnalyticsEngine FastAPI app/api/taxonomy.py]
                                                        |
                                                        v
                                          [MongoDB course_taxonomies + courses.taxonomy_version]
                                                        |
                    [app/taxonomy/normalizer.py load_taxonomy(db, course_code)] <-- DB first, file seed fallback
                                                        |
         [app/services/student_pipeline.py]  [app/services/exam_analytics.py]  [app/services/topic_canonicalization.py]
                                                        |
                                          [compute_exam_analytics -> examAnalytics/analytics_snapshots with taxonomy_version]
```

**New collection:** `course_taxonomies` (not embedded in `courses` — keeps responsibility separate, avoids bloat).

## 3. Data Model

### 3.1 `course_taxonomies`

```json
{
  "course_code": "IT2040",
  "topics": {
    "sql": {
      "canonical_topic": "Structured Query Language (SQL)",
      "aliases": ["SQL", "SQL Queries and Triggers", "SQL Queries and Triggers in Database Management Systems"],
      "subtopics": ["DDL – CREATE TABLE and Constraints", "DML – INSERT, DELETE, UPDATE"]
    }
  },
  "version": 3,
  "created_at": "2026-09-16T10:00:00Z",
  "updated_at": "2026-09-16T12:00:00Z",
  "updated_by": "lecturer@sliit.lk | system:seed"
}
```

- `course_code` unique index `uniq_course_taxonomies_course_code` (`{course_code:1}` unique). Added in `app/db/repository.py:27`.
- `topics` key = `canonical_id` = slug of `canonical_topic` lower, alphanumeric+underscore, e.g. `structured_query_language_sql` or keep existing ids (`intro_dbms`, `sql`, etc.) — slugify helper shared with validation.
- `version` int increment on every write, starts at 1 on seed.

### 3.2 `courses` patch

Add optional fields to document created in `GradingEngine/app/main.py:308`:

```json
{
  "code": "IT2040",
  "name": "Database Management Systems",
  "description": "...",
  "taxonomy_version": 3,
  "taxonomy_updated_at": "2026-09-16T12:00:00Z"
}
```

Mirrored from `course_taxonomies.version` for fast stale check in `repository.py:list_all_exams:439` without extra lookup.

### 3.3 `examAnalytics` / `analytics_snapshots` patch

Add on snapshot creation in `app/services/exam_analytics.py:319`:

```json
{
  "taxonomy_version": 3,
  "taxonomy_fingerprint": "sha256(sorted canonical_ids)",
  "taxonomy_course_code": "IT2040"
}
```

Legacy snapshots without field = `v0` (treated as stale).

## 4. Backend

### 4.1 `app/taxonomy/normalizer.py` refactor

- Signature change: `async def load_taxonomy(db, course_code: str) -> dict[str, dict]` and `async def get_alias_map(db, course_code)`.
- Logic:
  1. If `db is None` -> fallback to file `_taxonomy_path()` (for tests/scripts offline).
  2. Try `db["course_taxonomies"].find_one({"course_code": course_code})`.
  3. If found -> return `doc["topics"]`.
  4. If not found and `course_code == "IT2040"` -> load `CONFIG_TAXONOMY` file, upsert as seed `version=1, updated_by="system:seed"`, return it.
  5. If not found and other course -> return `{}`.
- Cache: replace `@lru_cache(maxsize=1)` with `cachetools.TTLCache(maxsize=128, ttl=60)` keyed by `course_code`. Add `async def invalidate_taxonomy_cache(course_code)`.
- Keep `normalize_topic(raw, course_code, db)` signature requiring `course_code` for alias map; substring fallback (`len(alias)>5`) unchanged `normalizer.py:72`.
- Preserve `validate_topic_coverage()`, `reload_cache()` compat (now per-course).

Callers updated to pass `db` + `course_code`:
- `app/services/student_pipeline.py:92,245,302` (needs `db` from `ensure_student_analytics` / `compute_exam_analytics`)
- `app/services/exam_analytics.py:106` (already has `db`, `course_code`)
- `app/services/topic_canonicalization.py:12`
- `app/ingestion/question_bank.py:111`
- `app/analytics/weakness.py:80`

### 4.2 New API `app/api/taxonomy.py`

Router prefix `/api/courses/{course_code}/taxonomy` included in `app/main.py:17`.

| Method | Path | Body | Resp | Notes |
|--------|------|------|------|-------|
| GET | `/{course_code}/taxonomy` | — | `{course_code, version, topics, updated_at, stale?}` | 404 if course not in `courses` |
| PUT | `/{course_code}/taxonomy/{canonical_id}` | `{canonical_topic, aliases[], subtopics[]}` | `{canonical_id, version}` | Create/update, slugify if `canonical_id=="new"`, 409 dup, inc version, invalidate cache, update `courses.taxonomy_version` |
| DELETE | `/{course_code}/taxonomy/{canonical_id}` | — | `{deleted:true, warning?:string, version}` | Warning if `canonical_id` found in `examAnalytics.canonical_topic_performance` for course, allow delete, inc version |
| POST | `/{course_code}/taxonomy/seed` | — | seeded doc | Admin/internal, seed IT2040 only |

Validation:
- `canonical_topic` required, trimmed, 3-120 chars, unique per course casefold.
- `canonical_id` slug: `re.sub(r'[^a-z0-9]+','_', canonical_topic.lower()).strip('_')`, 2-64 chars, unique per course. If collision -> 409.
- `aliases[]` array 0-20, each trimmed, dedup casefold, len 2-100, cannot equal canonical_topic casefold, cannot duplicate across topics in same course (409).
- `subtopics[]` array 0-50, each trimmed, dedup, 2-200 chars.
- Course must exist: check `db["courses"].find_one({"code": course_code})` else 404 `Create course first via POST /courses`.
- Optimistic concurrency optional: accept `If-Match: version` header, 409 if mismatch.

Side effects on PUT/DELETE:
- `course_taxonomies.updateOne` inc `version`, set `updated_at`, `updated_by`.
- `courses.updateOne({"code": course_code}, {"$set": {"taxonomy_version": new_version, "taxonomy_updated_at": now}})`.
- `invalidate_taxonomy_cache(course_code)`.

### 4.3 Stale handling

- On GET taxonomy, compute `stale = course_taxonomies.version != examAnalytics.taxonomy_version` for latest snapshot.
- Frontend shows banner; backend does not auto-delete snapshots (Q4=1).

## 5. Frontend

**File:** `Gradex_AI_Client/src/app/components/AnalyticsPage.tsx` + `Gradex_AI_Client/src/app/api/lecturerApi.ts:170`

- Add `taxonomyApi` object: `fetchTaxonomy(course_code)`, `upsertTopic(course_code, canonical_id, payload)`, `deleteTopic(course_code, canonical_id)`, `seedTaxonomy(course_code)`.
- New tab `Taxonomy` in `AnalyticsPage.tsx` when `selectedExam` set. Route param `?tab=taxonomy`.
- Table columns: `Topic (canonical_topic) | ID | Aliases (chips, tooltip full) | Subtopics (count, expand) | Actions`.
- Empty state for new courses: "No taxonomy yet — add first topic. Unclassified questions will appear until you add topics."
- Add/Edit: Drawer/Dialog with inputs `canonical_topic`, `aliases (Creatable Select)`, `subtopics (sortable list + add)`, live slug preview, validation messages (duplicate 409 from API).
- Delete: Confirm modal, show `warning.usedInN` if returned.
- Stale banner at top of exam analytics header: `Unclassified: 40 attempts...` existing plus `Taxonomy updated (v2→v3) — Reanalyse to apply` CTA linking to `POST /api/lecturers/exams/{course_code}/{session_name}/analytics/reanalyse` (`lecturer.py:205`).
- No change to `Gradex_AI_Client/src/app/components/LectureMaterialsPanel.tsx` or `GradingEngine` course UI.

## 6. Migration & Backward Compatibility

- Migration function `seed_it2040_if_empty(db)` called lazily on first `GET /taxonomy/IT2040` and at app startup (`app/db/repository.py:create_indexes` hook).
- If `course_taxonomies` empty: load `config/topic_taxonomy.json`, upsert `IT2040` `version=1`.
- Other collections (`CS3010`, `SE3040`) remain absent until PUT (intentionally empty).
- `load_taxonomy(db=None)` keeps file fallback for `tests/test_taxonomy.py` and offline scripts.
- Legacy `examAnalytics` docs without `taxonomy_version` treated as `v0` -> stale immediately after first taxonomy edit (forces reanalyse, desired to fix Unclassified).

## 7. Data Flow Example

1. Lecturer creates `CS3010` via `POST /courses` (Grading UI).
2. Lecturer navigates Analytics -> `CS3010` -> Taxonomy tab -> `+ Add Topic` `canonical_topic="Process Scheduling"`, `aliases=["Scheduling"]`, `subtopics=["FCFS","SJF"]` -> `PUT /courses/CS3010/taxonomy/process_scheduling`.
3. DB `course_taxonomies{CS3010} version=1`, `courses.taxonomy_version=1`, cache invalidated.
4. Next exam grading for `CS3010` calls `load_taxonomy(db, "CS3010")` -> returns new topics, `_topic_hits` matches `scheduling`, no longer `Unclassified`.
5. If exam already analyzed before step 2, it shows stale banner until lecturer clicks Reanalyse.

## 8. Error Handling

| Case | Code | Detail |
|------|------|--------|
| Course not exist | 404 | `Course 'CS3010' not found. Create course first.` |
| Duplicate canonical_id/topic/alias | 409 | `Topic 'SQL' already exists as 'sql'.` |
| Empty canonical_topic | 400 | `canonical_topic required` |
| Invalid aliases/subtopics | 400 | `alias 'x' too short, must be 2-100 chars` |
| Version conflict (If-Match) | 409 | `Version conflict, refresh and retry` |
| DB down | 500 | Fallback to file + log warning, analytics continues |

## 9. Testing

- **Unit** `AdaptiveExamAnalyticsEngine/tests/test_taxonomy.py`: `test_per_course_load`, `test_seed_it2040`, `test_empty_course_returns_empty`, `test_alias_dedup_per_course`, `test_slugify_and_uniqueness`.
- **API** new `tests/test_taxonomy_api.py`: CRUD lifecycle per course, 409 dup, 404 missing course, delete-warn path, version increment, cache invalidate.
- **Analytics** `tests/test_exam_analytics_service.py:14` + `tests/test_student_pipeline.py:102` mocks updated to pass `db`/`course_code`; add `test_unclassified_drops_after_taxonomy_add_and_reanalyse`.
- **Repo** `tests/test_repository.py:375`: add `test_course_taxonomy_upsert_and_version`.
- Manual: Create course, add taxonomy, ingest exam, verify `unclassified_coverage` before/after, check stale banner.

## 10. Alternatives Considered

- **Embed in `courses`** — rejected: doc bloat, mixes concerns, harder indexing.
- **File + patch** — rejected: two sources of truth, cannot support empty courses or full custom per course (Q2=A).
- Chosen **separate collection** is cleanest for per-course versioning and audit.

## 11. Risks & Mitigations

- Risk: Refactor touches 5 callers -> mitigate with sync compat wrapper and per-course TTL cache.
- Risk: Existing snapshots appear stale -> desired; communicate via banner not auto-delete.
- Risk: Lecturers add too many narrow topics -> mitigate with alias/subtopic guidance tooltip.

## 12. Implementation Order (for planning)

1. DB model + repository + migration
2. `normalizer.py` async refactor + compat
3. `taxonomy.py` API CRUD + version + cache
4. Update analytics callers to pass `course_code`/`db`
5. Frontend `taxonomyApi` + `AnalyticsPage` Taxonomy tab + stale banner
6. Tests + manual verification

# Task 3 Report: Taxonomy CRUD API (`app/api/taxonomy.py`)

**Status:** Complete (fix round 1/5)  
**Commits:** f65ad33 `feat(api): per-course taxonomy CRUD with version and stale warn` → <fix commit>  
**Branch:** feat/clean-up-v1.1

## Summary
Implemented per-course taxonomy CRUD FastAPI router at `AdaptiveExamAnalyticsEngine/app/api/taxonomy.py:1-210` and inclusion in `app/main.py:1-20`, with mocked TDD `AdaptiveExamAnalyticsEngine/tests/test_taxonomy_api.py`. Endpoints: `GET /{course_code}/taxonomy`, `PUT /{course_code}/taxonomy/{canonical_id}`, `DELETE /{course_code}/taxonomy/{canonical_id}`, `POST /{course_code}/taxonomy/seed`.

## Interfaces Produced (verbatim)
- `router = APIRouter(prefix="/api/courses", tags=["taxonomy"])` — `app/api/taxonomy.py:9`
- `class TopicPayload(canonical_topic, aliases, subtopics)` — `app/api/taxonomy.py:12-15`
- `GET /{course_code}/taxonomy` — `app/api/taxonomy.py:89-108`
- `PUT /{course_code}/taxonomy/{canonical_id}` — `app/api/taxonomy.py:113-154`
- `DELETE /{course_code}/taxonomy/{canonical_id}` — `app/api/taxonomy.py:157-186`
- `POST /{course_code}/taxonomy/seed` — `app/api/taxonomy.py:189-210`

Consumes: `get_course_taxonomy`, `upsert_course_taxonomy`, `find_taxonomy_usage_count`, `invalidate_taxonomy_cache`, `slugify_topic` (all async mocks).

## Implementation Details
- `TopicPayload`: `canonical_topic: str = Field(...)`, `aliases: list[str] = Field(default_factory=list)`, `subtopics: list[str] = Field(default_factory=list)` — no Pydantic length constraints; all length/duplicate validation done in `_validate_payload` to ensure 400 (not 422).
- `_validate_payload(payload, existing_topics, current_id)`: trims/dedups (casefold), validates canonical 3-120 →400, alias 2-100 & `alias != canonical` →400 & cross-topic alias/canonical duplicate →409, subtopic 2-200 →400, list caps 20/50 →400, canonical vs alias 409 gap: `if ct.casefold() in all_aliases: raise 409`.
- PUT: `course_code.upper()`, 404 course check, `If-Match` string compare →409, slug `new/__new` → `slugify_topic`, canonical_id 2-64 →400, uniqueness canonical_topic casefold →409, case-insensitive id duplicate →409, then `_validate_payload`, `upsert_course_taxonomy`, `await invalidate_taxonomy_cache`.
- DELETE: `canonical_id.strip().lower()` + 2-64 →400, 404 course/topic, case-insensitive topic lookup (`k.casefold()==canonical_id.casefold()`), `find_taxonomy_usage_count` warning if >0, `upsert` + `await invalidate...`, returns `{deleted, canonical_id, version, warning}`.
- GET: `course_code.upper()`, 404, seeds IT2040 via `seed_it2040_if_empty` (try/except), `get_course_taxonomy` → `{course_code, version, topics, updated_at}` with version 0 fallback.
- POST seed: `course_code.upper() != IT2040` →400, `seed_it2040_if_empty` + fallback `get_course_taxonomy` + `db["course_taxonomies"].find_one`, `await invalidate...`.

## TDD Steps Executed
1. Write failing test `tests/test_taxonomy_api.py` (GET 200 empty, PUT via new slug, 404, 409 If-Match, DELETE warning, seed 400/200).
2. Run failing → import errors until router added to `app/main.py`.
3. Implement `app/api/taxonomy.py` per brief.
4. Run passing `pytest tests/test_taxonomy_api.py -v` — 5 passed.
5. Commit f65ad33.

## Test Summary
`pytest AdaptiveExamAnalyticsEngine/tests/test_taxonomy_api.py -v` — 5 passed (get/upsert, 404, version conflict 409, delete warns, seed 400/200). Mocked via `app.db.repository.*` and `app.api.taxonomy.invalidate_taxonomy_cache` (correct patch target).

## Verification
- `pytest -v` 5 passed, `-W error::RuntimeWarning` 0 warnings (correct await + patch target `app.api.taxonomy.invalidate_taxonomy_cache`).
- Manual probes: `PUT {"canonical_topic":"ab"} →400` (was 422), `PUT {"canonical_topic":"DupAlias"} with existing alias dupAlias →409` (was 200), `DELETE /PROCESS_SCHEDULING` case-insensitive →200, `DELETE /a →400`.
- Router included: `app.include_router(taxonomy_router)` without extra prefix (router already has `/api/courses`).

---

## Fix Report (2026-09-16) — Review Findings Addressed (round 1/5)

**Review source:** Task 3 review — Spec conditional ✅ strict ❌ (422 vs 400, canonical vs alias 409 gap) + mock target wrong  
**Base:** f65ad33 **Fix:** taxonomy.py + test_taxonomy_api.py

### Findings Fixed

1. **422 vs 400 — canonical_topic 3-120:** Fixed. `TopicPayload` changed from `Field(min_length=3,max_length=120)` / `max_length=20/50` to `Field(...)` / `default_factory=list` (no Pydantic length constraints). `_validate_payload` already had manual `len(ct) 3-120 →400`; now request `{"canonical_topic":"ab"}` returns 400 not 422. Verified probe `PUT .../new {"canonical_topic":"ab"} →400`.

2. **Canonical vs alias 409 gap:** Fixed. In `_validate_payload` after building `all_aliases` (canon + aliases of other topics casefold), added: `if ct.casefold() in all_aliases: raise HTTPException(409, f"Topic '{ct}' alias already used ...")`. Previously `existing alias dupAlias + new canonical DupAlias →200`; now →409. Verified probe.

3. **DELETE case-sensitive + missing 2-64 validation:** Fixed. DELETE now does `canonical_id = canonical_id.strip().lower()` then `len 2-64 →400` before course lookup, and case-insensitive topic lookup loop `for k in topics_map: if k.casefold()==canonical_id.casefold(): actual_key=k`. Verified `DELETE /PROCESS_SCHEDULING →200` and `DELETE /a →400`.

4. **Test mocks wrong target + RuntimeWarning:** Fixed. Changed all `patch("app.taxonomy.normalizer.invalidate_taxonomy_cache", ...)` to `patch("app.api.taxonomy.invalidate_taxonomy_cache", ...)` (3 occurrences) because `taxonomy.py` does `from app.taxonomy.normalizer import invalidate_taxonomy_cache` — patch must target `app.api.taxonomy`. Existing `await invalidate_taxonomy_cache(...)` retained; `pytest -W error::RuntimeWarning` now 0 warnings, no `coroutine never awaited`.

5. **DELETE extra field `canonical_id`:** Kept spec-compatible; response returns `{"deleted": true, "canonical_id": actual_key, "version": ..., "warning": ...}` — `canonical_id` is optional additive, not breaking spec.

6. **PUT If-Match string compare:** Verified retained `str(version) != str(if_match).strip() →409`. No change needed.

### Verification (Fix)

- `python -m pytest AdaptiveExamAnalyticsEngine/tests/test_taxonomy_api.py -v` — **5 passed in ~1.6s** (previously 5 passed but warning-prone).
- `python -m pytest ... -W error::RuntimeWarning` — 5 passed, 0 RuntimeWarnings.
- Manual probes script (3 probes + DELETE 400): all `ALL PROBES PASSED` (`ab →400`, `DupAlias vs dupAlias →409`, `DELETE case-insensitive →200`, `DELETE /a →400`).
- Diff confirms minimal, spec-aligned changes: TopicPayload Fields, _validate_payload 409, DELETE normalization/validation/lookup, test patch targets.

### Files Changed (Fix)

- Modified: `AdaptiveExamAnalyticsEngine/app/api/taxonomy.py:12-15` (Field constraints removed), `:60-61` (canonical vs alias 409), `:157-186` (DELETE lower + 2-64 + case-insensitive)
- Modified: `AdaptiveExamAnalyticsEngine/tests/test_taxonomy_api.py` (patch targets `app.api.taxonomy.invalidate_taxonomy_cache` ×3)

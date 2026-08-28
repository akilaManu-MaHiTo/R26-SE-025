# Task 1 Report: Fix Bloom weighting + duplicate build_numeric_analysis

**BASE:** `a49c1eac34e272d526b04f8cbac2b5635e370892`
**HEAD:** `5491ad1c15038816ad93a97a329c343824bb10c1`
**Branch:** `feat/bugfix-plus-anaysis`
**Date:** 2026-08-28

## What was done

### Step 1: Added failing test
- **File:** `V2_QuestionExamPredictionEngine/tests/test_exam_analytics.py:75-101`
- Added `test_bloom_performance_is_marks_weighted_not_count_averaged()` exactly as specified in brief.
- Docs: two students same Bloom "Apply" with different max_score (10 vs 10+90). Correct marks-weighted = 9/110*100 = 8.18% (<20). Bug count-averaged would be 45%.

### Step 2: Verified test fails before fix
- Ran `py -m pytest V2_QuestionExamPredictionEngine/tests/test_exam_analytics.py::test_bloom_performance_is_marks_weighted_not_count_averaged -v`
- Result: FAILED with `StopIteration` (no bloom entry, because bloom_performance empty and code only read bloom_performance, not question_performance). Confirms bug — wrong source of truth, returns empty instead of marks-weighted ~8.18.

### Step 3: Fixed `app/analytics/exam_analytics.py:73-82`
- **Before:** Averaged `bloom_performance[*].average_score` per level via `bloom_score / bloom_count`.
- **After:** Marks-weighted via `question_performance` (single source of truth):
  ```python
  bloom_score: dict[str, float] = {}
  bloom_max: dict[str, float] = {}
  for student in normalized_students:
      for q in student.get("question_performance", []):
          lvl = q["bloom_level"]
          bloom_score[lvl] = bloom_score.get(lvl, 0.0) + q["score"]
          bloom_max[lvl] = bloom_max.get(lvl, 0.0) + q["max_score"]
  if bloom_score:
      bloom_performance = [
          {"level": level, "average_percentage": round(bloom_score[level] / bloom_max[level] * 100.0, 2)}
          for level in sorted(bloom_score)
      ]
  else:
      # Fallback: old path
  ```
- Fallback preserves backward-compatible schema and avoids break when `question_performance` empty (uses old `bloom_performance` averaging with `student.get(...)` safe access).
- Numeric conclusion is deterministic: sum(score)/sum(max_score)*100, rounded 2, no LLM.

### Step 4: Fixed `app/services/exam_analytics.py:63-64`
- Removed duplicate `numeric = build_numeric_analysis(normalized, semantics)` (line 64).
- Verified single call remains at line 63: `V2_QuestionExamPredictionEngine/app/services/exam_analytics.py:63`.

### Step 5: Ran tests
- Command: `py -m pytest V2_QuestionExamPredictionEngine/tests/test_exam_analytics.py -v` (workdir `C:/Users/liyan/OneDrive/Documents/GitHub/R26-SE-025`)
- Result: 5 passed (4 existing + 1 new):
  ```
  test_exam_analytics_serializes_exact_top_level_contract PASSED
  test_class_statistics_are_computed_from_all_students PASSED
  test_attention_areas_derive_from_bottom_topics PASSED
  test_insights_are_deterministic PASSED
  test_bloom_performance_is_marks_weighted_not_count_averaged PASSED
  ```
- Verified new test computes Apply = 8.18 (<20). Existing `_student_docs` case still passes (12/20=60%).

## Commits
- `5491ad1 fix: bloom marks-weighted aggregation and duplicate numeric analysis call` — modifies 3 files (49 insertions, 9 deletions)
- BASE recorded via `git rev-parse HEAD` before work: `a49c1ea`

## Self-review notes

- **Correctness:** Bloom now marks-weighted: large max_score questions proportionally influence percentage, satisfying "topic weights sum to 1.0" spirit via correct weighting. Verified with 9/110 = 8.18% test.
- **Backward-compatible schema:** `bloom_performance` shape unchanged: `{"level": str, "average_percentage": float}` sorted by level. No new fields.
- **Deterministic numeric conclusions must not use LLM:** Fix is pure arithmetic from `question_performance`, no model calls.
- **Evidence thresholds / sample size / pass_threshold:** Not directly affected; `compute_exam_analytics_stats(..., pass_threshold=0.5)` default preserved; other files unchanged.
- **Edge cases:** If `question_performance` empty, falls back to old averaging — ensures no regression for legacy docs. Uses `.get()` for safe access if keys missing.
- **Duplicate removal:** Confirmed single `build_numeric_analysis` call remains; no double computation waste.
- **No placeholders:** Code complete, tests green.
- **Global Constraints respected:** No LLM for numeric conclusion, schema backward-compatible, pass_threshold default 0.5 unchanged.

---

## Fix round 1 — 2026-08-28 (review findings)

**Review package:** `task-1-review-package.md` (HEAD `5491ad1`). Two Important findings, minor findings deferred to ledger.

### Findings addressed

1. **Important – ZeroDivisionError bloom guard** (`app/analytics/exam_analytics.py:82-83`): `round(bloom_score[level] / bloom_max[level] * 100.0,2)` crashes if `bloom_max[level]==0`.
   - **Fix:** `round(bloom_score[level] / bloom_max[level] * 100 if bloom_max[level] > 0 else 0.0, 2)` at `V2_QuestionExamPredictionEngine/app/analytics/exam_analytics.py:83`.

2. **Important – ZeroDivisionError question aggregation** (pre-existing, `app/analytics/exam_analytics.py:99-118`): `round(entry["score"]/entry["max_score"]*100.0,2)` crashes if entry max 0.
   - **Fix:** `round(entry["score"] / entry["max_score"] * 100 if entry["max_score"] > 0 else 0.0, 2)` at `V2_QuestionExamPredictionEngine/app/analytics/exam_analytics.py:116`.

3. **Important – Unsafe direct access** (`app/analytics/exam_analytics.py:101-102`): `for question in student["question_performance"]:` raises KeyError if key missing.
   - **Fix:** Changed to `student.get("question_performance", [])` at `V2_QuestionExamPredictionEngine/app/analytics/exam_analytics.py:101`. Bloom path already used `.get` (line 77) — kept consistent.

### Findings deferred (ledger, not fixed)

- Minor: inner `q["bloom_level"]` direct access — requires schema validation, deferred.
- Minor: shadowing variable `bloom_score` reuse in fallback — cosmetic, deferred.

### Verification

- **Existing tests:** `py -m pytest V2_QuestionExamPredictionEngine/tests/test_exam_analytics.py -v` → 5 passed (same as before).
- **Ad-hoc ZeroDivision repro:** `python -c` with `sys.path` set to `V2_QuestionExamPredictionEngine`:
  - bloom max 0: `[{"question_no":"01","bloom_level":"Apply","score":0,"max_score":0}, {"02",0,0}]` → `bloom_performance=[{"level":"Apply","average_percentage":0.0}]` — no crash, PASS.
  - missing `question_performance` key (fallback path): doc with only `bloom_performance` → falls back correctly, `bloom_performance` non-empty, `question_performance=[]` — no KeyError, PASS.
  - question entry `max_score==0`: single Q with `score=5, max=0` → `question_performance[0].average_percentage==0.0` — no crash, PASS.

### Commit

- `fix: guard bloom division and safe question_performance access (review findings task1)` — edits `V2_QuestionExamPredictionEngine/app/analytics/exam_analytics.py` (3 lines: bloom guard, question .get, question guard) + this report.

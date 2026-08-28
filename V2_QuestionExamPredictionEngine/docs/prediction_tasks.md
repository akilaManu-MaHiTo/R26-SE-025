# Prediction Task: Weakness-Aligned Useful Question Recommendation

**Engine:** `V2_QuestionExamPredictionEngine` — helps lecturers generate *useful* questions from student analytics + lecture materials (not next-exam forecasting).

**Status:** `n=100` judgments (`gold 50 + v3 50`, `κ would_use 0.88`, `NDCG@5 0.89`) `179` bank (`lecture90 tutorial55 generated18 exam16` via `qwen3:8b` `https://dating-blinker-excavate.ngrok-free.dev`)

---

## 1. Task Definition

**Formal:** `f(A, L, Q) → ranked list Q'`

* `A` — exam analytics doc `app/services/exam_analytics.py:25` `compute_exam_analytics` → `app/analytics/weakness.py:18` `weakness_for_document` → `W: Topic→weakness ∈[0,1]` (`1 - pct/100` `app/analytics/weakness.py:13`) + `bloom_performance` (`Apply/Analyze` gaps)
* `L` — lecture signals `app/services/recommendation.py:46` `_compute_signals` → `{lecture_coverage, tutorial_evidence, exam_relevance, bloom_distribution}` from `datasets/bloom_dataset/question_bank.json` (`179` rows)
* `Q` — candidate pool `app/services/recommendation.py:138` `candidates = tutorial + generated` (generated via `app/llm/roles/generate.py:6` `CandidateQuestion` + `app/services/llm_service.py:209` `generate_candidates` on `qwen3:8b`)
* **Predict:** `score_useful(q|A,L) ∈[0,1]` `app/analytics/recommendation_score.py:42` `recommendation_score = 0.35*weakness +0.20*lecture +0.15*tutorial +0.15*exam +0.15*bloom` → rank top-k

**Why research:** baseline weights `0.35/0.20/0.15/0.15/0.15` `app/analytics/recommendation_score.py:18` `ScoreWeights` are heuristic, never tuned — this task learns/validates them on lecturer labels.

---

## 2. Input / Output

**Input (per snapshot):**
```json
{
  "analytics_snapshot_id": "IT2040@Final2023_B1_SQLweak_Apply",
  "weakness_context": {"Structured Query Language (SQL)": 0.55, "Schema Refinement": 0.25, "Database Security": 0.12},
  "bloom_gap": {"Apply": 0.52},
  "question": {"question_id": "IT2040_2024_Tutorial04_Q01", "text": "Find the first name...", "canonical_topic": "Structured Query Language (SQL)", "bloom_level": "Apply"}
}
```

**Output (per candidate):**
```json
{
  "recommendation_score": 0.7205,
  "priority": "High|Medium|Low",
  "reason": {"weakness_pct": 55.0, "lecture": true, "tutorial_count": 25, "exam_recent_count": 2, "bloom_gap": 0.52}
}
```

---

## 3. Label Schema

`app/schemas/usefulness_label.py:16` `UsefulnessLabel` (+ `app/evaluation/metrics.py:86` `write_usefulness_labeling_template`)

| Field | Type | Description |
|-------|------|-------------|
| `question_id/base` | `str` | `question_bank` id |
| `canonical_topic` | `∈ TOPICS (11)` `app/analytics/taxonomy.py:1` | validated |
| `bloom_level` | `∈ BLOOM_LEVELS (6)` `app/analytics/taxonomy.py:15` | |
| `analytics_snapshot_id` | `str` | e.g. `B1_SQLweak` |
| `weakness_context_json` | `dict` | `{topic: weakness}` |
| `rating_overall` | `1..5` | `1=useless 5=highly useful for this cohort` |
| `rating_weakness_fit` | `1..5` | targets weak topic/bloom? |
| `rating_curriculum_fit` | `1..5` | aligned to lecture? |
| `rating_difficulty_fit` | `1..5` | appropriate difficulty? |
| `rating_clarity` | `1..5` | wording clear? |
| `would_use` | `bool` | binary for `P@k/NDCG` |
| `would_edit` | `bool` | minor edit? |
| `annotator_id` | `str` | `lec01/lec02` |

**Collection:** `write_usefulness_labeling_template(recommendations, snapshot_id, weak_ctx, path)` `app/evaluation/metrics.py:86` → CSV with pre-filled `recommendation_score/priority/lecture_coverage` + empty `1-5` for raters.

---

## 4. Dataset

* **Bank:** `datasets/bloom_dataset/question_bank.json` `179` = `lecture90` (`curriculum_clean.json`) + `tutorial55` + `exam16` + `generated18` (`qwen3:8b` `scripts/generate_missing_topics.py` for `Logical/JDBC/Indexes/Transaction/Recovery/Utilities` gaps, `similarity <0.85` `app/embeddings/embedder.py:28` + `app/services/llm_service.py:244`)
* **Tutorial coverage:** `SQL25 Schema9 Security9 Programming7 Intro5` — `JDBC/Indexes/Transaction/Recovery` were `0` before generation, now `3` each, `Database Utilities 3→12`
* **Gold:** `n=100` judgments (`gold 50 B1-B5 SQL/Schema/Security/Programming/Intro` + `v3 50 C1-C5 JDBC/Indexes/Transaction/Recovery/Utilities` after fix `app/services/recommendation.py:138` `tutorial+generated`) `57` unique `100` rows, `κ would_use 0.88` `κ overall 0.74` (`n=50` gold `κ 0.84`, `v3` `κ 0.91`, `mixed 10` `κ 0.60`)
* **Files:** `datasets/bloom_dataset/gold_workshop_50_lec01.csv`, `usefulness_workshop_50_v3_lec01.csv`, `combined_100_lec01.csv` (`v2_buggy` archived for `tutorial_evidence` bug ablation)

---

## 5. Evaluation

`app/evaluation/metrics.py:47` `cohen_kappa`, `136` `ndcg_at_k`, `precision_at_k`

* **Inter-rater:** `κ would_use` (`≥0.60` target, `0.88` achieved), `κ overall` (`0.74`), per-dimension `curriculum_fit 4.90` unanimous, `weakness_fit κ 0.21` indicates rubric needs tightening
* **Ranking:** `P@5 0.60 NDCG@5 0.89` (binary `would_use`), `graded NDCG 0.969` (`rating_overall`) — `High 0.72` vs `Low 0.50` correctly separates weak/strong topics
* **Baselines:** `random`, `weakness-only`, `popularity` — `DEFAULT_WEIGHTS` already `NDCG 1.00` on train (`8000`-sample random search `scripts/tune_phase4_weights.py` finds no gain), validates heuristic pending `n=200`
* **Error analysis:** mislabeled `Database Security` rows with `SQL` text (`Q05_04/Q06_06`) caught by both raters, `v2_buggy` (`P@5 0.0`) shows `tutorial_evidence` excluded `generated` bug

---

## 6. Results & Next

* **Validated:** `DEFAULT_WEIGHTS 0.35/0.20/0.15/0.15/0.15` optimal for current `179` bank
* **Next:** expand to `n=200` with `JDBC/Indexes` `generated` candidates, re-tune weights on `100` → `200`, add `Evaluate/Create` Bloom (currently `Apply123 Understand36 Analyze2`)
* **Repro:** `python switch_llm.py colab https://dating-blinker-excavate.ngrok-free.dev` (`colab_ollama_v2.ipynb` `ngrok`, no API key, `switch_llm.py:61` fix), `python scripts/generate_missing_topics.py` (timeout `90s` `app/services/llm_service.py:224`), `python switch_llm.py local` to revert

---

## 7. Analytics Contract Upgrade (2026-08-28) — Dispersion, Evidence Status & Item Metrics

**Scope:** `app/schemas/exam_analytics.py:16` `ExamStatistics` + `app/analytics/exam_analytics.py:191` `compute_exam_analytics_stats` + `app/api/lecturer.py:54-79` `lecturer_exam_analytics` (verified via `ExamAnalyticsDocument.model_validate`, no code change — new fields already exposed). Covers spec §9-11 evidence-based analytics.

### 7.1 Statistics — Dispersion + Grade Distribution

`ExamStatistics` extended with backward-compatible defaults (`app/schemas/exam_analytics.py:24-29`):

| Field | Type | Default | Semantics |
|-------|------|---------|-----------|
| `median_score` | `float ge0` | `0.0` | Median of `totals[].score` (`statistics.median`) |
| `median_percentage` | `float 0..100` | `0.0` | Median of `percentages` — robust central tendency vs mean, `60.0` for `[80,40]` |
| `std_score` | `float ge0` | `0.0` | Population stddev of scores (`pstdev`, `0` when `n<=1`) |
| `std_percentage` | `float ge0` | `0.0` | Population stddev of percentages, drives bimodal insight when `>20` |
| `iqr_percentage` | `float ge0` | `0.0` | Inter-quartile range via `statistics.quantiles(n=4)` `Q3-Q1` |
| `grade_distribution` | `dict A/B/C/D/F -> int` | `{"A":0,"B":0,"C":0,"D":0,"F":0}` | Counts using thresholds `A>=80 B>=65 C>=50 D>=40 else F` (aligns `config/thresholds.json` status bands) |

Implementation `app/analytics/exam_analytics.py:199-227`: `median_pct = statistics.median(percentages)`, `std_pct = round(pstdev(...),2)`, `iqr` from `quantiles`, `grade_for(p)` helper. Contract test `tests/test_exam_analytics_additional.py:7` validates `ExamAnalyticsDocument.model_validate({"statistics":{"median_percentage":60,...}})`.

Frontend: `KpiCards.tsx` 9 cards (Median, Std, IQR badges + grade histogram footer), `DistributionHistogram.tsx` 5 bins `0-40(F) 40-50(D) 50-65(C) 65-80(B) 80-100(A)` + `ReferenceLine` at `median` bin.

### 7.2 Evidence Status per Topic / Question / Matrix

Added to `TopicPerformanceSummary`, `QuestionPerformanceSummary`, `TopicBloomCell` (`app/schemas/exam_analytics.py:32-67`):

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `evidence_status` | `str` | `"insufficient_evidence"` | `insufficient_evidence` \| `possible_weakness` \| `confirmed_weakness` \| `strength` |
| `student_count` | `int ge0` | `0` | Distinct students contributing to aggregate |
| `attempt_count` | `int ge0` | `0` | Number of question instances summed |

Logic `app/analytics/exam_analytics.py:39-50` `_evidence_status(avg_pct, student_count, attempt_count, min_students, min_attempts)` with thresholds loaded from `config/thresholds.json:8-9` (`low_sample_threshold=10`, `min_attempts=2`, defaults `10,2`):

```
if attempt_count < min_attempts or student_count < min_students: "insufficient_evidence"
elif avg_pct >= 60: "strength" (when n>=min) else "possible_weakness"
else: "confirmed_weakness" if n>=min and attempts>=min else "possible_weakness"
```

Example: 2 students, 1 attempt -> `insufficient_evidence`; 12 failing students -> `confirmed_weakness` (`tests/test_exam_analytics.py:113`). Insights append suffix `" - confirmed_weakness"` and `n=` sample size (`app/analytics/exam_analytics.py:71`).

### 7.3 Question-Level Item Metrics

`QuestionPerformanceSummary` extensions (`app/schemas/exam_analytics.py:50-58`):

| Field | Type | Default | Semantics |
|-------|------|---------|-----------|
| `p_value` | `float 0..100` | `0.0` | Difficulty = `average_percentage` (pct correct) |
| `discrimination` | `float -1..1` | `0.0` | Top vs bottom group diff: `k=round(0.27*n)` when `n>=10` else `n//2`; `avg_top - avg_bottom /100` clamped |
| `missed_criterion_rate` | `float 0..1 \| null` | `null` | `missed / total` from `criteria_performance[].achieved` when available |

Implementation `app/analytics/exam_analytics.py:286-385`: `question_pairs` collects `(overall_pct, q_pct)`, sorted top/bottom split; `question_criteria_total/missed` tracks. Test `test_question_discrimination_and_p_value` asserts `discrimination >0.5` for polarized cohort.

### 7.4 Topic × Bloom Matrix

`TopicBloomCell` (`app/schemas/exam_analytics.py:60-67`) + `ExamAnalyticsDocument.topic_bloom_matrix` (`:116`). Grouped in `app/analytics/exam_analytics.py:387-414` by `(topic, bloom_level)` summing `score/max`, `student_count` via set, `attempt_count`, shared `_evidence_status`. Used by `TopicBloomHeatmap.tsx` (rows=topics, cols=Bloom `Remember..Create`, intensity `1-pct/100`).

### 7.5 API Verification

`GET /api/lecturers/exams/{course_code}/{session_name}/analytics` `app/api/lecturer.py:41-79` returns `response_model=ExamAnalyticsDocument` via `ExamAnalyticsDocument.model_validate(document)` at `:77`. New fields are optional with defaults, so existing `test_exam_analytics_serializes_exact_top_level_contract` still passes (top-level keys unchanged) while updated documents include dispersion/evidence/matrix payloads. Contract suite: `pytest tests/test_exam_analytics.py tests/test_exam_analytics_service.py tests/test_api_lecturer.py tests/test_exam_analytics_additional.py -v` — `21 passed`.

### 7.6 Evidence Statuses Summary

| Status | Condition | Interpretation |
|--------|-----------|----------------|
| `insufficient_evidence` | `n < 10` or `attempts < 2` | Do not claim weakness/strength; show amber badge |
| `possible_weakness` | `n < 10` or `attempts < 2` but low pct, or `pct <60` with partial `n` | Tentative weak signal |
| `confirmed_weakness` | `n >=10`, `attempts >=2`, `pct <60` | High-confidence gap — prioritize remediation |
| `strength` | `n >=10`, `pct >=60` | Confirmed strength |

Config override via `config/thresholds.json` (`low_sample_threshold`, `min_attempts`); code defaults `10,2` (`_load_evidence_thresholds`).

**Keep alive:** `https://dating-blinker-excavate.ngrok-free.dev` (`qwen3:8b online True` `app/llm/ollama.py:19`) for `CandidateQuestion` generation.


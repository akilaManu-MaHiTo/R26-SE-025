# gradev6 — 20-student essay and diagram demonstration dataset

Created and verified on 2026-10-16 using the configured MongoDB server.

## Contents

| Collection | Documents |
| --- | ---: |
| examkeys | 1 |
| rubricCollection | 1 |
| diagram_marking | 1 |
| submissions | 20 |
| diagram_evaluations | 20 |
| courses | 1 |
| course_taxonomies | 1 |

The exam is `EXAM-2025-S1-Apr`, IT2040, Final Examination, April 2025, semester 1. Its structure remains **five essay questions plus one diagram**, worth **35 + 20 = 55 marks**.

The five original students from gradev5 retain their original IDs and saved fields, raw/cleaned essay text where available, grading results, diagram extractions and statuses. The two existing graded essays remain graded; three students have no saved essay text/evaluation and retain their processing/not-started status. All five have saved diagram evaluations. No missing real answer or grade was fabricated.

Fifteen added students have explicit IDs `SYNTH-V6-001` through `SYNTH-V6-015`. Their authored essay answers contain varied correct, partial and incorrect explanations for the actual rubric topics. Each has a generated Chen ER diagram in `submitted_artifact` as an SVG, corresponding extracted nodes/connections, and rubric-consistent simulated scores. No OCR, detector or grading model was invoked for these generated artifacts.

## Provenance and interpretation

Every student component record has `dataset_provenance.kind`:

- `original_real_copy`: a preserved source component record, with its original database/collection/ID and source snapshot hash.
- `synthetic`: an authored demonstration record with simulated marks, explicitly identified as not a real student or independently verified grading result.

Synthetic essay `grading_source` and diagram `source` are `synthetic-fixture-not-model-graded`. Synthetic roster entries also have `synthetic: true`. The exam's `dataset_metadata` records the five-real/fifteen-synthetic composition.

This is a mixed demonstration dataset, **not 20 independent real student observations**. Separate real and synthetic records when reporting research accuracy or student outcomes. Source records may contain personal assessment data; no source answers or roster names were exported into this repository or printed in the seed report.

Original question headings and marking criteria are preserved. The original diagram question prompt and original submitted diagram images are not available in the source; the seed does not invent replacements for real records. Full question-paper reconstruction therefore still reports the original prompt gap. SVGs exist for the synthetic students only.

## Verification results

- **304 backend tests passed**, including six dataset tests for original preservation, projected-source restoration, missing real answers, unique/matched identities, diagram SVG/connection consistency, and refusal to overwrite an occupied target.
- All inserted documents were read back and compared with the prepared dataset.
- An independent live read compared all ten original component records with gradev5, excluding only the added provenance field: **all matched**. The source snapshot hash still matched after loading.
- Existing lecturer services returned **20 student rows, 17 complete grades, three pending grades and zero review-needed grades**.
- Existing diagram aggregation returned **20 students and 11 marking criteria**.
- Essay/diagram scores validate against their exact linked rubrics and the 55-mark combined maximum. No missing mark is filled with zero.
- No gradev5 writes, regrading, account/session copying, cache copying or application database-setting changes were performed. The app remains configured for gradev5. Pointing the running app at gradev6 and setting up any required login accounts is a separate deployment step.

## Loader

From `AdaptiveExamAnalyticsEngine`:

```powershell
python scripts/seed_gradev6.py          # read-only preparation and validation
python scripts/seed_gradev6.py --apply  # writes only if gradev6 contains no records
```

The loader uses existing connection settings privately and fixed source/target database names. It first matches the exam using existing repository logic, then reloads the matched IDs without projections to preserve full original fields. It does not delete, update or overwrite existing records. Now that gradev6 is populated, rerunning either command refuses the occupied target. Unique exam/student indexes prevent duplicate target component records.

All documents are validated before the first write. Inserts across collections are not a transaction on a standalone MongoDB server; an interrupted first load could leave a partial target, and a subsequent run would refuse to overwrite it. This load completed and passed full read-back verification.

Not checked: real-browser rendering of every generated SVG or live model grading. Synthetic mark fixtures demonstrate pipeline behavior; they do not establish grading accuracy.

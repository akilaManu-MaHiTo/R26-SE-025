# Independent Bloom holdout

The original 500-row `gold_bloom_v2.csv` overlaps the confirmed training-source
CSV in every row. It cannot currently substantiate unseen performance. Do not
split that pool again and claim the deployed checkpoint has never seen the split.

## Prepared exam candidates

`datasets/bloom_dataset/bloom/final_exam_holdout_candidates.csv` contains **14
unlabeled pilot candidates**, selected from the supplied 2022 and 2023 IT2040
final papers. Source PDF pages were rendered and checked against the selected
text. Shared relation/schema context is retained for contextual questions;
underlined primary keys are written explicitly for text input. Formatting and
arrow notation were normalized. The source has some apparent schema/query
ambiguities; notes flag these for lecturer review rather than silently repairing
the exam. These are not gold labels and are not a completed independent test set.

No candidate has an exact normalized text match in the supplied training source.
This includes case, whitespace, Unicode compatibility and punctuation
normalization. It does **not** establish semantic independence: a longer question
can contain a training question, and paraphrases can escape exact matching.
Review short question prompts as well as their full context against the training
pool. Related Q2/Q4 parts must be treated as question families; a small number of
families does not provide 14 independent samples.

The preparation manifest is `audit_evidence/final_exam_holdout_preparation.json`.
It records PDF and CSV hashes. The 2019 paper and the file named 2024 have scan
transcription problems; the latter's extracted cover says **2018**. Verify its
actual year before adding it. Diagram questions and unreliable code extraction
were excluded from this first text-only pilot. No claim covers those modalities.

## Complete the holdout

1. Confirm these questions and their variants were never used to fit, select,
   tune or debug the current checkpoint. Record that confirmation and any known
   exclusions in the study record. Supply every additional training/tuning CSV
   to the command below. A script cannot verify historical non-use or who labeled
   a row.
2. Two lecturers independently label each question **without model predictions**.
   Fill distinct rater IDs and `rater_a_label` / `rater_b_label`. Use full names:
   Remember, Understand, Apply, Analyze, Evaluate, Create. Keep necessary context
   in `question_text`; the model does not read `notes`.
3. Resolve disagreements using recorded `adjudicator_id` and final `bloom_label`.
   Review multi-demand questions, transcription, source ambiguities and semantic
   duplicates before inclusion. Keep raw rater labels unchanged.
4. Broaden the pilot to more independent question families and exams. Check
   counts across all six levels; do not invent labels to balance the set. A
   DBMS-only set supports claims about that domain only. Keep absent-class
   support visible rather than claiming six-class coverage.
5. Freeze the questions, adjudicated labels and model before evaluation. Never
   use the final holdout for tuning; obtain a fresh holdout if it informs changes.

## Validate and evaluate

From the engine directory, after filling the candidate sheet:

```powershell
.venv/Scripts/python.exe scripts/evaluate_bloom_holdout.py datasets/bloom_dataset/bloom/final_exam_holdout_candidates.csv
```

This fails for empty/unlabeled sets, duplicate IDs/text, unknown labels, unresolved
disagreements, missing provenance and normalized training-source overlap.
The complete confirmed training source is always excluded. Add additional pools
with repeated `--exclude-source path/to/tuning.csv` (columns `Questions` or
`question_text`). Do not pass only a subset of a known pool.

After human provenance review, add `--evaluate` to run the existing local frozen
ModernBERT. It validates **before loading the model** and prints JSON containing
input/exclusion/model file hashes, per-question predictions, accuracy,
six-class macro F1, per-class precision/recall/F1/support and a confusion matrix
(rows gold, columns predictions). Redirect stdout to a new JSON result file to
archive it. No training occurs. The existing classifier's configured truncation
still applies; long schema questions require separate input-length review.

No accuracy was measured during preparation: lecturer labels and confirmed
historical non-use have not been supplied.

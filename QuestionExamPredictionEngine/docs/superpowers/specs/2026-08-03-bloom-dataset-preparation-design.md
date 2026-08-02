# Bloom Dataset Preparation Design

**Date:** 2026-08-03
**Status:** Approved for specification review
**Project:** QuestionExamPredictionEngine

## 1. Purpose

Prepare the existing English Computer Science dataset for the first research model: a question-to-Bloom-level classifier. The process must preserve the original data, expose contradictory labels for expert review, and generate a training dataset only from explicitly approved labels.

## 2. Source-data finding

The source file contains 6,633 rows but only 128 normalized question texts. Every normalized question occurs with more than one observed Bloom label. Consequently, automatic deduplication cannot determine a trustworthy label for any question, and the preparation pipeline must not select a label by majority vote or silently discard the conflict.

## 3. Selected approach

Use a two-stage, fail-closed preparation pipeline:

1. Build a 128-row expert-review queue from the untouched source CSV.
2. Build the model-training CSV only from review rows with an explicitly approved Bloom label.

The original `training_dataset/dataset_v1_clean.csv` remains unchanged. The pipeline is deterministic and can be rerun after any review correction.

## 4. Components

### 4.1 Preparation module

Add `src/analysis/training/prepare_bloom_dataset.py` with independently testable functions for:

- normalizing question text;
- validating the input schema and Bloom labels;
- grouping source rows by normalized question;
- calculating observed-label counts;
- creating review records;
- validating reviewer-approved labels;
- creating one training record per approved normalized question;
- producing the audit summary; and
- writing CSV and JSON outputs through a command-line entry point.

The module will use Python's standard CSV and JSON libraries so the same command works locally and in Google Colab without adding a data-processing dependency.

### 4.2 Expert-review CSV

Generate `training_dataset/processed/dataset_v1_bloom_review.csv` with one row for each normalized question and these fields:

- `group_id`: deterministic SHA-256-based identifier for the normalized question;
- `question`: representative original question text;
- `normalized_question`;
- `source_row_count`;
- `observed_labels`: sorted pipe-delimited labels;
- `label_counts`: JSON object containing counts per label;
- `subjects`, `topics`, and `subtopics`: sorted pipe-delimited provenance values;
- `source_ids`: sorted pipe-delimited source-row identifiers;
- `approved_bloom_level`: blank until expert review;
- `review_status`: initially `needs_review`;
- `review_notes`: blank editable field.

The review file will not contain a guessed or majority-vote label.

### 4.3 Training CSV

Generate `training_dataset/processed/dataset_v1_bloom_train.csv` from the review file. It will contain only review rows whose `approved_bloom_level` is one of:

- `remember`
- `understand`
- `apply`
- `analyze`
- `evaluate`
- `create`

Each approved question appears exactly once with these fields:

- `group_id`;
- `question`;
- `bloom_level`;
- `source_row_count`;
- `review_status`;
- `review_notes`.

Unreviewed rows are excluded. Invalid nonblank approvals fail validation instead of being skipped.

### 4.4 Audit report

Generate `training_dataset/processed/dataset_v1_bloom_audit.json` containing:

- input path and SHA-256 checksum;
- total source rows;
- unique normalized questions;
- conflicting question groups and affected rows;
- observed source-label distribution;
- review-status counts;
- approved training-row count;
- approved training-label distribution;
- excluded unreviewed-row count;
- generation timestamp and pipeline version.

The timestamp is informational. All row ordering, identifiers, counts, and dataset contents remain deterministic for the same source and review inputs.

## 5. Data flow

```text
dataset_v1_clean.csv (read only)
          |
          v
schema validation and question normalization
          |
          v
grouping and conflict audit
          |
          v
dataset_v1_bloom_review.csv
          |
          | lecturer fills approved_bloom_level
          v
approval validation and one-row-per-question export
          |
          +--> dataset_v1_bloom_train.csv
          +--> dataset_v1_bloom_audit.json
```

On the first run, the training CSV will contain only its header because all 128 groups require review. After the lecturer fills approved labels, rerunning the command produces the deduplicated training rows.

## 6. Command-line behavior

Support two explicit operations:

```powershell
python -m src.analysis.training.prepare_bloom_dataset prepare-review `
  --input training_dataset/dataset_v1_clean.csv `
  --output-dir training_dataset/processed
```

```powershell
python -m src.analysis.training.prepare_bloom_dataset build-training `
  --review-file training_dataset/processed/dataset_v1_bloom_review.csv `
  --output-dir training_dataset/processed
```

`prepare-review` creates or refreshes the review queue and audit. If an existing review file is supplied, approved labels and review notes are retained by `group_id` when the question still exists.

`build-training` validates the completed portions of the review queue, writes the current approved subset, and updates the audit. It prints the number of approved and unreviewed groups. An optional `--require-complete-review` flag fails unless all 128 rows have valid approvals.

## 7. Error handling

The command exits unsuccessfully and does not replace existing outputs when:

- required input columns are missing;
- the input CSV cannot be parsed;
- a source row has an empty question or unsupported Bloom label;
- a nonblank approval contains an unsupported Bloom label;
- duplicate review rows share a `group_id`;
- a `group_id` does not match its normalized question; or
- `--require-complete-review` is used while reviews remain incomplete.

Outputs are written to temporary sibling files and then replaced, preventing partially written artifacts.

## 8. Testing

Add `tests/analysis/training/test_prepare_bloom_dataset.py` using temporary directories and real CSV files. Tests will cover:

- normalization and deterministic group identifiers;
- grouping duplicate questions without choosing a conflicting label;
- sorted observed-label counts and provenance;
- preservation of existing approvals when regenerating the review queue;
- rejection of missing columns, empty questions, and invalid labels;
- exclusion of blank approvals from training output;
- rejection of invalid nonblank approvals;
- one-row-per-approved-question training output;
- completeness enforcement;
- deterministic ordering; and
- audit counts matching the generated CSVs.

The tests will follow red-green-refactor development: each behavior is first expressed by a failing test, implemented minimally, and rerun with the complete repository test suite.

## 9. Verification and acceptance criteria

The work is accepted when:

- the original source CSV checksum is identical before and after preparation;
- the review CSV contains exactly 128 data rows;
- every review row has a stable unique `group_id`;
- every initial `approved_bloom_level` is blank;
- no conflicting observed label is silently selected;
- the initial training CSV has a header and zero data rows;
- approved review fixtures generate exactly one training row per approved group;
- audit totals reconcile with both output CSVs;
- the focused preparation tests and complete repository test suite pass; and
- generated CSVs can be loaded by the existing tabular-data loader.

## 10. Non-goals

- Automatically assigning Bloom levels from question verbs.
- Using majority vote to resolve label conflicts.
- Training the classifier in this change.
- Modifying the existing Bloom model or its inference interface.
- Treating the initial 128-question reviewed dataset as sufficient final dissertation evidence.

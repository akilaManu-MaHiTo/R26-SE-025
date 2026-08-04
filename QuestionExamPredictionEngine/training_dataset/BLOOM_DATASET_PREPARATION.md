# Preparing Bloom-Taxonomy Data for Training

This folder contains raw and prepared question datasets for the six-class
`CognitiveBloomModel`. Keep raw files unchanged and create new prepared files
when cleaning rules or source data change.

## Current files

| File | Purpose | Data rows |
|---|---|---:|
| `blooms_taxonomy_dataset_v1.csv` | Original BT1-BT6 source; do not edit | 999 |
| `blooms_taxonomy_dataset_v1_prepared.csv` | All source rows mapped to model labels | 999 |
| `blooms_taxonomy_dataset_v1_novel.csv` | Unique rows not present in the PONE 741-row corpus | 415 |
| `processed/pone_bloom_v1.0/pone_bloom_full.csv` | Existing PONE reference corpus | 741 |

The source file has 1,000 physical CSV rows including its header, so it
contains 999 training records rather than 1,000.

## Required model schema

The trainer requires at least these columns:

```text
question,bloom_level
```

Prepared files also retain audit fields:

| Column | Meaning |
|---|---|
| `row_id` | Stable identifier based on source filename and source row |
| `question_group_id` | Stable identifier based on normalized question text |
| `question` | Text used by the model |
| `bloom_level` | Six-class model target |
| `source_category` | Original BT1-BT6 label |
| `source_document` | Provenance filename |
| `quality_flags` | Pipe-delimited preparation warnings or `none` |

## Label mapping

Use the following mapping exactly:

| Source category | Model label |
|---|---|
| `BT1` | `remember` |
| `BT2` | `understand` |
| `BT3` | `apply` |
| `BT4` | `analyze` |
| `BT5` | `evaluate` |
| `BT6` | `create` |

The prepared-full label distribution is:

| Label | Rows |
|---|---:|
| `remember` | 277 |
| `understand` | 190 |
| `apply` | 161 |
| `analyze` | 149 |
| `evaluate` | 113 |
| `create` | 109 |

## Preparation procedure

1. Validate that the source columns are exactly `Questions` and `Category`.
2. Reject blank questions, blank categories, and categories outside BT1-BT6.
3. Repair recognizable Windows-1252 and UTF-8 mojibake punctuation.
4. Normalize question text to Unicode NFKC.
5. Trim leading and trailing whitespace and collapse internal whitespace.
6. Map BT1-BT6 to the six model labels above.
7. Generate deterministic row and normalized-question group identifiers.
8. Mark duplicate, encoding, placeholder, missing-context, short-question,
   language-error, and PONE-overlap conditions in `quality_flags`.
9. Keep every source row in the prepared-full artifact.
10. For the novel artifact, remove all questions already present in PONE and
    retain only one row per normalized question.

Never silently rewrite the meaning of a question or infer a new Bloom label
from its action verb. Suspected label errors require human review.

## Duplicate and leakage policy

The raw source contains three duplicate extra rows and has no duplicate group
with conflicting labels. After text and encoding normalization, 581 rows
overlap the PONE 741-row corpus.

Do not concatenate `blooms_taxonomy_dataset_v1_prepared.csv` with a PONE file.
That would repeat hundreds of questions and could place identical wording in
both training and evaluation data. Use
`blooms_taxonomy_dataset_v1_novel.csv` when augmenting PONE.

All rows sharing a `question_group_id` must remain in the same train,
validation, or test split. Keep the existing PONE test file untouched when
comparing models.

## Train a separate model using all 999 prepared questions

From the `QuestionExamPredictionEngine` directory:

```powershell
.\.venv\Scripts\python.exe -m src.analysis.training.train_cognitive_bloom_model `
  --input training_dataset\blooms_taxonomy_dataset_v1_prepared.csv `
  --output model\cognitive_bloom\cognitive_bloom_csv_v1.joblib `
  --label-column bloom_level `
  --text-columns question
```

The current trainer performs its own deterministic 80/20 internal split.
Record that validation score, but do not compare it directly with a score
calculated from a different test set.

## Train an augmented PONE model

To augment PONE safely, combine only:

```text
processed/pone_bloom_v1.0/pone_bloom_train.csv
blooms_taxonomy_dataset_v1_novel.csv
```

Select the common `question` and `bloom_level` columns, write one CSV header,
and preserve provenance/group identifiers in the working version. Do not add
PONE validation or test rows to training. Evaluate the resulting model on:

```text
processed/pone_bloom_v1.0/pone_bloom_validation.csv
processed/pone_bloom_v1.0/pone_bloom_test.csv
```

## Validation checklist

Before training, confirm:

- every `question` is nonblank;
- every `bloom_level` is one of the six supported labels;
- row identifiers are unique;
- duplicate question groups do not cross splits;
- all six labels are represented;
- no PONE test question appears in augmented training data;
- quality flags have been reviewed rather than automatically ignored;
- the final test set has not been used for tuning.

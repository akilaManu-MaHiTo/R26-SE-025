# PONE Bloom Dataset Design

**Date:** 2026-08-04
**Status:** Approved design; awaiting written-spec review
**Project:** QuestionExamPredictionEngine

## 1. Purpose

Build a reproducible six-class Bloom-taxonomy dataset from the two supplied
Word documents. All 741 source-labeled questions must remain available for
model training. Quality concerns are recorded as flags and review records; they
do not remove rows from the full dataset.

## 2. Source documents

The inputs are:

- `pone.0230442.s001.docx`: 141 questions;
- `pone.0230442.s002.docx`: 600 questions.

The source documents remain unchanged. Each generated row records its source
document and source paragraph index, and the audit records a SHA-256 checksum
for each input.

## 3. Label mapping

The documents use the original Bloom category names. Convert them to the
labels expected by `CognitiveBloomModel`:

| Source heading | Model label |
|---|---|
| Knowledge | `remember` |
| Comprehension | `understand` |
| Application | `apply` |
| Analysis | `analyze` |
| Synthesis | `create` |
| Evaluation | `evaluate` |

The source heading remains in `legacy_bloom_level`; the mapped value is written
to `bloom_level`.

## 4. Extraction and normalization

Implement a deterministic extractor for the paragraph-only DOCX structure.
It will read the document XML, switch the active label whenever it encounters
one of the six headings, and emit every subsequent nonblank paragraph as a
question until the next heading.

Normalization is conservative:

- normalize Unicode to NFKC;
- trim leading and trailing whitespace;
- collapse repeated internal whitespace;
- preserve wording, spelling, grammar, placeholders, and punctuation content;
- store the unchanged extracted text in `original_question`;
- store the normalized text used by the model in `question`.

No question is rewritten and no label is inferred from its wording.

## 5. Row identity and duplicate handling

Every source question remains a distinct row. Generate a stable `row_id` from
the source-document name and paragraph index. Generate a `question_group_id`
from the normalized question text.

Exact and normalized duplicates are not deleted because the approved scope
requires all 741 rows. Rows sharing a `question_group_id` must always be
assigned to the same train, validation, or test split so duplicated wording
cannot leak across evaluation boundaries.

## 6. Quality flags

Add zero or more pipe-delimited flags to `quality_flags`:

- `placeholder`: ellipses, long underscore blanks, or visibly incomplete
  substitution prompts;
- `missing_context`: references to a diagram, picture, graph, passage, table,
  story, questionnaire, or other absent supporting material;
- `very_short`: fewer than four word tokens;
- `possible_language_error`: a narrow deterministic list of obvious grammar or
  spelling patterns;
- `exact_duplicate`: repeated normalized question text;
- `none`: no detected issue.

Flagged rows remain in the full dataset and in one of the three split files.
The quality-review CSV is informational and supports later human correction.
It does not act as an exclusion list.

## 7. Generated artifacts

Write artifacts under
`training_dataset/processed/pone_bloom_v1.0/`:

1. `pone_bloom_full.csv` — all 741 rows, suitable for complete-corpus training.
2. `pone_bloom_train.csv` — grouped, stratified training split.
3. `pone_bloom_validation.csv` — grouped, stratified validation split.
4. `pone_bloom_test.csv` — grouped, stratified held-out test split.
5. `pone_bloom_quality_review.csv` — all flagged rows with review columns.
6. `pone_bloom_audit.json` — provenance, hashes, counts, distributions, flags,
   duplicate groups, split totals, and pipeline version.

The CSV schema is:

- `row_id`;
- `question_group_id`;
- `question`;
- `original_question`;
- `bloom_level`;
- `legacy_bloom_level`;
- `source_document`;
- `source_paragraph`;
- `quality_flags`;
- `split`.

`question` and `bloom_level` make every dataset directly loadable by the
existing tabular loader and Bloom trainer. Additional columns provide audit
and review information and are ignored by the current model pipeline.

## 8. Split policy

Create deterministic 70/15/15 train, validation, and test splits with a fixed
seed. Stratify as closely as possible by `bloom_level`, but treat each
`question_group_id` as an indivisible unit. The full dataset and the union of
the three split files must each contain exactly 741 rows.

Because the current `CognitiveBloomModel.fit()` performs its own random split,
the generated validation and test files are authoritative evaluation artifacts;
they must not be passed into model fitting. A later training change may add an
explicit external-evaluation command, but modifying model behavior is outside
this dataset-build scope.

## 9. Audit and failure behavior

The build fails without replacing existing artifacts if:

- either source file is missing or unreadable;
- a document contains questions before the first recognized heading;
- a document does not contain all six headings;
- an emitted row has an empty question or unsupported mapped label;
- extracted source totals are not 141 and 600 respectively;
- the combined total is not 741;
- a row appears in more than one split;
- a duplicate group crosses split boundaries; or
- output counts do not reconcile with the audit.

Write outputs through staged sibling files and replace the artifact set only
after all validations succeed.

## 10. Implementation components

Add:

- `src/analysis/training/prepare_pone_bloom_dataset.py` for DOCX extraction,
  normalization, flagging, splitting, validation, audit creation, atomic
  output, and a command-line entry point;
- `tests/analysis/training/test_prepare_pone_bloom_dataset.py` for focused unit
  and CLI tests.

Use Python's standard `zipfile`, `xml.etree.ElementTree`, `csv`, `json`, and
hashing modules so the build does not add a runtime dependency on Word or
LibreOffice.

## 11. Verification and acceptance criteria

The dataset build is accepted when:

- source checksums are unchanged after processing;
- the full CSV contains exactly 741 data rows;
- label counts are exactly `remember=126`, `understand=123`, `apply=115`,
  `analyze=123`, `create=130`, and `evaluate=124`;
- all six model labels are present in every split when group constraints permit;
- every row has a stable identity and provenance;
- flagged rows remain present in the full dataset and split union;
- the split files are disjoint and total 741 rows;
- no `question_group_id` crosses split boundaries;
- the audit reconciles with every CSV;
- `load_tabular_dataset()` loads each output successfully;
- a fresh in-memory `CognitiveBloomModel` fit succeeds on the training split;
- focused tests and the complete repository test suite pass.

## 12. Non-goals

- Correcting or rewriting source questions.
- Removing placeholder, context-dependent, short, or erroneous questions.
- Inventing answers, subjects, topics, or difficulty labels.
- Relabeling questions based on action verbs.
- Training or replacing `cognitive_bloom_model.joblib` in this dataset-build
  change.

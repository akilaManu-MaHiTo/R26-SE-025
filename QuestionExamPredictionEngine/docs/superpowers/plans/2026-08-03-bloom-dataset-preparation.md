# Bloom Dataset Preparation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reproducible, fail-closed pipeline that converts the contradictory source CSV into an expert-review queue, an approved-only Bloom training CSV, and a reconciled audit report.

**Architecture:** A focused standard-library Python module owns normalization, validation, grouping, review preservation, training-row selection, auditing, and atomic output. A two-command CLI first prepares the 128-row review queue and then builds training data only from valid human approvals. The original source CSV is always read-only.

**Tech Stack:** Python 3, standard-library `argparse`, `csv`, `hashlib`, `json`, `tempfile`, `unittest`, and the repository's existing tabular loader for compatibility verification.

## Global Constraints

- Preserve `training_dataset/dataset_v1_clean.csv` byte-for-byte.
- Never infer, majority-vote, or silently select a Bloom label.
- Valid labels are exactly `remember`, `understand`, `apply`, `analyze`, `evaluate`, and `create` after lowercase normalization.
- Write generated artifacts under `training_dataset/processed/`.
- Invalid nonblank approvals fail validation.
- The initial training CSV contains a header and zero data rows.
- Use one stable SHA-256-derived `group_id` per normalized question.
- Use standard-library CSV and JSON processing; do not add dependencies.
- Follow test-first red-green-refactor development.

---

## File structure

- Create `src/analysis/training/prepare_bloom_dataset.py`: transformation functions, atomic writers, audit construction, and CLI.
- Create `tests/analysis/__init__.py`: test-package marker.
- Create `tests/analysis/training/__init__.py`: test-package marker.
- Create `tests/analysis/training/test_prepare_bloom_dataset.py`: unit and CLI-level behavior tests using temporary real CSV files.
- Generate `training_dataset/processed/dataset_v1_bloom_review.csv`: editable expert review queue.
- Generate `training_dataset/processed/dataset_v1_bloom_train.csv`: approved-only model input.
- Generate `training_dataset/processed/dataset_v1_bloom_audit.json`: source, conflict, review, and training reconciliation.

### Task 1: Normalize, validate, and group source rows

**Files:**
- Create: `src/analysis/training/prepare_bloom_dataset.py`
- Create: `tests/analysis/__init__.py`
- Create: `tests/analysis/training/__init__.py`
- Create: `tests/analysis/training/test_prepare_bloom_dataset.py`

**Interfaces:**
- Consumes: iterable mappings with source columns `id`, `subject`, `topic`, `subtopic`, `question`, and `bloom_level`.
- Produces: `normalize_question(value: object) -> str`, `question_group_id(normalized_question: str) -> str`, `validate_source_rows(rows: list[dict[str, str]]) -> None`, and `build_review_records(rows: list[dict[str, str]], existing_reviews: list[dict[str, str]] | None = None) -> list[dict[str, str]]`.

- [ ] **Step 1: Write failing normalization and identifier tests**

```python
def test_normalize_question_collapses_spacing_and_case(self):
    self.assertEqual(normalize_question("  Explain   ACID?  "), "explain acid?")

def test_question_group_id_is_stable(self):
    self.assertEqual(
        question_group_id("explain acid?"),
        question_group_id(normalize_question(" Explain  ACID? ")),
    )
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `\.venv\Scripts\python.exe -m unittest tests.analysis.training.test_prepare_bloom_dataset -v`

Expected: import failure because `prepare_bloom_dataset` does not exist.

- [ ] **Step 3: Implement normalization and stable IDs**

```python
VALID_BLOOM_LEVELS = ("remember", "understand", "apply", "analyze", "evaluate", "create")
PIPELINE_VERSION = "1.0.0"

def normalize_question(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    return " ".join(text.split())

def question_group_id(normalized_question: str) -> str:
    digest = hashlib.sha256(normalized_question.encode("utf-8")).hexdigest()
    return f"bloom-{digest[:16]}"
```

- [ ] **Step 4: Run focused tests and verify GREEN**

Run: `\.venv\Scripts\python.exe -m unittest tests.analysis.training.test_prepare_bloom_dataset -v`

Expected: normalization and identifier tests pass.

- [ ] **Step 5: Write failing validation tests**

```python
def test_validate_source_rows_rejects_missing_required_column(self):
    with self.assertRaisesRegex(ValueError, "missing required columns"):
        validate_source_rows([{"id": "1", "question": "Explain ACID?"}])

def test_validate_source_rows_rejects_empty_question(self):
    row = source_row(question="   ")
    with self.assertRaisesRegex(ValueError, "empty question"):
        validate_source_rows([row])

def test_validate_source_rows_rejects_invalid_bloom_label(self):
    row = source_row(bloom_level="invent")
    with self.assertRaisesRegex(ValueError, "unsupported Bloom label"):
        validate_source_rows([row])
```

- [ ] **Step 6: Run validation tests and verify RED**

Run: `\.venv\Scripts\python.exe -m unittest tests.analysis.training.test_prepare_bloom_dataset -v`

Expected: failures because source validation is not implemented.

- [ ] **Step 7: Implement source validation and review grouping**

Implement `validate_source_rows()` to reject an empty dataset, missing required columns, empty normalized questions, and labels outside `VALID_BLOOM_LEVELS`. Implement `build_review_records()` with `defaultdict(list)` and `Counter`; sort groups by `(normalized_question, group_id)`, sort provenance values, serialize label counts with `json.dumps(..., sort_keys=True)`, and leave approvals blank when no matching existing review is present.

The review record fields must follow `REVIEW_FIELDNAMES` in this exact order:

```python
REVIEW_FIELDNAMES = (
    "group_id", "question", "normalized_question", "source_row_count",
    "observed_labels", "label_counts", "subjects", "topics", "subtopics",
    "source_ids", "approved_bloom_level", "review_status", "review_notes",
)
```

- [ ] **Step 8: Add and pass conflict-grouping tests**

Add a fixture with the same normalized question labelled `Remember` and `Analyze`. Assert that one review row is returned, `approved_bloom_level == ""`, `review_status == "needs_review"`, `observed_labels == "analyze|remember"`, and `label_counts == '{"analyze": 1, "remember": 1}'`.

Run: `\.venv\Scripts\python.exe -m unittest tests.analysis.training.test_prepare_bloom_dataset -v`

Expected: all Task 1 tests pass.

- [ ] **Step 9: Commit Task 1**

```powershell
git add src/analysis/training/prepare_bloom_dataset.py tests/analysis
git commit -m "feat: group Bloom questions for expert review"
```

### Task 2: Preserve reviews and build approved-only training rows

**Files:**
- Modify: `src/analysis/training/prepare_bloom_dataset.py`
- Modify: `tests/analysis/training/test_prepare_bloom_dataset.py`

**Interfaces:**
- Consumes: Task 1 review records or review rows loaded from CSV.
- Produces: `validate_review_rows(rows: list[dict[str, str]]) -> None` and `build_training_records(review_rows: list[dict[str, str]], require_complete: bool = False) -> list[dict[str, str]]`.

- [ ] **Step 1: Write failing review-preservation test**

Create source rows for `Explain ACID?` and an existing review row with the matching `group_id`, `approved_bloom_level="Understand"`, and `review_notes="Checked by lecturer"`. Assert regenerated review data preserves the lowercase approval and note and sets `review_status="approved"`.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `\.venv\Scripts\python.exe -m unittest tests.analysis.training.test_prepare_bloom_dataset.BloomDatasetPreparationTests.test_existing_review_is_preserved -v`

Expected: failure because existing approvals are not preserved.

- [ ] **Step 3: Implement preservation by verified `group_id`**

Index existing rows by `group_id`. Validate that each existing `group_id` is unique and equals `question_group_id(normalize_question(row["normalized_question"]))`. Preserve only valid approval and notes for a still-existing group. Recalculate status as `approved` when approval is nonblank and `needs_review` otherwise.

- [ ] **Step 4: Run the preservation test and verify GREEN**

Run the same focused command and expect PASS.

- [ ] **Step 5: Write failing approved-only export tests**

```python
def review_row(question, approval):
    normalized = normalize_question(question)
    return {
        "group_id": question_group_id(normalized),
        "question": question,
        "normalized_question": normalized,
        "source_row_count": "1",
        "observed_labels": "remember",
        "label_counts": '{"remember": 1}',
        "subjects": "Computer Science",
        "topics": "Databases",
        "subtopics": "Transactions",
        "source_ids": "1",
        "approved_bloom_level": approval,
        "review_status": "approved" if approval else "needs_review",
        "review_notes": "",
    }

def test_training_rows_include_only_valid_approvals(self):
    reviews = [review_row("q1", "Remember"), review_row("q2", "")]
    result = build_training_records(reviews)
    self.assertEqual(len(result), 1)
    self.assertEqual(result[0]["bloom_level"], "remember")
    self.assertEqual(result[0]["review_status"], "approved")

def test_invalid_nonblank_approval_is_rejected(self):
    with self.assertRaisesRegex(ValueError, "invalid approved Bloom label"):
        build_training_records([review_row("q1", "Invent")])

def test_complete_review_can_be_required(self):
    with self.assertRaisesRegex(ValueError, "review is incomplete"):
        build_training_records([review_row("q1", "")], require_complete=True)
```

- [ ] **Step 6: Run the export tests and verify RED**

Run the focused test module and expect failures because training selection is absent.

- [ ] **Step 7: Implement review validation and training selection**

Use exact field order:

```python
TRAIN_FIELDNAMES = (
    "group_id", "question", "bloom_level", "source_row_count",
    "review_status", "review_notes",
)
```

Reject duplicate or mismatched IDs and invalid nonblank approvals. Exclude blank approvals unless `require_complete=True`. Sort output by `(question.lower(), group_id)` and emit exactly one row per group.

- [ ] **Step 8: Run Task 2 tests and verify GREEN**

Run: `\.venv\Scripts\python.exe -m unittest tests.analysis.training.test_prepare_bloom_dataset -v`

Expected: all Task 1 and Task 2 tests pass.

- [ ] **Step 9: Commit Task 2**

```powershell
git add src/analysis/training/prepare_bloom_dataset.py tests/analysis/training/test_prepare_bloom_dataset.py
git commit -m "feat: build approved Bloom training rows"
```

### Task 3: Add atomic outputs, audit reconciliation, and CLI

**Files:**
- Modify: `src/analysis/training/prepare_bloom_dataset.py`
- Modify: `tests/analysis/training/test_prepare_bloom_dataset.py`

**Interfaces:**
- Consumes: source CSV, optional existing review CSV, and Task 1/2 transformation functions.
- Produces: `prepare_review(input_path: Path, output_dir: Path) -> dict[str, object]`, `build_training(review_file: Path, output_dir: Path, require_complete_review: bool = False) -> dict[str, object]`, and `main(argv: Sequence[str] | None = None) -> int`.

- [ ] **Step 1: Write failing end-to-end `prepare-review` test**

Write a temporary source CSV with two normalized questions and conflicting labels. Call `prepare_review()`. Assert:

- source bytes and SHA-256 are unchanged;
- review CSV has two data rows;
- training CSV exists with zero data rows;
- audit JSON reports source rows, unique groups, conflicts, zero approvals, and two exclusions;
- `load_tabular_dataset()` loads both output CSVs.

- [ ] **Step 2: Run the end-to-end test and verify RED**

Run the focused test and expect failure because orchestration and writers are absent.

- [ ] **Step 3: Implement CSV loading and atomic writers**

Implement:

```python
def read_csv_rows(path: Path) -> list[dict[str, str]]: ...
def write_csv_atomic(path: Path, fieldnames: Sequence[str], rows: Sequence[Mapping[str, object]]) -> None: ...
def write_json_atomic(path: Path, payload: Mapping[str, object]) -> None: ...
def sha256_file(path: Path) -> str: ...
```

Write sibling temporary files using `tempfile.NamedTemporaryFile(delete=False, dir=path.parent)` and replace the destination with `os.replace()` only after serialization succeeds. Clean up a remaining temporary file in `finally`.

- [ ] **Step 4: Implement reconciled audit construction**

`build_audit()` must report input path/checksum, `PIPELINE_VERSION`, UTC generation time, source row and label counts, unique/conflicting groups, affected conflict rows, review-status counts, approved training count and label distribution, and excluded unreviewed count. Derive every count from the same source/review/training collections written in that operation.

- [ ] **Step 5: Implement `prepare_review()` and pass its test**

When the target review CSV exists, load it to preserve valid approvals. Build current review records, training records, and audit in memory before writing any final output. Write review, training, and audit using the atomic helpers.

Run the focused end-to-end test and expect PASS.

- [ ] **Step 6: Write failing `build-training` and CLI tests**

Approve one temporary review row, call `build_training()`, and assert one lowercase-labelled training row and reconciled audit counts. Add an invalid approval case and a `main([...])` `--require-complete-review` case that raises validation through `SystemExit` with a nonzero code.

- [ ] **Step 7: Implement `build_training()` and `argparse` CLI**

Create subcommands matching the design:

```text
prepare-review --input PATH --output-dir PATH
build-training --review-file PATH --output-dir PATH [--require-complete-review]
```

For `build-training`, retain immutable source statistics and checksum from the existing audit file, then replace review/training-related counts from the current review and training rows. Return exit code zero on success and print concise row totals.

- [ ] **Step 8: Run the complete preparation test module**

Run: `\.venv\Scripts\python.exe -m unittest tests.analysis.training.test_prepare_bloom_dataset -v`

Expected: all preparation tests pass with no warnings or errors.

- [ ] **Step 9: Commit Task 3**

```powershell
git add src/analysis/training/prepare_bloom_dataset.py tests/analysis/training/test_prepare_bloom_dataset.py
git commit -m "feat: add Bloom dataset preparation CLI"
```

### Task 4: Generate and verify the real dataset artifacts

**Files:**
- Generate: `training_dataset/processed/dataset_v1_bloom_review.csv`
- Generate: `training_dataset/processed/dataset_v1_bloom_train.csv`
- Generate: `training_dataset/processed/dataset_v1_bloom_audit.json`
- Modify if needed: `.gitignore` only if generated research artifacts are already intentionally ignored; preserve the user's unrelated current edit.

**Interfaces:**
- Consumes: `training_dataset/dataset_v1_clean.csv` and the Task 3 CLI.
- Produces: the three verified research artifacts described in the design.

- [ ] **Step 1: Record the original checksum**

Run: `Get-FileHash -Algorithm SHA256 training_dataset\dataset_v1_clean.csv`

Save the displayed hash for the post-run comparison.

- [ ] **Step 2: Run real review preparation**

```powershell
.\.venv\Scripts\python.exe -m src.analysis.training.prepare_bloom_dataset prepare-review --input training_dataset\dataset_v1_clean.csv --output-dir training_dataset\processed
```

Expected: 6,633 source rows, 128 review groups, zero approved training rows.

- [ ] **Step 3: Verify artifact counts and schema**

Load all outputs with the module and assert:

```python
len(review_rows) == 128
len(training_rows) == 0
len({row["group_id"] for row in review_rows}) == 128
all(row["approved_bloom_level"] == "" for row in review_rows)
audit["source_rows"] == 6633
audit["unique_normalized_questions"] == 128
audit["approved_training_rows"] == 0
```

- [ ] **Step 4: Verify original integrity**

Run `Get-FileHash -Algorithm SHA256 training_dataset\dataset_v1_clean.csv` again and confirm it matches Step 1 and the audit checksum.

- [ ] **Step 5: Run focused and full regression suites**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.analysis.training.test_prepare_bloom_dataset -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: zero failures and zero errors.

- [ ] **Step 6: Inspect the final diff and artifact samples**

Run `git diff --check`, `git status --short`, display the CSV headers and first two review rows, and inspect the complete audit JSON. Confirm the user's pre-existing `.gitignore` modification was not overwritten.

- [ ] **Step 7: Commit generated artifacts**

```powershell
git add training_dataset/processed/dataset_v1_bloom_review.csv training_dataset/processed/dataset_v1_bloom_train.csv training_dataset/processed/dataset_v1_bloom_audit.json
git commit -m "data: prepare Bloom expert review dataset"
```

### Task 5: Final acceptance verification

**Files:**
- Verify only; no planned modifications.

**Interfaces:**
- Consumes: implementation, tests, and generated artifacts from Tasks 1-4.
- Produces: evidence-backed completion report.

- [ ] **Step 1: Run the exact focused and full verification commands again**

```powershell
.\.venv\Scripts\python.exe -m unittest tests.analysis.training.test_prepare_bloom_dataset -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

- [ ] **Step 2: Reconcile acceptance criteria**

Check every criterion in `docs/superpowers/specs/2026-08-03-bloom-dataset-preparation-design.md` against command output, output row counts, checksums, and audit fields.

- [ ] **Step 3: Report the manual next step**

Tell the user to fill only `approved_bloom_level` and optionally `review_notes` in the review CSV, using the six valid lowercase labels, then rerun `build-training --require-complete-review` before model training.

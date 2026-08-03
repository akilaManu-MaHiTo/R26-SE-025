# PONE Bloom Dataset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reproducibly extract all 741 source-labeled questions from two PONE supplementary DOCX files into a six-class Bloom dataset, quality-review artifact, grouped splits, and reconciled audit.

**Architecture:** A focused training-data module reads the paragraph-only DOCX XML with Python's standard library, maps legacy Bloom headings to model labels, creates provenance-rich rows and quality flags, then assigns whole normalized-question groups to deterministic stratified splits. It reuses the existing atomic artifact writer so all five CSV files and the JSON audit are committed as one set only after validation succeeds.

**Tech Stack:** Python 3 standard library (`zipfile`, `xml.etree.ElementTree`, `csv`, `json`, `hashlib`, `random`, `re`, `unicodedata`), existing `CognitiveBloomModel`, and `unittest`.

## Global Constraints

- Preserve both supplied DOCX source files unchanged.
- Retain all 741 questions; quality flags never exclude a row.
- Expected source counts are 141 rows from `pone.0230442.s001.docx` and 600 rows from `pone.0230442.s002.docx`.
- Expected labels are `remember=126`, `understand=123`, `apply=115`, `analyze=123`, `create=130`, and `evaluate=124`.
- Map Knowledge/Comprehension/Application/Analysis/Synthesis/Evaluation to remember/understand/apply/analyze/create/evaluate.
- Keep every duplicate row, but never split one `question_group_id` across train, validation, and test.
- Use deterministic 70/15/15 grouped splits with seed `42`.
- Do not add a DOCX parsing dependency; read `word/document.xml` directly.
- Do not train or replace `model/cognitive_bloom/cognitive_bloom_model.joblib`.

---

## File Structure

- Create `src/analysis/training/prepare_pone_bloom_dataset.py`: DOCX extraction, normalization, row identity, flags, grouped splitting, validation, auditing, atomic output, and CLI.
- Create `tests/analysis/training/test_prepare_pone_bloom_dataset.py`: unit, failure-path, CLI, atomicity, and model-loader compatibility tests.
- Create `training_dataset/processed/pone_bloom_v1.0/pone_bloom_full.csv`: all 741 rows.
- Create `training_dataset/processed/pone_bloom_v1.0/pone_bloom_train.csv`: grouped training rows.
- Create `training_dataset/processed/pone_bloom_v1.0/pone_bloom_validation.csv`: grouped validation rows.
- Create `training_dataset/processed/pone_bloom_v1.0/pone_bloom_test.csv`: grouped test rows.
- Create `training_dataset/processed/pone_bloom_v1.0/pone_bloom_quality_review.csv`: flagged rows plus review fields.
- Create `training_dataset/processed/pone_bloom_v1.0/pone_bloom_audit.json`: provenance and reconciled statistics.

---

### Task 1: Extract labeled questions from DOCX XML

**Files:**
- Create: `src/analysis/training/prepare_pone_bloom_dataset.py`
- Create: `tests/analysis/training/test_prepare_pone_bloom_dataset.py`

**Interfaces:**
- Consumes: DOCX path containing paragraph-only questions grouped under six legacy headings.
- Produces: `extract_docx_questions(path: Path) -> list[dict[str, object]]`, `normalize_question(value: object) -> str`, and constants `LEGACY_TO_MODEL`, `VALID_BLOOM_LEVELS`, `EXPECTED_SOURCE_COUNTS`.

- [ ] **Step 1: Write failing parser and mapping tests**

Create a minimal DOCX fixture helper using `zipfile.ZipFile` and this document XML shape:

```python
def write_docx(path: Path, paragraphs: list[str]) -> None:
    body = "".join(
        f"<w:p><w:r><w:t>{escape(text)}</w:t></w:r></w:p>"
        for text in paragraphs
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/'
        'wordprocessingml/2006/main"><w:body>'
        f"{body}</w:body></w:document>"
    )
    with ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", xml)
```

Add tests that assert:

```python
def test_extract_docx_maps_all_legacy_headings(self):
    paragraphs = [
        "Note: fixture",
        "Knowledge", "Recall a fact.",
        "Comprehension", "Explain a fact.",
        "Application", "Use the rule.",
        "Analysis", "Compare the cases.",
        "Synthesis", "Design a solution.",
        "Evaluation", "Judge the solution.",
    ]
    write_docx(self.source_path, paragraphs)
    rows = extract_docx_questions(self.source_path)
    self.assertEqual(
        [row["bloom_level"] for row in rows],
        ["remember", "understand", "apply", "analyze", "create", "evaluate"],
    )
    self.assertEqual(rows[0]["source_paragraph"], 2)
```

Also test missing `word/document.xml`, a non-note paragraph before the first heading, a missing heading, and an empty question paragraph being ignored.

- [ ] **Step 2: Run the focused tests and verify red state**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.analysis.training.test_prepare_pone_bloom_dataset -v
```

Expected: import failure because `prepare_pone_bloom_dataset` does not exist.

- [ ] **Step 3: Implement minimal extraction and normalization**

Define exact constants and signatures:

```python
LEGACY_TO_MODEL = {
    "knowledge": "remember",
    "comprehension": "understand",
    "application": "apply",
    "analysis": "analyze",
    "synthesis": "create",
    "evaluation": "evaluate",
}
VALID_BLOOM_LEVELS = tuple(LEGACY_TO_MODEL.values())
EXPECTED_SOURCE_COUNTS = {
    "pone.0230442.s001.docx": 141,
    "pone.0230442.s002.docx": 600,
}
WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

def normalize_question(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip()
    return " ".join(text.split())

def extract_docx_questions(path: Path) -> list[dict[str, object]]:
    ...
```

Read `word/document.xml`, iterate each `w:p`, join its descendant `w:t` values, and record the zero-based document paragraph index. Permit only blank paragraphs and `Note:` metadata before the first heading. Track all six encountered headings and raise `ValueError` if any are missing. Emit `original_question`, normalized `question`, lower-case legacy heading, mapped model label, source filename, and paragraph index.

- [ ] **Step 4: Run parser tests and verify green state**

Run the focused unittest command from Step 2.

Expected: all Task 1 tests pass.

- [ ] **Step 5: Commit Task 1**

```powershell
git add src/analysis/training/prepare_pone_bloom_dataset.py tests/analysis/training/test_prepare_pone_bloom_dataset.py
git commit -m "feat: extract PONE Bloom questions from DOCX"
```

---

### Task 2: Create stable rows, quality flags, and grouped splits

**Files:**
- Modify: `src/analysis/training/prepare_pone_bloom_dataset.py`
- Modify: `tests/analysis/training/test_prepare_pone_bloom_dataset.py`

**Interfaces:**
- Consumes: extracted dictionaries from `extract_docx_questions()`.
- Produces: `build_rows(source_paths: Sequence[Path]) -> list[dict[str, object]]`, `quality_flags(question: str) -> tuple[str, ...]`, and `assign_grouped_splits(rows: list[dict[str, object]], seed: int = 42) -> list[dict[str, object]]`.

- [ ] **Step 1: Write failing identity and flag tests**

Add assertions for stable identifiers and the fixed flag order:

```python
def test_build_rows_keeps_duplicates_and_flags_them(self):
    extracted = [
        source_record("Explain the diagram...", paragraph=2),
        source_record("Explain the diagram...", paragraph=3),
    ]
    with patch.object(module, "extract_docx_questions", return_value=extracted):
        rows = build_rows([Path("fixture.docx")])
    self.assertEqual(len(rows), 2)
    self.assertEqual(rows[0]["question_group_id"], rows[1]["question_group_id"])
    self.assertNotEqual(rows[0]["row_id"], rows[1]["row_id"])
    self.assertEqual(
        rows[0]["quality_flags"],
        "placeholder|missing_context|exact_duplicate",
    )
```

Test `very_short`, `possible_language_error`, and `none` separately. Verify NFKC and whitespace normalization without spelling correction.

- [ ] **Step 2: Write failing grouped-split tests**

Build at least ten unique groups per class plus a duplicate group and assert:

```python
assigned = assign_grouped_splits(rows, seed=42)
self.assertEqual(len(assigned), len(rows))
self.assertEqual({row["split"] for row in assigned}, {"train", "validation", "test"})
for group_id in {row["question_group_id"] for row in assigned}:
    self.assertEqual(
        len({row["split"] for row in assigned if row["question_group_id"] == group_id}),
        1,
    )
self.assertEqual(assigned, assign_grouped_splits(rows, seed=42))
```

Also assert that a normalized duplicate group containing two different Bloom labels raises `ValueError`.

- [ ] **Step 3: Run Task 2 tests and verify red state**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.analysis.training.test_prepare_pone_bloom_dataset -v
```

Expected: failures for missing row-building, flagging, and split functions.

- [ ] **Step 4: Implement row identity and quality flags**

Use these stable IDs:

```python
def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"

row_id = _stable_id("pone-row", f"{source_document}:{source_paragraph}")
question_group_id = _stable_id("pone-question", question.casefold())
```

Detect flags with narrow compiled patterns:

```python
FLAG_ORDER = (
    "placeholder",
    "missing_context",
    "very_short",
    "possible_language_error",
    "exact_duplicate",
)
PLACEHOLDER_RE = re.compile(r"_{2,}|\.{3,}|…")
MISSING_CONTEXT_RE = re.compile(
    r"\b(above|below|following|diagram|picture|graph|passage|questionnaire|"
    r"table|selected information|story|text|article)\b",
    re.IGNORECASE,
)
LANGUAGE_ERROR_RE = re.compile(
    r"\b(the the|pictoral|cach |does .+ stands|did he took|"
    r"difference parts|a eukaryotic)\b",
    re.IGNORECASE,
)
```

Compute `exact_duplicate` only after grouping all emitted rows. Serialize no flags as `none`; otherwise join flags in `FLAG_ORDER` with `|`.

- [ ] **Step 5: Implement deterministic grouped stratification**

Validate that every question group contains a single label. For each label, sort groups by SHA-256 of `f"{seed}:{group_id}"`, allocate `round(group_count * 0.15)` groups to validation, the same number to test, and the remainder to train. Apply the chosen split to every row in the group. Return rows in their original source order.

- [ ] **Step 6: Run Task 2 tests and verify green state**

Run the focused unittest command.

Expected: all Task 1 and Task 2 tests pass.

- [ ] **Step 7: Commit Task 2**

```powershell
git add src/analysis/training/prepare_pone_bloom_dataset.py tests/analysis/training/test_prepare_pone_bloom_dataset.py
git commit -m "feat: flag and split PONE Bloom rows"
```

---

### Task 3: Validate and atomically write the artifact set

**Files:**
- Modify: `src/analysis/training/prepare_pone_bloom_dataset.py`
- Modify: `tests/analysis/training/test_prepare_pone_bloom_dataset.py`

**Interfaces:**
- Consumes: assigned rows from `assign_grouped_splits()` and source paths.
- Produces: `build_audit(source_paths, rows) -> dict[str, object]`, `validate_dataset(source_paths, rows, audit) -> None`, and `build_dataset(source_paths: Sequence[Path], output_dir: Path) -> dict[str, object]`.

- [ ] **Step 1: Write failing audit and validation tests**

Assert the audit contains:

```python
self.assertEqual(audit["pipeline_version"], "1.0.0")
self.assertEqual(audit["total_rows"], len(rows))
self.assertEqual(audit["label_distribution"]["remember"], expected_remember)
self.assertEqual(sum(audit["split_counts"].values()), len(rows))
self.assertEqual(audit["source_documents"][0]["sha256"], sha256_file(source_path))
```

Add rejection tests for a missing source, wrong per-source count, wrong total, unsupported label, duplicate `row_id`, empty question, missing class, duplicate group crossing splits, and audit/row disagreement.

- [ ] **Step 2: Write failing atomic artifact test**

Patch `src.analysis.training.prepare_bloom_dataset.os.replace` so replacing `pone_bloom_audit.json` raises `OSError`. Prepopulate all destination files with sentinel bytes, call `build_dataset()`, and assert every sentinel file remains unchanged after rollback.

- [ ] **Step 3: Run Task 3 tests and verify red state**

Run the focused unittest command.

Expected: failures for missing audit, validation, and build functions.

- [ ] **Step 4: Implement audit and validation**

Define:

```python
PIPELINE_VERSION = "1.0.0"
CSV_FIELDNAMES = (
    "row_id", "question_group_id", "question", "original_question",
    "bloom_level", "legacy_bloom_level", "source_document",
    "source_paragraph", "quality_flags", "split",
)
QUALITY_REVIEW_FIELDNAMES = CSV_FIELDNAMES + ("review_status", "review_notes")
```

The audit must include `generated_at_utc`, source filenames/absolute paths/hashes/counts, total and unique-question counts, label distribution, flag counts, flagged-row count, exact-duplicate group count, split counts, split label distributions, and pipeline version. Validation compares actual counts against `EXPECTED_SOURCE_COUNTS` and the fixed six-class distribution, verifies exactly 741 rows, and reconciles every audit field.

- [ ] **Step 5: Implement atomic artifact generation**

Import and reuse:

```python
from src.analysis.training.prepare_bloom_dataset import (
    sha256_file,
    write_artifact_set_atomic,
)
```

Build `full`, `train`, `validation`, and `test` row lists. Build quality-review rows by copying every row whose flags are not `none` and adding `review_status="needs_review"` and `review_notes=""`. Call `write_artifact_set_atomic()` once with all five CSV destinations and the audit JSON destination.

- [ ] **Step 6: Run Task 3 tests and verify green state**

Run the focused unittest command.

Expected: all focused tests pass, including rollback.

- [ ] **Step 7: Commit Task 3**

```powershell
git add src/analysis/training/prepare_pone_bloom_dataset.py tests/analysis/training/test_prepare_pone_bloom_dataset.py
git commit -m "feat: build audited PONE Bloom artifacts"
```

---

### Task 4: Add the CLI, generate the real dataset, and run integration checks

**Files:**
- Modify: `src/analysis/training/prepare_pone_bloom_dataset.py`
- Modify: `tests/analysis/training/test_prepare_pone_bloom_dataset.py`
- Create: `training_dataset/processed/pone_bloom_v1.0/pone_bloom_full.csv`
- Create: `training_dataset/processed/pone_bloom_v1.0/pone_bloom_train.csv`
- Create: `training_dataset/processed/pone_bloom_v1.0/pone_bloom_validation.csv`
- Create: `training_dataset/processed/pone_bloom_v1.0/pone_bloom_test.csv`
- Create: `training_dataset/processed/pone_bloom_v1.0/pone_bloom_quality_review.csv`
- Create: `training_dataset/processed/pone_bloom_v1.0/pone_bloom_audit.json`

**Interfaces:**
- Consumes: two explicit `--input` paths and `--output-dir`.
- Produces: CLI exit status `0`, printed reconciled summary, and the complete artifact set.

- [ ] **Step 1: Write failing CLI tests**

Call:

```python
result = main([
    "--input", str(source_one),
    "--input", str(source_two),
    "--output-dir", str(output_dir),
])
self.assertEqual(result, 0)
```

Patch `EXPECTED_SOURCE_COUNTS` to fixture counts. Assert output contains total rows, per-class counts, flagged rows, and output directory. Add a failure test for passing one input or duplicate paths.

- [ ] **Step 2: Run CLI tests and verify red state**

Run the focused unittest command.

Expected: CLI tests fail because `main()` is not implemented.

- [ ] **Step 3: Implement the CLI**

Use `argparse` with repeatable required `--input`, required `--output-dir`, and optional `--seed` defaulting to `42`. Require exactly two distinct source paths. Catch `OSError`, `ValueError`, `zipfile.BadZipFile`, and `ET.ParseError` through `parser.error()` and print the audit summary after a successful build.

- [ ] **Step 4: Run focused and complete tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.analysis.training.test_prepare_pone_bloom_dataset -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: zero failures and zero errors.

- [ ] **Step 5: Generate real artifacts from the supplied documents**

Run:

```powershell
.\.venv\Scripts\python.exe -m src.analysis.training.prepare_pone_bloom_dataset `
  --input "C:\Users\liyan\OneDrive\Documents\SLIIT\Y4\Research\Dataset\bloom model\pone.0230442.s001.docx" `
  --input "C:\Users\liyan\OneDrive\Documents\SLIIT\Y4\Research\Dataset\bloom model\pone.0230442.s002.docx" `
  --output-dir training_dataset\processed\pone_bloom_v1.0
```

Expected summary: 741 total rows with the exact six-class counts in Global Constraints.

- [ ] **Step 6: Verify artifact invariants and model compatibility**

Run a read-only verification script that loads every CSV with `load_tabular_dataset()`, checks the split union equals the 741 full row IDs, ensures split row-ID sets are disjoint, ensures each group has one split, verifies source hashes, and fits without saving:

```python
rows = load_tabular_dataset(output_dir / "pone_bloom_train.csv")
model = CognitiveBloomModel(model_path=None).fit(rows)
assert set(model.pipeline.classes_) == {
    "remember", "understand", "apply", "analyze", "create", "evaluate"
}
```

Expected: all assertions pass and no joblib file is written.

- [ ] **Step 7: Commit the implementation and generated dataset**

```powershell
git add src/analysis/training/prepare_pone_bloom_dataset.py `
  tests/analysis/training/test_prepare_pone_bloom_dataset.py `
  training_dataset/processed/pone_bloom_v1.0 `
  docs/superpowers/plans/2026-08-04-pone-bloom-dataset.md
git commit -m "data: build six-class PONE Bloom dataset"
```

---

## Final Verification

- [ ] Confirm `git status --short` shows only the user's pre-existing unrelated changes.
- [ ] Re-run the focused dataset test module.
- [ ] Re-run the complete repository test discovery command.
- [ ] Re-run the artifact-invariant and in-memory model-fit verification.
- [ ] Inspect `pone_bloom_audit.json` and confirm all counts reconcile.
- [ ] Confirm `model/cognitive_bloom/cognitive_bloom_model.joblib` was not modified.

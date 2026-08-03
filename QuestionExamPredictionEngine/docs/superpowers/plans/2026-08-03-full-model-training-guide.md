# Full Model Training Guide Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create `FULL_MODEL_TRAINING_GUIDE.md` at the repository root that gives a research-honest, single entry point for building, evaluating, saving, and integrating every model in the intended four-domain-agent architecture.

**Architecture:** The guide is a standalone markdown deliverable (no new Python code). It documents verified repository facts, marks partially implemented and proposed capabilities explicitly, and uses one consistent status vocabulary and one training workflow sequence. Every percentage and command must be reproducible from the repository at the time of writing.

**Tech Stack:** Markdown only; verification uses PowerShell + the repository's `.venv` Python (`\.venv\Scripts\python.exe`) and `git`.

## Global Constraints

- Deliverable path is exactly the repository root: `FULL_MODEL_TRAINING_GUIDE.md`.
- Distinguish three states: verified in repo, partial-but-unvalidated, proposed-not-implemented.
- Four domain agents plus one orchestrator; the orchestrator is never counted as a domain agent or trainable model.
- Bloom results must use the six separate indicators in the design, never one misleading percentage.
- Status vocabulary is exactly: `Operational`, `Pilot`, `Partial`, `Not started`, `Not trainable`.
- Windows/PowerShell commands only for existing trainers; Colab workflows only for GPU-beneficial or proposed models; proposed commands must be labelled future scaffolding.
- Every file link must resolve from the repository root; every percentage must be recomputable from stated counts.
- Do not modify any source file, training script, model artifact, or dataset. This plan writes documentation only.
- Preserve the staged `model/cognitive_bloom/cognitive_bloom_model.joblib` change; it is evidence the Bloom model was retrained on the 128-row approved dataset.

---

## File structure

- Create: `FULL_MODEL_TRAINING_GUIDE.md` — the single deliverable, assembled section by section across tasks.

No other files are created or modified. Task boundaries are chosen so each task writes one or two self-contained sections and ends with a fact-verification step.

## Verified repository facts (authoritative for all tasks)

Gathered on 2026-08-03; each task's content must agree with these exact values.

**Agents and orchestrator:**
- `src/agents/question_knowledge_agent.py` — `QuestionKnowledgeAgent`, topic mapping, Bloom detection, rubric criteria.
- `src/agents/answer_misconception_agent.py` — `AnswerMisconceptionAgent`, per-answer analytical scores.
- `src/agents/cohort_prediction_agent.py` — `CohortPredictionAgent`, weak topics, misunderstood questions, cognitive gaps, descriptive trends.
- `src/agents/orchestrator.py` — `ExamAnalysisOrchestrator`, coordinates the three agents, records `context.model_versions`, isolates item-level failures.
- `src/agents/contracts.py` — `QuestionMappingResult`, `AnswerAnalysisResult`, `CohortPredictionResult`, `FutureTopicProbability`, `AgentRunContext`.
- `src/agents/model_registry.py` — `ModelRegistry` with `register`, `get`, `try_get`, `versions`, `statuses`.

**Registry entries** (`src/api/dependencies.py:83-97`):
- `similarity` version `exam-similarity-local-v1` → `get_similarity_model`.
- `weak_topic` version `weak-topic-local-v1` → `get_weak_topic_model`.
- `cognitive_bloom` version `cognitive-bloom-local-v1` → `get_cognitive_bloom_model`.

**Saved artifacts:**
- `model/similarity/exam_similarity_model/` — SentenceTransformer fine-tuned from `all-MiniLM-L6-v2`, CosineSimilarityLoss, 5 epochs, 341 training samples, dataset_size `341` in README front matter.
- `model/weak_topic/weak_topic_model.joblib` — `StandardScaler` + `LogisticRegression`, 10 features, `weak_probability_threshold=0.55`.
- `model/cognitive_bloom/cognitive_bloom_model.joblib` — metadata: `training_rows=128`, `label_counts={"understand": 96, "remember": 32}`, `validation_accuracy=1.0`, validation report supports `remember=7` / `understand=19`, macro avg f1 `1.0`.

**Training CLIs (verified via `--help`):**
- `python -m src.analysis.training.train_cognitive_bloom_model --input PATH --output PATH --label-column bloom_level --text-columns question answer source_text summary topic subtopic difficulty language cognitive_skill`
- `python -m src.analysis.training.train_weak_topic_model --input PATH --output PATH --weak-threshold 0.5`
- `python -m src.analysis.training.prepare_bloom_dataset prepare-review --input PATH --output-dir PATH`
- `python -m src.analysis.training.prepare_bloom_dataset build-training --review-file PATH --output-dir PATH [--require-complete-review]`
- `python -m src.analysis.training.train_model` (no CLI; hard-coded `data/train_data_v2.json` → `model/similarity/exam_similarity_model`).

**Bloom dataset artifacts** (`training_dataset/processed/`):
- `dataset_v1_bloom_review.csv` — header: `group_id,question,normalized_question,source_row_count,observed_labels,label_counts,subjects,topics,subtopics,source_ids,approved_bloom_level,review_status,review_notes`.
- `dataset_v1_bloom_train.csv` — 128 rows; 32 `remember`, 96 `understand`; header: `group_id,question,bloom_level,source_row_count,review_status,review_notes`.
- `dataset_v1_bloom_audit.json` — `source_rows=6633`, `unique_normalized_questions=128`, `conflicting_question_groups=128`, `approved_training_rows=128`, `approved_training_label_distribution={"remember": 32, "understand": 96}`, `input_sha256=8374a5bc0a4fade4f9ab6d9ef7371cd895b6f1591f52733ad25c64f9a2a155d4`.

**Regression command:** `\.venv\Scripts\python.exe -m unittest discover -s tests -v`

**Proposal checklist:** `PROPOSAL_IMPLEMENTATION_CHECKLIST.md` (Bloom = Partial, predictive analytics = Partial, clustering/forecasting/generation = Not started).

---

### Task 1: Scaffold the guide: title, purpose, audience, target architecture, status legend

**Files:**
- Create: `FULL_MODEL_TRAINING_GUIDE.md`

**Interfaces:**
- Produces: the document skeleton and Sections 1-3 that all later tasks append into.

- [ ] **Step 1: Create `FULL_MODEL_TRAINING_GUIDE.md` with the header and purpose**

Write the file with this opening:

```markdown
# Full Model Training Guide

**Date:** 2026-08-03
**Scope:** Every model required by the intended four-domain-agent architecture in this repository.

## 1. Purpose

This guide is the single entry point for building, evaluating, saving, and integrating every model in the
intended four-domain-agent architecture. It is intentionally research-honest: it separates three states of
truth so you never confuse a demo artifact with a validated model:

- **Verified in this repository** — capabilities and artifacts you can reproduce today.
- **Partial implementation, not research-validated** — code exists but essential data, evaluation, or
  integration is missing.
- **Proposed, not implemented** — described for future scaffolding only.

The orchestrator is a workflow component and is **not** a domain agent or a trainable model.

## 2. Audience

A fourth-year undergraduate researcher. You should understand basic Python, work in Windows PowerShell
locally, and use Google Colab for GPU-assisted experiments. You do **not** need to know the repository internals.
```

- [ ] **Step 2: Add the target architecture section**

Append `## 3. Target architecture` listing the four domain agents and the orchestrator, and the current-state statement. Use these exact four domain agents and note the repo currently holds three agent classes:

```markdown
1. **Question and Rubric Knowledge Agent** — topic mapping, rubric mapping, Bloom classification, and future retrieval-backed evidence.
2. **Answer Grading and Misconception Agent** — semantic answer similarity, deterministic grading, concept analysis, and future misconception classification.
3. **Student and Cohort Cognitive Analytics Agent** — weak-topic classification, cognitive-gap analysis, misunderstood-question analysis, and cohort summaries.
4. **Exam Prediction and Question Generation Agent** — future-topic forecasting, question-structure prediction, and controlled question generation after prediction models are validated.
5. **Exam Analysis Orchestrator** — coordinates the four agents, records model versions, isolates failures, and persists results; it is not trained.

**Current repository state:** three domain-agent classes exist —
`QuestionKnowledgeAgent` (`src/agents/question_knowledge_agent.py`),
`AnswerMisconceptionAgent` (`src/agents/answer_misconception_agent.py`), and
`CohortPredictionAgent` (`src/agents/cohort_prediction_agent.py`) — coordinated by
`ExamAnalysisOrchestrator` (`src/agents/orchestrator.py`). The target four-agent architecture requires
splitting cohort analytics from future exam prediction/generation, or adding a fourth agent without
counting the orchestrator.
```

- [ ] **Step 3: Add the status legend**

Append `## 4. Status legend` with the five evidence-based categories and the citation rule:

```markdown
- **Operational** — implemented and usable for its stated current scope.
- **Pilot** — trained or implemented but not research-valid for the intended scope.
- **Partial** — a useful implementation exists, but essential data, evaluation, or integration is missing.
- **Not started** — no substantive trainable implementation or artifact exists.
- **Not trainable** — deterministic workflow or orchestration component.

Every status below cites a repository file, artifact, command output, or explicitly missing acceptance gate.
```

- [ ] **Step 4: Verify scaffolding**

Run: `Select-String -Path FULL_MODEL_TRAINING_GUIDE.md -Pattern '## 1. Purpose','## 2. Audience','## 3. Target architecture','## 4. Status legend'`

Expected: all four headings present. Confirm the file path is the repository root: `Test-Path -LiteralPath FULL_MODEL_TRAINING_GUIDE.md` must print `True`.

- [ ] **Step 5: Commit**

```powershell
git add FULL_MODEL_TRAINING_GUIDE.md
git commit -m "docs: scaffold full model training guide"
```

### Task 2: Add the model inventory status table

**Files:**
- Modify: `FULL_MODEL_TRAINING_GUIDE.md`

**Interfaces:**
- Consumes: verified facts above (registry entries, artifacts, audit JSON, proposal checklist).
- Produces: the master status table that the per-model sections later expand.

- [ ] **Step 1: Append `## 5. Model inventory`**

Write the master table with these exact rows, statuses, and evidence:

```markdown
| # | Model / capability | Agent owner | Status | Key evidence |
|---|---|---|---|---|
| 1 | Cognitive Bloom classifier | Question & Rubric Knowledge; Answer Grading & Misconception | Pilot | `model/cognitive_bloom/cognitive_bloom_model.joblib`; two-class only |
| 2 | Topic/rubric mapper + future retrieval embedding | Question & Rubric Knowledge | Partial | `src/analytics/topic_utils.py`; no retrieval embedder |
| 3 | Sentence-transformer answer-similarity model | Answer Grading & Misconception | Operational | `model/similarity/exam_similarity_model/`; README dataset_size 341 |
| 4 | Misconception classifier / bounded extraction | Answer Grading & Misconception | Not started | `Misconception` contract exists; no trainer or artifact |
| 5 | Weak-topic classifier | Student & Cohort Cognitive Analytics | Pilot | `model/weak_topic/weak_topic_model.joblib`; bootstrapped labels |
| 6 | Future-topic forecasting/ranking model | Exam Prediction & Question Generation | Not started | `future_topic_probabilities=[]` in `src/agents/cohort_prediction_agent.py:102` |
| 7 | Question-structure prediction model | Exam Prediction & Question Generation | Not started | no structure schema or trainer |
| 8 | Controlled question-generation / shared instruction model | Exam Prediction & Question Generation | Not started | no generator code |
| — | Rule-based analytics (weak-topic rule, thresholds) | all | Not trainable | deterministic functions |
| — | Exam Analysis Orchestrator | — | Not trainable | `src/agents/orchestrator.py` |
```

- [ ] **Step 2: Add the "not trainable" clarification paragraph**

```markdown
Rule-based analytics and the orchestrator are documented here so ownership is clear, but they are **not**
trainable models and have no training sections.
```

- [ ] **Step 3: Verify every file link resolves**

Run:

```powershell
$paths = @(
  'model/cognitive_bloom/cognitive_bloom_model.joblib',
  'src/analytics/topic_utils.py',
  'model/similarity/exam_similarity_model/',
  'model/weak_topic/weak_topic_model.joblib',
  'src/agents/cohort_prediction_agent.py',
  'src/agents/orchestrator.py'
)
$paths | ForEach-Object { "$_ -> $(Test-Path -LiteralPath $_)" }
```

Expected: every line prints `True`.

- [ ] **Step 4: Commit**

```powershell
git add FULL_MODEL_TRAINING_GUIDE.md
git commit -m "docs: add model inventory status table"
```

### Task 3: Add the Bloom-model percentage policy section

**Files:**
- Modify: `FULL_MODEL_TRAINING_GUIDE.md`

**Interfaces:**
- Consumes: joblib metadata and audit JSON values from the verified facts.
- Produces: Section 6, replacing any single-percentage summary of the Bloom model.

- [ ] **Step 1: Append `## 6. Bloom-model results: separate indicators, no single percentage`**

Write exactly these six reproducible indicators plus the status sentence:

```markdown
| Indicator | Value | Source / computation |
|---|---|---|
| Internal validation accuracy | 100% | random 80/20 split in `CognitiveBloomModel.fit()` |
| Label-space coverage | 33.3% | 2 observed labels / 6 intended Bloom levels |
| Higher-order coverage | 0% | no `apply`, `analyze`, `evaluate`, or `create` rows |
| Dataset distribution | 25% remember, 75% understand | 32 and 96 of 128 unique questions |
| Research-valid six-class accuracy | not measurable | no independent, balanced six-class test set exists |
| Status | two-class pilot only | the 100% score is driven by repeated question templates; it is not six-class generalization |

Sources: `training_dataset/processed/dataset_v1_bloom_audit.json`
(`approved_training_label_distribution`), `model/cognitive_bloom/cognitive_bloom_model.joblib`
metadata (`label_counts`, `validation_accuracy`, `validation_report`).
```

- [ ] **Step 2: Add the next-evaluation recommendation**

```markdown
The next evaluation must report **macro-F1**, per-class precision/recall/F1, confusion matrices, and use
**independently authored or template-grouped** test data — not a random split that keeps templates in both
partitions.
```

- [ ] **Step 3: Verify the percentages are reproducible from stated counts**

Run:

```powershell
.\.venv\Scripts\python.exe -c "import json; a=json.load(open(r'training_dataset\processed\dataset_v1_bloom_audit.json')); d=a['approved_training_label_distribution']; n=sum(d.values()); print(n, d['remember']/n, d['understand']/n, len(d)/6)"
```

Expected output: `128 0.25 0.75 0.3333333333333333`. Confirm 0.25 → 25% and 0.75 → 75% match the table.

- [ ] **Step 4: Commit**

```powershell
git add FULL_MODEL_TRAINING_GUIDE.md
git commit -m "docs: add Bloom indicator policy"
```

### Task 4: Add the shared 10-step training workflow format

**Files:**
- Modify: `FULL_MODEL_TRAINING_GUIDE.md`

**Interfaces:**
- Produces: Section 7, the canonical sequence every trainable-model section below reuses.

- [ ] **Step 1: Append `## 7. Training workflow format`**

Write the ten steps verbatim:

```markdown
Every trainable-model section below follows this sequence:

1. Define the prediction target and the agent that consumes it.
2. Specify the minimum dataset schema and the expert-labelled fields.
3. Define leakage-safe train / validation / test splitting (group duplicates and paraphrases; never random-split templates).
4. Train a simple, reproducible baseline first.
5. Train an advanced comparison model only when dataset size supports it.
6. Evaluate with metrics appropriate to the target (see each section).
7. Save the model, label mapping, preprocessing configuration, metrics, and a data fingerprint.
8. Integrate through `ModelRegistry` (`src/agents/model_registry.py`) or a stable adapter.
9. Run smoke, regression, and out-of-distribution tests.
10. Promote the model only after its stated research gate passes.

Commands below are Windows/PowerShell for existing repository trainers. Colab workflows appear only where
GPU training or a proposed model benefits from them. **Proposed commands are labelled future scaffolding and
do not exist in this repository yet.**
```

- [ ] **Step 2: Verify the registry and training modules exist**

Run:

```powershell
$paths = @(
  'src/agents/model_registry.py',
  'src/analysis/training/train_cognitive_bloom_model.py',
  'src/analysis/training/train_weak_topic_model.py',
  'src/analysis/training/train_model.py',
  'src/analysis/training/prepare_bloom_dataset.py'
)
$paths | ForEach-Object { "$_ -> $(Test-Path -LiteralPath $_)" }
```

Expected: all print `True`.

- [ ] **Step 3: Commit**

```powershell
git add FULL_MODEL_TRAINING_GUIDE.md
git commit -m "docs: add training workflow format"
```

### Task 5: Add per-model sections for the three existing (verified) models

**Files:**
- Modify: `FULL_MODEL_TRAINING_GUIDE.md`

**Interfaces:**
- Consumes: CLI help output already verified; joblib metadata.
- Produces: Sections 8.1 (Bloom), 8.2 (similarity), 8.3 (weak topic) with runnable commands.

- [ ] **Step 1: Append `## 8. Model sections` and `### 8.1 Cognitive Bloom classifier`**

Include: owner agents, purpose, current implementation path, dataset schema, recommended first model
(TF-IDF + LogisticRegression, already implemented), optional advanced model (sentence-transformer or
BERT-style fine-tune on Colab), artifact path, evaluation metrics (macro-F1, per-class P/R/F1, confusion
matrix, template-grouped holdout), integration point (`ModelRegistry` name `cognitive_bloom`), and the
completion gate: *a balanced, independently authored six-class test set with a reported macro-F1, plus
`apply`/`analyze`/`evaluate`/`create` rows*. Then include the verified command:

```powershell
\.venv\Scripts\python.exe -m src.analysis.training.train_cognitive_bloom_model --input training_dataset\processed\dataset_v1_bloom_train.csv --output model\cognitive_bloom\cognitive_bloom_model.joblib --label-column bloom_level
```

Add a note that `train_model.py`'s previous metadata reported **16.68% validation accuracy on 4,855 rows**
per `PROPOSAL_IMPLEMENTATION_CHECKLIST.md`; that artifact was superseded by the 128-row approved dataset and
the current `validation_accuracy=1.0` two-class pilot.

- [ ] **Step 2: Append `### 8.2 Sentence-transformer answer-similarity model`**

Include: owner (Answer Grading and Misconception Agent), purpose (semantic answer similarity), current
implementation (`model/similarity/exam_similarity_model/`, fine-tuned from `all-MiniLM-L6-v2`,
CosineSimilarityLoss, 5 epochs, 341 samples), training data (`data/train_data_v2.json`), recommended first
model (the existing fine-tune), advanced model (larger multilingual sentence transformer on Colab), artifact
path, evaluation metrics (held-out pair similarity correlation / retrieval Precision@K against a labelled
triplet set — must be added), integration point (`ModelRegistry` name `similarity`), completion gate:
*held-out similarity evaluation on labelled pairs, no grading-mark influence*. Include the verified command:

```powershell
\.venv\Scripts\python.exe -m src.analysis.training.train_model
```

Label this command as the only existing trainer that is a script with hard-coded paths (no CLI arguments),
and note the artifact is registered at version `exam-similarity-local-v1`.

- [ ] **Step 3: Append `### 8.3 Weak-topic classifier`**

Include: owner (Student and Cohort Cognitive Analytics Agent), purpose (weak-topic classification), current
implementation (`model/weak_topic/weak_topic_model.joblib`, `StandardScaler` + `LogisticRegression`, 10
features), training data (topic feature rows from student reports, labels bootstrapped by the
`weak_threshold` / `minimum_students` / `minimum_below_share` rule in `build_topic_feature_rows`), evaluation
metrics (weak-topic precision/recall/F1 vs instructor judgement — currently missing), integration point
(`ModelRegistry` name `weak_topic`), completion gate: *a lecturer-labelled weak/non-weak topic set proving
the classifier beats the deterministic rule*. Include the verified command:

```powershell
\.venv\Scripts\python.exe -m src.analysis.training.train_weak_topic_model --input data\traindata\student_data_V3.json --output model\weak_topic\weak_topic_model.joblib --weak-threshold 0.5
```

Add an explicit warning: because labels are derived from the same score thresholds the model predicts, the
status is **Pilot**, not Operational.

- [ ] **Step 4: Verify each command runs its CLI help without errors**

Run:

```powershell
\.venv\Scripts\python.exe -m src.analysis.training.train_cognitive_bloom_model --help
\.venv\Scripts\python.exe -m src.analysis.training.train_weak_topic_model --help
```

Expected: both print usage and exit 0. (Do not run `train_model.py`; it trains and would rewrite the artifact.)

- [ ] **Step 5: Commit**

```powershell
git add FULL_MODEL_TRAINING_GUIDE.md
git commit -m "docs: document existing model training sections"
```

### Task 6: Add per-model sections for the proposed (not-started) models

**Files:**
- Modify: `FULL_MODEL_TRAINING_GUIDE.md`

**Interfaces:**
- Consumes: `CohortPredictionResult.future_topic_probabilities` contract and design delivery phases.
- Produces: Sections 8.4-8.7, all clearly labelled future scaffolding.

- [ ] **Step 1: Append `### 8.4 Topic/rubric mapper and retrieval embedding model`**

Mark status **Partial**. Describe: owner (Question and Rubric Knowledge Agent); current implementation
(`src/analytics/topic_utils.py` canonical topic resolution); missing pieces (a retrieval embedding model, a
ChromaDB ingestion/query path per the agent-architecture design, citations); proposed first model
(sentence-transformer embedding + ChromaDB); evaluation (retrieval Precision@K on a labelled
lecture-chunk holdout); integration (`ModelRegistry` entry `lecture_retrieval`); completion gate.
Include a Colab-scaffolding block labelled **Proposed — not implemented** that downloads a
sentence-transformer and exports embeddings.

- [ ] **Step 2: Append `### 8.5 Misconception classifier or bounded extraction model`**

Mark status **Not started**. Note the `Misconception` Pydantic contract already exists in
`src/agents/contracts.py` but no extractor or trainer exists. Requirements: lecturer-labelled answers with
known misconceptions; metrics = misconception-label precision, recall, and citation validity; integration via
`ModelRegistry` name `misconception_extractor`; completion gate = precision/recall against labelled data with
a deterministic fallback that never changes the mark.

- [ ] **Step 3: Append `### 8.6 Future-topic forecasting and question-structure prediction models`**

Mark status **Not started**. State that `CohortPredictionResult.future_topic_probabilities` is currently
always `[]` (`src/agents/cohort_prediction_agent.py:102`). Requirements: temporal feature table (topic
recurrence, year, marks, frequency, cognitive level, difficulty), train-through-year-`Y` / predict-`Y+1`
validation only, baselines (frequency, recency), metrics Precision@K / Recall@K / Brier score / calibration,
and an evaluation artifact recording supported course, training years, metrics, and calibration status.
Question-structure prediction needs a defined structure schema (type, Bloom level, marks, parts, wording
pattern) that does not exist yet. Include a Colab-scaffolding block labelled **Proposed — not implemented**.

- [ ] **Step 4: Append `### 8.7 Controlled question-generation model`**

Mark status **Not started**. Requirements: generate from a predicted topic/Bloom/difficulty/marks/structure;
add answer/rubric generation, duplication and leakage checks, factual validation, lecturer review/approval,
and generation-quality evaluation. State clearly it must not run until the prediction models pass their gates.

- [ ] **Step 5: Verify the contract fields referenced exist**

Run:

```powershell
Select-String -Path src\agents\contracts.py -Pattern 'future_topic_probabilities','class Misconception','class FutureTopicProbability'
```

Expected: three matches. Confirm `future_topic_probabilities` also appears in `src\agents\cohort_prediction_agent.py`.

- [ ] **Step 6: Commit**

```powershell
git add FULL_MODEL_TRAINING_GUIDE.md
git commit -m "docs: document proposed model sections"
```

### Task 7: Add the error-prevention and research-safeguards section

**Files:**
- Modify: `FULL_MODEL_TRAINING_GUIDE.md`

**Interfaces:**
- Consumes: design section 8 and the verified repo facts.
- Produces: Section 9 with the nine explicit prohibitions.

- [ ] **Step 1: Append `## 9. Error prevention and research safeguards`**

Write these nine items:

```markdown
This guide and the repository explicitly prevent the following mistakes:

1. Treating the orchestrator as another AI model — it is a workflow component.
2. Claiming every agent requires its own large language model — most capabilities are statistical models.
3. Reporting template-driven validation accuracy as external performance — the 100% Bloom figure is a two-class pilot.
4. Creating artificial class balance by assigning incorrect Bloom labels — labels must come from expert review.
5. Splitting duplicates or paraphrases across training and test sets — group by `group_id` before splitting.
6. Calling historical trends a future forecast — `historical_trends` is descriptive; probabilities are disabled until validation.
7. Allowing an optional language model to silently change deterministic marks — marks stay authoritative.
8. Publishing forecast probabilities without temporal validation and calibration — `future_topic_probabilities` stays empty until a gate passes.
9. Training from student data without documented privacy, consent, and anonymization controls — student identifiers are pseudonymous and never logged by default.
```

- [ ] **Step 2: Verify the two enforcement points are real**

Run:

```powershell
Select-String -Path src\agents\cohort_prediction_agent.py -Pattern 'future_topic_probabilities='
Select-String -Path src\agents\orchestrator.py -Pattern 'with_defaults'
```

Expected: one `future_topic_probabilities=[]` match and one `with_defaults` match.

- [ ] **Step 3: Commit**

```powershell
git add FULL_MODEL_TRAINING_GUIDE.md
git commit -m "docs: add error prevention safeguards"
```

### Task 8: Final acceptance verification and completion report

**Files:**
- Verify only; fix links or numbers in `FULL_MODEL_TRAINING_GUIDE.md` only if a check fails.

**Interfaces:**
- Consumes: the complete guide and the design's verification checklist.
- Produces: evidence-backed completion report.

- [ ] **Step 1: Run the repository regression suite**

Run:

```powershell
\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expected: zero failures and zero errors. This proves the guide's claim that the current workflow is tested.

- [ ] **Step 2: Re-verify all file links and headings**

Run:

```powershell
$paths = @(
  'FULL_MODEL_TRAINING_GUIDE.md',
  'model/cognitive_bloom/cognitive_bloom_model.joblib',
  'model/weak_topic/weak_topic_model.joblib',
  'model/similarity/exam_similarity_model/',
  'training_dataset/processed/dataset_v1_bloom_audit.json',
  'training_dataset/processed/dataset_v1_bloom_train.csv',
  'src/agents/contracts.py',
  'src/agents/model_registry.py',
  'src/agents/orchestrator.py',
  'src/agents/question_knowledge_agent.py',
  'src/agents/answer_misconception_agent.py',
  'src/agents/cohort_prediction_agent.py',
  'src/analytics/topic_utils.py',
  'src/analytics/weak_topic_model.py',
  'src/api/dependencies.py',
  'PROPOSAL_IMPLEMENTATION_CHECKLIST.md'
)
$paths | ForEach-Object { "$_ -> $(Test-Path -LiteralPath $_)" }
```

Expected: all print `True`. Then:

```powershell
Select-String -Path FULL_MODEL_TRAINING_GUIDE.md -Pattern '## 1. Purpose','## 2. Audience','## 3. Target architecture','## 4. Status legend','## 5. Model inventory','## 6. Bloom-model','## 7. Training workflow','## 8. Model sections','## 9. Error prevention'
```

Expected: all nine headings present.

- [ ] **Step 3: Reconcile against the design checklist**

Check each item in `docs/superpowers/specs/2026-08-03-full-model-training-guide-design.md`:

- Purpose / audience → Task 1.
- Target architecture incl. current three-agent statement → Task 1 Step 2.
- Model inventory of eight models → Task 2.
- Training workflow 10-step format + Windows/Colab/proposed labelling → Task 4.
- Bloom percentage policy, six indicators → Task 3.
- Status representation, five categories with citations → Task 2.
- Error prevention, nine safeguards → Task 7.
- Verification: agent classes, registry entries, saved artifacts, training CLIs, Bloom audit/metadata,
  proposal checklist, regression command → Tasks 2, 3, 5, 8.
- Deliverable at repository root → confirmed in Task 1 Step 4.

- [ ] **Step 4: Inspect final diff and commit any remaining fix**

Run `git status --short`, `git diff --stat`, and `git diff --check` (must print nothing). Commit any
non-whitespace fix with message `docs: finalize full model training guide`. Confirm the staged
`model/cognitive_bloom/cognitive_bloom_model.joblib` change is still present (it is evidence of the retrain).

- [ ] **Step 5: Report the manual next step**

Tell the user the guide is complete and that the natural next research step is expert review of the
`training_dataset/processed/dataset_v1_bloom_review.csv` approvals, then a six-class Bloom expansion, before
any advanced model training.

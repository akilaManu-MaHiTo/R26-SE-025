# Full Model Training Guide Design

**Date:** 2026-08-03  
**Status:** Approved design  
**Target document:** `FULL_MODEL_TRAINING_GUIDE.md`

## 1. Purpose

Create one practical, research-honest guide for building, evaluating, saving, and integrating every model required by the intended four-domain-agent architecture. The orchestrator remains a separate workflow component and is not counted as a domain agent or trainable model.

The guide must distinguish three different states:

- capabilities and artifacts verified in the current repository;
- models that have a partial implementation but still need research validation;
- proposed models for agents or capabilities that are not implemented yet.

## 2. Audience

The primary reader is a fourth-year undergraduate researcher using Windows PowerShell locally and Google Colab for GPU-assisted experiments. Instructions must be executable by a reader who understands basic Python but may not know the repository internals.

## 3. Target architecture

The guide will describe four domain agents plus one separate orchestrator:

1. **Question and Rubric Knowledge Agent** — topic mapping, rubric mapping, Bloom classification, and future retrieval-backed evidence.
2. **Answer Grading and Misconception Agent** — semantic answer similarity, deterministic grading, concept analysis, and future misconception classification.
3. **Student and Cohort Cognitive Analytics Agent** — weak-topic classification, cognitive-gap analysis, misunderstood-question analysis, and cohort summaries.
4. **Exam Prediction and Question Generation Agent** — future-topic forecasting, question-structure prediction, and controlled question generation after prediction models are validated.
5. **Exam Analysis Orchestrator** — coordinates the four agents, records model versions, isolates failures, and persists results; it is not trained.

The guide must state that the repository currently contains three domain-agent classes (`QuestionKnowledgeAgent`, `AnswerMisconceptionAgent`, and `CohortPredictionAgent`). The target four-agent architecture requires splitting cohort analytics from future exam prediction/generation or adding a fourth agent without merging the orchestrator into that count.

## 4. Model inventory

Each model section will identify its owning agent, purpose, current implementation, training data, recommended first model, optional advanced model, artifact path, evaluation metrics, integration point, and completion gate.

The inventory will cover:

- Cognitive Bloom classifier.
- Topic/rubric mapper and future retrieval embedding model.
- Sentence-transformer answer-similarity model.
- Misconception classifier or bounded extraction model.
- Weak-topic classifier.
- Future-topic forecasting/ranking model.
- Question-structure prediction model.
- Controlled question-generation model or shared instruction model.

Rule-based analytics and the orchestrator will be documented but will not be presented as trainable models.

## 5. Training workflow format

Every trainable-model section will use the same sequence:

1. Define the prediction target and agent consumer.
2. Specify the minimum dataset schema and expert-labelled fields.
3. Define leakage-safe train, validation, and test splitting.
4. Train a simple reproducible baseline first.
5. Train an advanced comparison only when the dataset size supports it.
6. Evaluate with metrics appropriate to the target.
7. Save the model, label mapping, preprocessing configuration, metrics, and data fingerprint.
8. Integrate through the model registry or a stable adapter.
9. Run smoke, regression, and out-of-distribution tests.
10. Promote the model only after its stated research gate passes.

Windows/PowerShell commands will be provided for existing repository trainers. Colab workflows will be provided for models that benefit from GPU training. Proposed commands will be clearly labelled so they are not confused with commands that already exist in the repository.

## 6. Bloom-model percentage policy

The current Bloom model must not be summarized with one misleading percentage. The guide will report separate, reproducible indicators:

- **Internal validation accuracy: 100%** — the value produced by the current random 80/20 split.
- **Label-space coverage: 33.3%** — two observed labels divided by six intended Bloom levels.
- **Higher-order coverage: 0%** — no approved `apply`, `analyze`, `evaluate`, or `create` rows.
- **Dataset distribution: 25% remember and 75% understand** — 32 and 96 of 128 unique questions.
- **Research-valid six-class accuracy: not measurable** — no independent, balanced six-class test set exists.
- **Status: two-class pilot only** — the 100% score is driven by repeated question templates and must not be used as evidence of six-class generalization.

The guide will recommend macro-F1, per-class precision/recall/F1, confusion matrices, and independently authored or template-grouped test data for the next evaluation.

## 7. Status representation

The status table will use evidence-based categories instead of an invented readiness score:

- **Operational** — implemented and usable for its stated current scope.
- **Pilot** — trained or implemented but not research-valid for the intended scope.
- **Partial** — useful implementation exists, but essential data, evaluation, or integration is missing.
- **Not started** — no substantive trainable implementation or artifact exists.
- **Not trainable** — deterministic workflow or orchestration component.

Each status must cite a repository file, artifact, command output, or explicit missing acceptance gate.

## 8. Error prevention and research safeguards

The guide will explicitly prevent the following mistakes:

- treating the orchestrator as another AI model;
- claiming that every agent requires its own large language model;
- reporting template-driven validation accuracy as external performance;
- creating artificial class balance by assigning incorrect Bloom labels;
- splitting duplicates or paraphrases across training and test sets;
- calling historical trends a future forecast;
- allowing an optional language model to silently change deterministic marks;
- publishing forecast probabilities without temporal validation and calibration;
- training from student data without documented privacy, consent, and anonymization controls.

## 9. Verification

Before completion, the final guide will be checked against:

- current agent classes and orchestration contracts;
- current model registry entries and saved artifacts;
- current training-script CLI arguments;
- generated Bloom audit/model metadata;
- the proposal implementation checklist and approved agent-architecture design;
- the repository regression-test command.

All existing commands included in the guide must be executed or checked through their CLI help. Proposed commands must be marked as future scaffolding. File links must resolve from the repository root, and all reported percentages must be reproducible from stated counts.

## 10. Deliverable

Create `FULL_MODEL_TRAINING_GUIDE.md` at the repository root. It will be the single entry point for model ownership, current status, data preparation, local/Colab training, evaluation, integration, and the recommended research sequence.

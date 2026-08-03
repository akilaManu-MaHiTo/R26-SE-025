# Current Model Audit and Improvement Plan

**Status:** Approved design package for review  
**Date:** 2026-08-03  
**Purpose:** Define what the current models do, how agents use them, and what must change before production claims are made.

## 1. Model inventory

| Capability | Artifact / implementation | Current runtime use | Status |
|---|---|---|---|
| Answer semantic similarity | `model/similarity/exam_similarity_model/` | Grading service | Pilot/operational support |
| Bloom cognitive classification | `model/cognitive_bloom/cognitive_bloom_model.joblib` | Question and answer cognitive comparison | Two-class pilot |
| Weak-topic classification | `model/weak_topic/weak_topic_model.joblib` | Loaded, but default prediction path is deterministic | Pilot with routing defect |
| Existing-topic matching | `src/prediction/topic_prediction.py` | Token overlap | Deterministic baseline, not forecasting |
| Historical trend analysis | `src/prediction/trend_analysis.py` | Yearly means and slope | Descriptive analytics, not forecasting |

## 2. SentenceTransformer similarity model

### What it does

- Fine-tuned from `all-MiniLM-L6-v2`.
- Encodes model and student answers into 384-dimensional vectors.
- Uses cosine similarity as an answer-semantic signal.
- The model card reports 341 training pairs, five epochs, and `CosineSimilarityLoss`.

### Current use

The local grading service combines similarity with concept-keyword coverage. In the overall platform, GradingEngine already provides the authoritative score and feedback. QuestionExamPredictionEngine therefore treats similarity as an optional diagnostic feature, not as permission to regrade.

### Risks

- The model card reports labels concentrated between 0.7 and 1.0, which is insufficient evidence of discrimination against incorrect answers.
- No independent held-out evaluation is recorded.
- Raw cosine similarity is not a calibrated correctness probability.
- Course and domain coverage are narrow.

### Improvement plan

1. Build expert-labelled positive, partial, misconception, and incorrect answer pairs.
2. Split by question/template so paraphrases do not cross train and test.
3. Measure correlation with expert similarity judgements.
4. Measure retrieval Precision@K and separation of correct versus incorrect answers.
5. Evaluate by course, question type, answer length, and language.
6. Save a manifest with data fingerprint, metrics, supported domains, and limitations.
7. Use the model only when question-level answer text and a trusted reference exist.

### Promotion gate

Do not label the model production-grade until independent held-out results demonstrate useful separation of correct, partially correct, misconception, and incorrect answers.

## 3. Cognitive Bloom model

### What it does

- Uses word and bigram TF-IDF features.
- Uses class-balanced logistic regression.
- Predicts a Bloom label for the question and student answer.
- Converts labels to ordinal scores and calculates cognitive alignment.

### Current artifact evidence

- 128 reviewed training questions.
- 96 `understand` and 32 `remember`.
- Internal validation accuracy recorded as 1.0.
- No `apply`, `analyze`, `evaluate`, or `create` examples in the artifact.

The current 100% figure is a two-class internal result, not evidence of six-class Bloom performance.

### Runtime fallback

If the artifact cannot load, the code falls back to Bloom verb and answer-length heuristics covering all six levels. The fallback must be recorded in model provenance.

### Improvement plan

1. Complete expert review for all six Bloom levels.
2. Balance by class, subject, question template, and source.
3. Split by normalized question/template group.
4. Establish TF-IDF/logistic regression as the baseline.
5. Compare a sentence-transformer classifier after sufficient data exists.
6. Report macro-F1, per-class precision/recall/F1, confusion matrix, and calibration.
7. Test question classification and answer-demonstration classification separately.
8. Add an `unknown/insufficient_text` outcome instead of forced confidence.

### Promotion gate

Require a six-class independently authored holdout set, all classes represented, and an approved metric threshold defined with academic reviewers. Until then, return `pilot` provenance and allow lecturer review.

## 4. Weak-topic model

### What it does

The feature builder aggregates student attempts by topic into ten values:

1. average learning score;
2. average performance score;
3. average concept score;
4. average cognitive score;
5. score standard deviation;
6. weak-student count;
7. students attempted;
8. attempts;
9. weak-student share; and
10. average Bloom-level gap.

The saved pipeline is `StandardScaler + LogisticRegression` with a default weak probability threshold of 0.55.

### Current routing defect

`WeakTopicModel.predict(rows, use_deterministic=True)` defaults to a deterministic weighted weak score. `WeakTopicAnalyzer` calls `predict(topic_rows)` without changing that argument. Consequently, the loaded classifier is normally bypassed even though the artifact exists.

### Label-quality risk

Training labels are bootstrapped from the same score thresholds and weak-student share used as model features. This creates a circular target. The learned model cannot be claimed to discover expert weakness until compared with independent lecturer labels.

### Improvement plan

1. Define the authoritative weak-topic target with lecturers.
2. Collect lecturer weak/non-weak labels plus severity and intervention need.
3. Split data by course and assessment time, not random topic rows.
4. Retain the deterministic rule as a transparent baseline.
5. Train and evaluate the classifier against independent labels.
6. Compare precision, recall, F1, Average Precision, and stability across cohorts.
7. Make routing explicit: `mode=rule` or `mode=model`; never rely on a default boolean.
8. Report active mode and artifact version in every result.

### Promotion gate

The model must beat the deterministic rule on a lecturer-labelled temporal holdout and remain stable across supported courses.

## 5. Deterministic analytics

### Topic matching

Current topic matching counts non-stopword token overlap between supplied answer text and existing exam-topic/question text. It is useful as a fallback candidate generator. It does not discover topics and is not next-exam prediction.

### Historical trends

Current trend analysis calculates yearly averages and a least-squares slope. It is valid descriptive evidence. It must not populate future probabilities.

### Concept coverage

Current concept scoring compares answer words with keywords extracted from a model/reference answer, with limited stemming. It is interpretable but sensitive to terminology and reference-answer quality.

## 6. Required shared model manifest

Every artifact has a machine-readable manifest containing:

```text
capability_name
model_version
artifact_checksum
created_at
training_data_fingerprint
training_range
supported_courses
target_definition
feature_schema_version
label_schema_version
metrics
calibration_status
decision_thresholds
known_limitations
fallback_capability
approval_status
```

The registry loads the manifest before making a model available. An artifact with a missing or incompatible manifest is unavailable, not silently accepted.

## 7. Agent usage after corrections

| Model | Primary agent | Allowed use | Fallback |
|---|---|---|---|
| Similarity | Student Understanding Agent | Supporting semantic feature and evidence | Omit feature; preserve grade |
| Bloom | Question Knowledge and Student Understanding Agents | Required/demonstrated cognitive level | Explicit heuristic with warning |
| Weak topic | Cohort Forecasting Agent | Rank cohort topic weakness | Deterministic rule baseline |
| Topic token matcher | Question Knowledge Agent | Candidate topics only | Declared rubric topic |
| Trend analyzer | Cohort Forecasting Agent | Historical summaries/features | Empty history with warning |

## 8. Implementation sequence

1. Introduce model manifests and provenance contracts.
2. Add regression tests documenting current behavior.
3. Replace the weak-topic default boolean with an explicit mode.
4. Keep deterministic weak-topic mode active until independent evaluation passes.
5. Expand and independently evaluate the Bloom dataset.
6. Build the similarity evaluation dataset and report.
7. Add supported-course and out-of-distribution checks.
8. Expose model status, active mode, metrics, and warnings through the API.

## 9. Acceptance criteria

- No model is described more strongly than its evaluation supports.
- Weak-topic model versus rule selection is explicit and tested.
- The Bloom API exposes that the current artifact supports only two classes.
- Similarity output is never interpreted as a correctness probability.
- All model-derived fields record capability, version, fallback state, and confidence.
- Existing grading marks remain unchanged when models fail.


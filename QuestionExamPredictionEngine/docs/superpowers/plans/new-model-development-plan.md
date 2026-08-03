# New Model Development Plan

**Status:** Approved design package for review  
**Date:** 2026-08-03  
**Purpose:** Define every model or decision capability required to complete QuestionExamPredictionEngine.

## 1. Development policy

Every capability follows this sequence:

1. Define the target and decision owner.
2. Define the row-level dataset schema and provenance.
3. Establish a transparent baseline.
4. Prevent temporal, student, question-template, and label leakage.
5. Train an advanced model only when data volume and target quality support it.
6. Evaluate on independent data using target-appropriate metrics.
7. Calibrate probabilities where probabilities are exposed.
8. Package artifact, preprocessing, labels, metrics, and support manifest together.
9. Integrate through the Model Registry and a typed protocol.
10. Promote only after the acceptance gate passes.

## 2. Complete capability inventory

| Capability | Build type | Status | Owning agent |
|---|---|---|---|
| Answer similarity | Improve existing | Pilot | Student Understanding |
| Six-level Bloom classification | Replace/expand existing | Pilot | Question Knowledge and Student Understanding |
| Weak-topic classification | Correct/retrain existing | Pilot | Cohort Forecasting |
| Semantic topic and rubric mapping | New | Not started | Question Knowledge |
| Misconception extraction/classification | New | Not started | Student Understanding |
| Next-exam topic forecasting | New | Not started | Cohort Forecasting |
| Question-structure prediction | New | Not started | Cohort Forecasting |
| Student/cohort performance-risk prediction | New | Not started | Cohort Forecasting |
| Lecturer recommendation policy/ranker | New | Not started | Lecturer Support |
| Controlled practice-question generation | Optional later capability | Not started | Lecturer Support |

## 3. Semantic topic and rubric mapper

### Target

Map each rubric question to one or more canonical course topics and concepts with evidence from the rubric and approved course material.

### Dataset

One row per question-topic judgement:

```text
course_id, assessment_id, question_id, question_text,
rubric_criteria, model_answer, canonical_topic_ids,
concept_ids, lecturer_id_pseudonymous, approval_status
```

### Baseline

- Declared rubric topic where available.
- Existing token-overlap matcher as a candidate generator.
- Sentence-transformer nearest-neighbour retrieval over approved topic descriptions.

### Advanced option

A fine-tuned sentence-pair or multi-label classifier after sufficient lecturer-labelled mappings exist. ChromaDB is storage/retrieval infrastructure, not itself the model.

### Evaluation and gate

Use Precision@K, Recall@K, multi-label macro-F1, citation validity, coverage, and abstention rate. Split by assessment and question template. Every accepted mapping includes a canonical topic, confidence, source citation or declared-rubric provenance, and supported-course status.

## 4. Misconception detector

### Target

Identify a bounded, lecturer-defined misconception label from student-answer evidence without altering the mark.

### Dataset

```text
course_id, question_id, canonical_topic_ids, rubric_criteria,
reference_answer, student_answer, authoritative_score,
misconception_labels, evidence_span, lecturer_approval
```

Include correct, incomplete, irrelevant, and multiple-misconception examples. Student identifiers are not model features.

### Baseline

- Rubric-criterion misses.
- Concept-keyword gaps.
- Lecturer-authored rules for high-value misconceptions.

### Advanced options

- Multi-label classifier over question/reference/answer text.
- Bounded LLM extraction constrained to an approved taxonomy, JSON schema, retrieved evidence, and no mark modification.

### Evaluation and gate

Measure per-label precision/recall/F1, evidence-span accuracy, citation validity, false-positive rate on correct answers, and lecturer agreement. The detector must meet a lecturer-approved precision requirement, cite answer evidence, and abstain on unsupported labels.

## 5. Six-level Bloom model

This expands the current pilot because four intended classes are effectively unbuilt.

### Separate targets

- `required_bloom_level`: what the question requires.
- `demonstrated_bloom_level`: evidence demonstrated in a student answer.

These targets need separate datasets or explicitly distinct labels. A question label must not automatically become the answer label.

### Baseline and advanced option

- Baseline: TF-IDF plus logistic regression.
- Advanced: compact transformer or sentence-embedding classifier after a balanced dataset exists.

### Evaluation and gate

Use grouped independent test data, macro-F1, per-class reports, confusion matrices, ordinal-distance error, calibration, and abstention. All six classes must be represented before promotion.

## 6. Weak-topic classifier

### Target

Predict whether a topic needs lecturer intervention, ideally with severity or ranked priority, using independent lecturer judgement rather than labels derived from the same threshold features.

### Dataset and baseline

Use one row per course-topic-assessment cutoff containing only data available at that cutoff and a later lecturer/expert label. Compare against the current weak-student-share rule and ranking by average learning score.

### Evaluation and gate

Use temporal/course holdouts, precision/recall/F1, Average Precision, ranking stability, and improvement over both baselines.

## 7. Next-exam topic forecaster

### Target

For a course and future assessment horizon, rank canonical topics by likelihood of appearing and optionally produce calibrated probabilities.

### Training row

One row per `(course, cutoff assessment, candidate topic)`:

```text
course_id
cutoff_assessment_id
candidate_topic_id
target_next_assessment_contains_topic
historical_frequency
assessments_since_last_appearance
appearance_intervals
recent_marks_share
marks_trend
recent_bloom_distribution
question_type_distribution
student_weakness_features
curriculum_version
```

The label comes only from the next chronological assessment. No feature uses that assessment or later data.

### Baselines

- Global/course frequency ranking.
- Recency ranking.
- Frequency plus recency weighted score.

### Candidate models

- Regularized logistic regression or gradient-boosted trees over candidate topics.
- Learning-to-rank after sufficient cross-course history exists.
- Sequence models are out of scope until substantially more chronological data exists.

### Evaluation

Use expanding-window evaluation: train through assessment `T`, predict `T+1`.

- Precision@K and Recall@K.
- Mean Average Precision or NDCG.
- Brier score and reliability diagram for probabilities.
- Comparison with frequency and recency baselines.
- Metrics by course and forecast horizon.

### Gate

Publish probabilities only with a passing temporal evaluation artifact and calibration status. Otherwise return ranked baseline evidence or `forecast_unavailable`.

## 8. Question-structure predictor

### Target schema

Define and label before training:

- question type;
- required Bloom level;
- marks band;
- number of parts;
- answer form such as explanation, calculation, design, or diagram;
- difficulty band; and
- optionally command verb and expected answer length.

### Baseline and candidate models

Start with per-course empirical distributions conditioned on predicted topic and recent assessments. Later compare independent calibrated classifiers or a multi-output tree model.

### Evaluation and gate

Use macro-F1 for categorical fields, MAE for marks/parts, joint exact match, and temporal baseline comparison. Do not generate future questions until every required field has a defined label, temporal evaluation, and abstention behavior.

## 9. Student and cohort performance-risk predictor

### Target

Predict next-assessment risk, not the score of the assessment already graded. Supported targets are:

- probability of scoring below a lecturer-defined threshold;
- expected normalized score range; and
- topic-specific mastery risk.

### Training row

Use one row per student-course cutoff or cohort-course cutoff. Features include only prior results, trends, exposure counts, rubric mastery, cognitive gaps, and participation signals available before the target.

### Baselines and candidate models

- Last-score carry-forward.
- Historical student average.
- Cohort mean and simple trend.
- Regularized logistic/linear regression.
- Gradient-boosted trees with probability calibration.

### Evaluation

- AUROC and Average Precision for risk classification.
- Brier score and calibration.
- MAE/RMSE for expected score.
- False-negative analysis for at-risk students.
- Fairness/error analysis across permitted non-sensitive groups.

### Gate

Predictions are advisory, access-controlled, and never disciplinary. Every result includes the cutoff, evidence features, uncertainty, and a review path.

## 10. Lecturer recommendation engine

### First release: deterministic policy

This capability initially needs rules rather than a trained model:

- high weak-student share plus high concept gap → reteach with worked examples;
- repeated rubric-criterion misses → focused revision activity;
- high cognitive gap → practice at the required Bloom level;
- high-likelihood forecast plus current weakness → prioritize next-exam revision; and
- isolated student risk → targeted support rather than whole-cohort reteaching.

Every recommendation has reason codes, evidence IDs, priority, affected scope, and expiry/review date.

### Later learned ranker

Train only after lecturers record acceptance, completion, usefulness, and later outcomes. Evaluate acceptance, precision of intervention need, time saved, and subsequent mastery without claiming causation unless supported by study design.

## 11. Controlled practice-question generation

This optional capability follows forecasting and recommendation approval:

- Input: approved topic, Bloom level, structure, marks, difficulty, and evidence.
- Output: draft question, model answer, rubric, citations, duplication score, and safety flags.
- Controls: factual validation, past-paper leakage check, lecturer editing and approval.
- Generated content never enters a live exam automatically.

## 12. Artifact layout

```text
model/
  <capability>/
    <version>/
      artifact files
      manifest.json
      metrics.json
      preprocessing.json
      labels.json
      data_fingerprint.json
      model_card.md
```

## 13. Build order

1. Correct current model routing and provenance.
2. Build semantic topic mapping and a canonical topic dataset.
3. Build the six-level Bloom dataset/model.
4. Build lecturer-labelled weak-topic and misconception datasets/models.
5. Build the historical feature store and forecast baselines.
6. Train topic and performance-risk models.
7. Train question-structure prediction.
8. Implement deterministic lecturer recommendations.
9. Learn recommendation ranking after feedback accumulates.
10. Add optional controlled generation.

